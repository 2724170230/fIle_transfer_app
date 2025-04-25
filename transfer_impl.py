import os
import time
import hashlib
import threading
import logging
import socket
import json
import select
from queue import Queue
from typing import Dict, List, Tuple, Optional, Callable, Any, Set

from network import NetworkManager, Message, MessageType, DeviceInfo, BUFFER_SIZE, TRANSFER_PORT
from transfer import TransferManager, TransferTask, FileInfo

# 配置日志
logger = logging.getLogger("SendNow.TransferImpl")

def _transfer_server_loop(self):
    """传输服务器循环，监听传入的连接请求"""
    server_sock = self.network_manager.create_server_socket()
    
    logger.info(f"传输服务器已启动，监听端口 {TRANSFER_PORT}")
    
    while self.running:
        try:
            # 使用select非阻塞等待连接
            readable, _, _ = select.select([server_sock], [], [], 1.0)
            
            if not readable:
                continue
            
            client_sock, client_addr = server_sock.accept()
            logger.info(f"接受来自 {client_addr} 的连接")
            
            # 为每个连接创建一个处理线程
            handler_thread = threading.Thread(
                target=self._handle_client_connection,
                args=(client_sock, client_addr)
            )
            handler_thread.daemon = True
            handler_thread.start()
            
        except socket.timeout:
            continue
        except Exception as e:
            if self.running:
                logger.error(f"传输服务器出错: {e}")
                time.sleep(1)  # 出错后等待一会再重试
    
    server_sock.close()
    logger.info("传输服务器已停止")

def _handle_client_connection(self, client_sock: socket.socket, client_addr: Tuple[str, int]):
    """处理客户端连接"""
    try:
        client_sock.settimeout(10.0)  # 设置超时时间
        
        # 接收消息
        data = b""
        chunk = client_sock.recv(BUFFER_SIZE)
        while chunk:
            data += chunk
            # 检查是否接收到完整消息
            try:
                # 尝试解析JSON，如果成功则说明消息接收完毕
                json.loads(data.decode('utf-8'))
                break
            except:
                # 继续接收
                chunk = client_sock.recv(BUFFER_SIZE)
        
        # 解析消息
        message = Message.from_bytes(data)
        if not message:
            logger.error(f"从 {client_addr} 接收到无效消息")
            client_sock.close()
            return
        
        logger.debug(f"从 {client_addr} 接收到消息: {message.msg_type}")
        
        if message.msg_type == MessageType.TRANSFER_REQUEST:
            # 处理传输请求
            self._handle_transfer_request(message, client_sock)
        
        elif message.msg_type == MessageType.TRANSFER_ACCEPT:
            # 处理传输接受
            self._handle_transfer_accept(message, client_sock)
        
        elif message.msg_type == MessageType.TRANSFER_REJECT:
            # 处理传输拒绝
            self._handle_transfer_reject(message)
        
        elif message.msg_type == MessageType.FILE_INFO:
            # 处理文件信息
            self._handle_file_info(message, client_sock, client_addr)
        
        elif message.msg_type in [MessageType.PAUSE, MessageType.RESUME, MessageType.CANCEL]:
            # 处理传输控制命令
            self._handle_transfer_control(message)
        
        else:
            # 其他消息类型
            logger.warning(f"未处理的消息类型: {message.msg_type}")
    
    except Exception as e:
        logger.error(f"处理连接 {client_addr} 出错: {e}")
    
    finally:
        client_sock.close()

def _handle_transfer_request(self, message: Message, client_sock: socket.socket):
    """处理传输请求"""
    payload = message.payload
    if not payload or "transfer_id" not in payload:
        logger.error("无效的传输请求消息：缺少transfer_id")
        return
    
    # 兼容性处理：检查files或file_infos字段
    if "files" not in payload and "file_infos" not in payload:
        logger.error("无效的传输请求消息：缺少files或file_infos")
        return
    
    transfer_id = payload["transfer_id"]
    sender_id = payload.get("sender_id")
    sender_name = payload.get("sender_name", "未知设备")
    
    # 兼容性处理：优先使用file_infos，如果不存在则使用files
    files_data = payload.get("file_infos", []) or payload.get("files", [])
    
    # 查找发送设备
    sender_device = None
    for device in self.network_manager.get_devices():
        if device.device_id == sender_id:
            sender_device = device
            break
    
    if not sender_device:
        logger.error(f"找不到发送设备 ID={sender_id}")
        return
    
    # 创建文件信息列表
    files = []
    for file_data in files_data:
        file_info = FileInfo.from_dict(file_data)
        file_info.transfer_id = f"{transfer_id}_{file_info.file_id}"
        files.append(file_info)
        
        # 将文件信息添加到待处理列表
        self.pending_transfers[file_info.transfer_id] = file_info
    
    logger.info(f"收到来自 {sender_name} 的传输请求，文件数量: {len(files)}")
    
    # 触发传输请求回调
    if self.on_transfer_request:
        # 回调将决定是否自动接受传输
        auto_accept = self.on_transfer_request(sender_device, files)
        
        if auto_accept:
            # 自动接受所有文件
            for file_info in files:
                self.accept_transfer(file_info.transfer_id)

