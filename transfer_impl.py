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
import struct
import traceback

from network import NetworkManager, Message, MessageType, DeviceInfo, BUFFER_SIZE, TRANSFER_PORT
from transfer import TransferManager, TransferTask, FileInfo

# 配置日志
logger = logging.getLogger("SendNow.TransferImpl")

def recv_all(sock: socket.socket, n: int) -> bytes:
    """
    确保从套接字接收指定数量的字节
    
    Args:
        sock: 套接字对象
        n: 需要接收的字节数
        
    Returns:
        bytes: 接收到的字节数据
    """
    data = b''
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:  # 套接字已关闭
            return None
        data += packet
    return data

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
    
    # 查找对应的发送任务 - 直接匹配
    task = self.send_tasks.get(transfer_id)
    
    # 如果没有找到对应的任务，尝试查找相关的任务
    if not task:
        # 记录调试信息
        logger.info(f"收到传输接受消息，但未找到直接对应的任务: {transfer_id}")
        logger.info(f"当前的发送任务列表: {list(self.send_tasks.keys())}")
        
        # 尝试查找以该ID开头的任务（用于处理组合ID: global_id_file_id）
        for task_id in list(self.send_tasks.keys()):
            if task_id.startswith(transfer_id + "_") or transfer_id.startswith(task_id + "_"):
                logger.info(f"找到关联的传输任务: {task_id}")
                task = self.send_tasks.get(task_id)
                transfer_id = task_id  # 更新为实际的任务ID
                break
        
        # 尝试通过file_id匹配
        if not task and "file_id" in payload:
            file_id = payload.get("file_id")
            logger.info(f"尝试通过文件ID匹配任务: {file_id}")
            for task_id, task_obj in self.send_tasks.items():
                if task_obj.file_info.file_id == file_id:
                    logger.info(f"通过文件ID找到匹配的任务: {task_id}")
                    task = task_obj
                    transfer_id = task_id
                    break
    
    # 如果仍未找到任务，报错并返回
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
    
    # 查找对应的发送任务 - 直接匹配
    task = self.send_tasks.get(transfer_id)
    
    # 如果没有找到对应的任务，尝试查找相关的任务
    if not task:
        # 记录调试信息
        logger.info(f"收到传输拒绝消息，但未找到直接对应的任务: {transfer_id}")
        logger.info(f"当前的发送任务列表: {list(self.send_tasks.keys())}")
        
        # 尝试查找以该ID开头的任务（用于处理组合ID: global_id_file_id）
        for task_id in list(self.send_tasks.keys()):
            if task_id.startswith(transfer_id + "_") or transfer_id.startswith(task_id + "_"):
                logger.info(f"找到关联的传输任务: {task_id}")
                task = self.send_tasks.get(task_id)
                transfer_id = task_id  # 更新为实际的任务ID
                break
        
        # 尝试通过file_id匹配
        if not task and "file_id" in payload:
            file_id = payload.get("file_id")
            logger.info(f"尝试通过文件ID匹配任务: {file_id}")
            for task_id, task_obj in self.send_tasks.items():
                if task_obj.file_info.file_id == file_id:
                    logger.info(f"通过文件ID找到匹配的任务: {task_id}")
                    task = task_obj
                    transfer_id = task_id
                    break
    
    # 如果仍未找到任务，报错并返回
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
    
    # 查找对应的接收任务 - 直接匹配
    task = self.receive_tasks.get(transfer_id)
    
    # 如果没有找到对应的任务，尝试查找相关的任务
    if not task:
        # 记录调试信息
        logger.info(f"收到文件信息消息，但未找到直接对应的任务: {transfer_id}")
        logger.info(f"当前的接收任务列表: {list(self.receive_tasks.keys())}")
        
        # 尝试查找以该ID开头的任务（用于处理组合ID: global_id_file_id）
        for task_id in list(self.receive_tasks.keys()):
            if task_id.startswith(transfer_id + "_") or transfer_id.startswith(task_id + "_"):
                logger.info(f"找到关联的接收任务: {task_id}")
                task = self.receive_tasks.get(task_id)
                transfer_id = task_id  # 更新为实际的任务ID
                break
        
        # 尝试通过file_id匹配
        file_id = file_data.get("file_id")
        if not task and file_id:
            logger.info(f"尝试通过文件ID匹配任务: {file_id}")
            for task_id, task_obj in self.receive_tasks.items():
                if task_obj.file_info.file_id == file_id:
                    logger.info(f"通过文件ID找到匹配的任务: {task_id}")
                    task = task_obj
                    transfer_id = task_id
                    break
    
    # 如果仍未找到任务，报错并返回
    if not task:
        logger.error(f"找不到对应的接收任务: {transfer_id}")
        return
    
    # 更新文件信息
    file_info = FileInfo.from_dict(file_data)
    
    # 确保保存路径存在并且有权限写入
    save_dir = self.default_save_dir
    full_save_path = os.path.join(save_dir, file_info.file_name)
    
    # 创建保存目录
    try:
        os.makedirs(save_dir, exist_ok=True)
        logger.info(f"确保保存目录存在: {save_dir}, 完整保存路径: {full_save_path}")
        
        # 检查目录权限
        if not os.access(save_dir, os.W_OK):
            logger.error(f"无权限写入保存目录: {save_dir}")
            # 尝试使用临时目录
            import tempfile
            temp_dir = tempfile.gettempdir()
            full_save_path = os.path.join(temp_dir, file_info.file_name)
            logger.info(f"改用临时目录: {temp_dir}, 新保存路径: {full_save_path}")
    except Exception as e:
        logger.error(f"创建保存目录失败: {e}")
        import tempfile
        temp_dir = tempfile.gettempdir()
        full_save_path = os.path.join(temp_dir, file_info.file_name)
        logger.info(f"改用临时目录: {temp_dir}, 新保存路径: {full_save_path}")
    
    # 设置文件保存路径
    file_info.save_path = full_save_path
    task.file_info = file_info
    
    logger.info(f"准备接收文件: {task.file_info.file_name}, 大小: {task.file_info.get_formatted_size()}, 保存到: {task.file_info.save_path}")
    
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
    
    # 查找对应的传输任务 - 直接匹配
    task = self.send_tasks.get(transfer_id) or self.receive_tasks.get(transfer_id)
    
    # 如果没有找到对应的任务，尝试查找相关的任务
    if not task:
        # 记录调试信息
        logger.info(f"收到传输控制消息({action})，但未找到直接对应的任务: {transfer_id}")
        logger.info(f"当前的发送任务列表: {list(self.send_tasks.keys())}")
        logger.info(f"当前的接收任务列表: {list(self.receive_tasks.keys())}")
        
        # 尝试在发送任务中查找
        for task_id in list(self.send_tasks.keys()):
            if task_id.startswith(transfer_id + "_") or transfer_id.startswith(task_id + "_"):
                logger.info(f"在发送任务中找到关联的传输任务: {task_id}")
                task = self.send_tasks.get(task_id)
                transfer_id = task_id  # 更新为实际的任务ID
                break
        
        # 如果在发送任务中未找到，尝试在接收任务中查找
        if not task:
            for task_id in list(self.receive_tasks.keys()):
                if task_id.startswith(transfer_id + "_") or transfer_id.startswith(task_id + "_"):
                    logger.info(f"在接收任务中找到关联的传输任务: {task_id}")
                    task = self.receive_tasks.get(task_id)
                    transfer_id = task_id  # 更新为实际的任务ID
                    break
    
    # 如果仍未找到任务，报错并返回
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
    needs_close = False
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
        if not client_sock:
            logger.debug(f"创建新的套接字连接到 {device.ip_address}:{device.port}")
            client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_sock.settimeout(10.0)
            client_sock.connect((device.ip_address, device.port))
            needs_close = True
            
            # 发送文件信息
            file_info_message = Message(MessageType.FILE_INFO, {"file_info": file_info.to_dict()})
            client_sock.sendall(file_info_message.to_bytes())
            
            # 等待接收方准备就绪
            time.sleep(0.5)
        else:
            # 检查socket是否有效
            try:
                client_sock.getpeername()  # 如果套接字已关闭会抛出异常
            except Exception as e:
                logger.warning(f"提供的套接字无效，创建新的连接: {e}")
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
                
                try:
                    # 发送头部长度（4字节）
                    header_len = len(header_bytes)
                    client_sock.sendall(header_len.to_bytes(4, byteorder='big'))
                    
                    # 发送头部
                    client_sock.sendall(header_bytes)
                    
                    # 发送数据
                    client_sock.sendall(chunk)
                except (socket.error, BrokenPipeError) as e:
                    logger.error(f"发送数据时套接字错误: {e}")
                    raise
                
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
        if isinstance(e, socket.error):
            logger.error(f"套接字错误详情: {traceback.format_exc()}")
        
        # 更新状态
        task.status = "failed"
        file_info.status = "failed"
        
        # 触发错误回调
        if self.on_transfer_error:
            self.on_transfer_error(file_info, f"发送失败: {str(e)}")
    
    finally:
        # 清理资源
        if needs_close and client_sock:
            try:
                client_sock.close()
            except Exception as e:
                logger.debug(f"关闭套接字时出错: {e}")
        
        # 从发送任务列表中移除
        if transfer_id in self.send_tasks and (task.status == "completed" or task.status == "failed"):
            del self.send_tasks[transfer_id]
        
        # 从线程池中移除
        if transfer_id in self.sender_threads:
            del self.sender_threads[transfer_id]