def _handle_transfer_accept(self, message: Message, client_sock: socket.socket):
    """处理传输接受响应"""
    payload = message.payload
    if not payload or "transfer_id" not in payload:
        logger.error("无效的传输接受消息")
        return
    
    transfer_id = payload["transfer_id"]
    accepted = payload.get("accepted", False)
    
    task = self.send_tasks.get(transfer_id)
    if not task:
        logger.error(f"找不到对应的发送任务: {transfer_id}")
        return
    
    if not accepted:
        reason = payload.get("reason", "接收方拒绝")
        logger.info(f"传输被拒绝: {transfer_id}, 原因: {reason}")
        task.file_info.status = "rejected"
        del self.send_tasks[transfer_id]
        return
    
    # 开始传输文件
    logger.info(f"传输请求已接受: {transfer_id}")
    task.file_info.status = "transferring"
    
    # 创建发送线程
    sender_thread = threading.Thread(
        target=self._send_file,
        args=(task, client_sock)
    )
    sender_thread.daemon = True
    self.sender_threads[transfer_id] = sender_thread
    sender_thread.start()

def _handle_transfer_reject(self, message: Message):
    """处理传输拒绝响应"""
    payload = message.payload
    if not payload or "transfer_id" not in payload:
        logger.error("无效的传输拒绝消息")
        return
    
    transfer_id = payload["transfer_id"]
    reason = payload.get("reason", "未指定原因")
    
    # 查找对应的发送任务
    task = self.send_tasks.get(transfer_id)
    if not task:
        logger.error(f"找不到对应的发送任务: {transfer_id}")
        return
    
    logger.info(f"传输被拒绝: {transfer_id}, 原因: {reason}")
    
    # 更新任务状态
    task.file_info.status = "rejected"
    
    # 触发错误回调
    if self.on_transfer_error:
        self.on_transfer_error(task.file_info, f"传输被拒绝: {reason}")
    
    # 从任务列表中移除
    del self.send_tasks[transfer_id]

def _handle_file_info(self, message: Message, client_sock: socket.socket, client_addr: Tuple[str, int]):
    """处理文件信息消息，准备接收文件"""
    payload = message.payload
    if not payload or "file_info" not in payload:
        logger.error("无效的文件信息消息")
        return
    
    file_data = payload["file_info"]
    transfer_id = file_data.get("transfer_id")
    
    # 查找对应的接收任务
    task = self.receive_tasks.get(transfer_id)
    if not task:
        logger.error(f"找不到对应的接收任务: {transfer_id}")
        return
    
    # 更新文件信息
    task.file_info = FileInfo.from_dict(file_data)
    task.file_info.save_path = os.path.join(self.default_save_dir, task.file_info.file_name)
    
    logger.info(f"准备接收文件: {task.file_info.file_name}, 大小: {task.file_info.get_formatted_size()}")
    
    # 创建接收线程
    receiver_thread = threading.Thread(
        target=self._receive_file,
        args=(task, client_sock)
    )
    receiver_thread.daemon = True
    self.receiver_threads[transfer_id] = receiver_thread
    receiver_thread.start()

def _handle_transfer_control(self, message: Message):
    """处理传输控制命令（暂停、继续、取消）"""
    payload = message.payload
    if not payload or "transfer_id" not in payload or "action" not in payload:
        logger.error("无效的传输控制消息")
        return
    
    transfer_id = payload["transfer_id"]
    action = payload["action"]
    
    # 查找对应的传输任务
    task = self.send_tasks.get(transfer_id) or self.receive_tasks.get(transfer_id)
    if not task:
        logger.error(f"找不到对应的传输任务: {transfer_id}")
        return
    
    if action == "pause":
        logger.info(f"暂停传输: {transfer_id}")
        task.paused = True
        task.file_info.status = "paused"
    
    elif action == "resume":
        logger.info(f"恢复传输: {transfer_id}")
        task.paused = False
        task.file_info.status = "transferring"
    
    elif action == "cancel":
        logger.info(f"取消传输: {transfer_id}")
        task.cancelled = True
        task.file_info.status = "cancelled"
        
        # 如果是接收方，删除未完成的文件
        if not task.is_sender and task.file_info.save_path and os.path.exists(task.file_info.save_path):
            try:
                os.remove(task.file_info.save_path)
            except Exception as e:
                logger.error(f"删除未完成文件失败: {e}")
        
        # 从任务列表中移除
        if transfer_id in self.send_tasks:
            del self.send_tasks[transfer_id]
        
        if transfer_id in self.receive_tasks:
            del self.receive_tasks[transfer_id]