def _receive_file(self, task: TransferTask, client_sock: socket.socket):
    """接收文件内容并保存"""
    try:
        # 确认文件信息已设置
        if not task.file_info or not task.file_info.save_path:
            raise ValueError(f"任务{task.task_id}的文件信息未设置或保存路径无效")
        
        logger.info(f"开始接收文件: {task.file_info.file_name}, 保存到: {task.file_info.save_path}")
        
        # 设置任务状态为正在接收
        task.status = "receiving"
        if task.manager:
            task.manager.update_task_status(task)
        
        # 确保目标目录存在
        save_dir = os.path.dirname(task.file_info.save_path)
        os.makedirs(save_dir, exist_ok=True)
        
        # 将文件名指定为绝对路径
        save_path = task.file_info.save_path
        
        # 创建临时文件名，用于部分下载
        temp_file_path = f"{save_path}.part"
        
        bytes_received = 0
        expected_size = task.file_info.file_size
        last_progress_update = time.time()
        progress_update_interval = 0.5  # 更新间隔，秒
        
        logger.info(f"正在接收文件数据到临时文件: {temp_file_path}")
        
        with open(temp_file_path, 'wb') as f:
            # 接收数据块直到文件接收完成
            while bytes_received < expected_size:
                # 最大缓冲区：8MB
                client_sock.settimeout(30)  # 设置30秒超时
                try:
                    # 接收数据块头部(数据块大小)
                    header = recv_all(client_sock, 4)
                    if not header or len(header) < 4:
                        logger.error(f"接收文件头错误，收到: {header}")
                        raise ConnectionError("接收文件头错误")
                    
                    # 解析数据块大小
                    chunk_size = struct.unpack("!I", header)[0]
                    logger.debug(f"接收数据块，大小: {chunk_size} 字节")
                    
                    # 接收数据块
                    if chunk_size > 0:
                        chunk = recv_all(client_sock, chunk_size)
                        if not chunk or len(chunk) < chunk_size:
                            logger.error(f"接收数据块错误，预期大小: {chunk_size}，实际大小: {len(chunk) if chunk else 0}")
                            raise ConnectionError("接收数据块错误")
                        
                        # 写入文件
                        f.write(chunk)
                        bytes_received += len(chunk)
                        
                        # 更新进度
                        current_time = time.time()
                        if current_time - last_progress_update >= progress_update_interval:
                            task.update_progress(bytes_received)
                            last_progress_update = current_time
                            logger.debug(f"文件传输进度: {task.progress:.2f}%，已接收: {bytes_received}/{expected_size} 字节")
                    else:
                        logger.warning("收到零大小数据块，跳过")
                        
                except socket.timeout:
                    logger.error("接收数据超时")
                    raise ConnectionError("接收数据超时")
            
            # 最后一次进度更新，确保显示100%
            task.update_progress(bytes_received)
            logger.info(f"文件接收完成: {task.file_info.file_name}，大小: {bytes_received} 字节")
        
        # 验证接收到的数据大小
        if bytes_received != expected_size:
            logger.error(f"文件大小不匹配: 预期 {expected_size}，实际接收 {bytes_received}")
            task.status = "failed"
            task.error_message = "文件大小不匹配"
            os.remove(temp_file_path)  # 删除不完整文件
            return
        
        # 验证文件哈希(如果有)
        if task.file_info.file_hash:
            with open(temp_file_path, 'rb') as f:
                file_hash = compute_file_hash(f)
                if file_hash != task.file_info.file_hash:
                    logger.error(f"文件哈希不匹配: 预期 {task.file_info.file_hash}，计算得到 {file_hash}")
                    task.status = "failed"
                    task.error_message = "文件哈希不匹配"
                    os.remove(temp_file_path)  # 删除不完整文件
                    return
        
        # 将临时文件重命名为最终文件名
        try:
            # 确保目标文件不存在
            if os.path.exists(save_path):
                os.remove(save_path)
            os.rename(temp_file_path, save_path)
            logger.info(f"已将临时文件重命名为最终文件: {save_path}")
        except Exception as e:
            logger.error(f"重命名文件失败: {e}")
            task.status = "failed"
            task.error_message = f"重命名文件失败: {str(e)}"
            return
        
        # 更新任务状态为已完成
        task.status = "completed"
        # 确保进度显示为100%
        task.update_progress(expected_size)
        logger.info(f"文件接收任务完成: {task.task_id}, 文件: {task.file_info.file_name}")
        
        # 发送完成确认消息
        self._send_transfer_complete(task)
        
    except ConnectionError as e:
        logger.error(f"连接错误: {e}")
        task.status = "failed"
        task.error_message = f"连接错误: {str(e)}"
    except Exception as e:
        logger.error(f"接收文件出错: {e}")
        logger.error(traceback.format_exc())
        task.status = "failed"
        task.error_message = f"接收文件出错: {str(e)}"
    finally:
        # 更新任务状态
        if task.manager:
            task.manager.update_task_status(task)
        
        # 如果任务失败且临时文件仍存在，删除它
        if task.status == "failed" and os.path.exists(f"{save_path}.part"):
            try:
                os.remove(f"{save_path}.part")
                logger.info(f"已删除不完整的临时文件: {save_path}.part")
            except Exception as e:
                logger.error(f"删除临时文件失败: {e}")
        
        # 从接收线程列表中移除
        if task.task_id in self.receiver_threads:
            del self.receiver_threads[task.task_id]

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