def _handle_network_message(self, message: Message, addr: Tuple[str, int]):
    """处理网络消息回调"""
    # 这里主要处理通过UDP广播收到的控制消息
    if message.msg_type in [MessageType.PAUSE, MessageType.RESUME, MessageType.CANCEL]:
        self._handle_transfer_control(message)

def _send_file(self, task: TransferTask, client_sock: socket.socket = None):
    """发送文件实现"""
    try:
        file_info = task.file_info
        device = task.device
        transfer_id = task.transfer_id
        
        if not file_info.file_path or not os.path.exists(file_info.file_path):
            raise Exception(f"文件不存在: {file_info.file_path}")
        
        # 标记任务开始
        task.start_time = time.time()
        task.status = "transferring"
        file_info.status = "transferring"
        
        # 计算文件哈希值（如果尚未计算）
        if not file_info.file_hash:
            file_info.calculate_hash()
        
        # 如果没有提供socket，则创建一个新的连接
        needs_close = False
        if not client_sock:
            client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_sock.settimeout(10.0)
            client_sock.connect((device.ip_address, device.port))
            needs_close = True
            
            # 发送文件信息
            file_info_message = Message(MessageType.FILE_INFO, {"file_info": file_info.to_dict()})
            client_sock.sendall(file_info_message.to_bytes())
            
            # 等待接收方准备就绪
            time.sleep(0.5)
        
        task.socket = client_sock
        
        # 打开文件并发送数据
        file_size = file_info.file_size
        chunk_size = file_info.chunk_size
        bytes_sent = 0
        
        with open(file_info.file_path, 'rb') as f:
            while bytes_sent < file_size and not task.cancelled:
                # 检查是否暂停
                if task.paused:
                    time.sleep(0.1)
                    continue
                
                # 计算本次发送的大小
                size_to_send = min(chunk_size, file_size - bytes_sent)
                
                # 读取文件块
                chunk = f.read(size_to_send)
                if not chunk:
                    break
                
                # 构建数据包头
                header = {
                    "transfer_id": transfer_id,
                    "offset": bytes_sent,
                    "size": len(chunk)
                }
                header_json = json.dumps(header)
                header_bytes = header_json.encode('utf-8')
                
                # 发送头部长度（4字节）
                header_len = len(header_bytes)
                client_sock.sendall(header_len.to_bytes(4, byteorder='big'))
                
                # 发送头部
                client_sock.sendall(header_bytes)
                
                # 发送数据
                client_sock.sendall(chunk)
                
                # 更新进度
                bytes_sent += len(chunk)
                task.update_progress(bytes_sent)
                
                # 控制发送速度，避免网络拥堵
                time.sleep(0.001)
        
        # 发送完成消息
        if not task.cancelled:
            complete_message = {
                "transfer_id": transfer_id,
                "completed": True,
                "file_hash": file_info.file_hash
            }
            message = Message(MessageType.COMPLETE, complete_message)
            client_sock.sendall(message.to_bytes())
            
            # 更新状态
            task.status = "completed"
            file_info.status = "completed"
            task.end_time = time.time()
            
            logger.info(f"文件发送完成: {file_info.file_name}, 大小: {file_info.get_formatted_size()}")
            
            # 触发完成回调
            if self.on_transfer_complete:
                self.on_transfer_complete(file_info, True)
    
    except Exception as e:
        logger.error(f"发送文件出错: {e}")
        
        # 更新状态
        task.status = "failed"
        file_info.status = "failed"
        
        # 触发错误回调
        if self.on_transfer_error:
            self.on_transfer_error(file_info, f"发送失败: {str(e)}")
    
    finally:
        # 清理资源
        if needs_close and client_sock:
            client_sock.close()
        
        # 从发送任务列表中移除
        if transfer_id in self.send_tasks and (task.status == "completed" or task.status == "failed"):
            del self.send_tasks[transfer_id]
        
        # 从线程池中移除
        if transfer_id in self.sender_threads:
            del self.sender_threads[transfer_id]

def _receive_file(self, task: TransferTask, client_sock: socket.socket):
    """接收文件实现"""
    try:
        file_info = task.file_info
        transfer_id = task.transfer_id
        
        # 标记任务开始
        task.start_time = time.time()
        task.status = "transferring"
        file_info.status = "transferring"
        
        # 创建保存文件的目录
        save_dir = os.path.dirname(file_info.save_path)
        os.makedirs(save_dir, exist_ok=True)
        
        task.socket = client_sock
        
        # 打开文件用于写入
        bytes_received = 0
        
        with open(file_info.save_path, 'wb') as f:
            while not task.cancelled:
                # 检查是否暂停
                if task.paused:
                    time.sleep(0.1)
                    continue
                
                # 接收头部长度
                try:
                    header_len_bytes = client_sock.recv(4)
                    if not header_len_bytes:
                        break
                    
                    header_len = int.from_bytes(header_len_bytes, byteorder='big')
                    
                    # 接收头部
                    header_bytes = b""
                    while len(header_bytes) < header_len:
                        chunk = client_sock.recv(header_len - len(header_bytes))
                        if not chunk:
                            raise Exception("连接中断")
                        header_bytes += chunk
                    
                    header = json.loads(header_bytes.decode('utf-8'))
                    
                    # 检查是否是完成消息
                    if "completed" in header and header["completed"]:
                        logger.info(f"接收文件完成: {file_info.file_name}")
                        break
                    
                    # 获取数据大小
                    data_size = header["size"]
                    
                    # 接收数据
                    data = b""
                    while len(data) < data_size:
                        chunk = client_sock.recv(min(BUFFER_SIZE, data_size - len(data)))
                        if not chunk:
                            raise Exception("连接中断")
                        data += chunk
                    
                    # 写入文件
                    f.write(data)
                    
                    # 更新进度
                    bytes_received += len(data)
                    task.update_progress(bytes_received)
                
                except socket.timeout:
                    logger.warning(f"接收超时: {transfer_id}")
                    continue
                except Exception as e:
                    logger.error(f"接收数据出错: {e}")
                    break
        
        # 验证文件完整性
        if file_info.file_hash and not task.cancelled:
            is_valid = file_info.verify_hash(file_info.save_path)
            if not is_valid:
                raise Exception("文件哈希验证失败，传输可能不完整")
        
        # 更新状态
        if not task.cancelled:
            task.status = "completed"
            file_info.status = "completed"
            task.end_time = time.time()
            
            logger.info(f"文件接收完成: {file_info.file_name}, 保存到 {file_info.save_path}")
            
            # 触发完成回调
            if self.on_transfer_complete:
                self.on_transfer_complete(file_info, False)
    
    except Exception as e:
        logger.error(f"接收文件出错: {e}")
        
        # 更新状态
        task.status = "failed"
        file_info.status = "failed"
        
        # 删除不完整的文件
        if file_info.save_path and os.path.exists(file_info.save_path):
            try:
                os.remove(file_info.save_path)
                logger.info(f"删除不完整的文件: {file_info.save_path}")
            except Exception as e:
                logger.error(f"删除不完整文件失败: {e}")
        
        # 触发错误回调
        if self.on_transfer_error:
            self.on_transfer_error(file_info, f"接收失败: {str(e)}")
    
    finally:
        # 清理资源
        if client_sock:
            client_sock.close()
        
        # 从接收任务列表中移除
        if transfer_id in self.receive_tasks and (task.status == "completed" or task.status == "failed"):
            del self.receive_tasks[transfer_id]
        
        # 从线程池中移除
        if transfer_id in self.receiver_threads:
            del self.receiver_threads[transfer_id]

def _on_file_progress(self, file_info: FileInfo, progress: float, speed: float):
    """文件传输进度回调"""
    if self.on_file_progress:
        self.on_file_progress(file_info, progress, speed)

def _on_file_complete(self, file_info: FileInfo, is_sender: bool):
    """文件传输完成回调"""
    if self.on_transfer_complete:
        self.on_transfer_complete(file_info, is_sender)

def _on_file_error(self, file_info: FileInfo, error_message: str):
    """文件传输错误回调"""
    if self.on_transfer_error:
        self.on_transfer_error(file_info, error_message)

# 将方法添加到 TransferManager 类
setattr(TransferManager, "_transfer_server_loop", _transfer_server_loop)
setattr(TransferManager, "_handle_client_connection", _handle_client_connection)
setattr(TransferManager, "_handle_transfer_request", _handle_transfer_request)
setattr(TransferManager, "_handle_transfer_accept", _handle_transfer_accept)
setattr(TransferManager, "_handle_transfer_reject", _handle_transfer_reject)
setattr(TransferManager, "_handle_file_info", _handle_file_info)
setattr(TransferManager, "_handle_transfer_control", _handle_transfer_control)
setattr(TransferManager, "_handle_network_message", _handle_network_message)
setattr(TransferManager, "_send_file", _send_file)
setattr(TransferManager, "_receive_file", _receive_file)
setattr(TransferManager, "_on_file_progress", _on_file_progress)
setattr(TransferManager, "_on_file_complete", _on_file_complete)
setattr(TransferManager, "_on_file_error", _on_file_error) 