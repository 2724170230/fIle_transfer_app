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
import subprocess
import sys
import shutil

from network import NetworkManager, Message, MessageType, DeviceInfo, BUFFER_SIZE, TRANSFER_PORT
from transfer import TransferManager, TransferTask, FileInfo

# 配置日志
logger = logging.getLogger("SendNow.TransferImpl")

def debug_system_info():
    """收集系统信息用于调试"""
    info = []
    info.append(f"Python版本: {sys.version}")
    info.append(f"平台: {sys.platform}")
    
    # 检查用户目录
    home = os.path.expanduser("~")
    info.append(f"用户主目录: {home}")
    
    # 检查下载目录
    download_dir = os.path.join(home, "Downloads")
    app_download_dir = os.path.join(download_dir, "SendNow")
    
    info.append(f"下载目录: {download_dir} (存在: {os.path.exists(download_dir)})")
    info.append(f"程序下载目录: {app_download_dir} (存在: {os.path.exists(app_download_dir)})")
    
    # 检查目录权限
    if os.path.exists(download_dir):
        info.append(f"下载目录权限: {'可写' if os.access(download_dir, os.W_OK) else '不可写'}")
    
    if os.path.exists(app_download_dir):
        info.append(f"程序下载目录权限: {'可写' if os.access(app_download_dir, os.W_OK) else '不可写'}")
        # 尝试列出目录内容
        try:
            files = os.listdir(app_download_dir)
            info.append(f"程序下载目录内容: {files}")
        except Exception as e:
            info.append(f"列出程序下载目录内容失败: {e}")
    
    # 检查临时目录
    import tempfile
    temp_dir = tempfile.gettempdir()
    info.append(f"临时目录: {temp_dir} (存在: {os.path.exists(temp_dir)})")
    if os.path.exists(temp_dir):
        info.append(f"临时目录权限: {'可写' if os.access(temp_dir, os.W_OK) else '不可写'}")
    
    # 检查磁盘空间
    try:
        if sys.platform == 'win32':
            free_bytes = ctypes.c_ulonglong(0)
            ctypes.windll.kernel32.GetDiskFreeSpaceExW(ctypes.c_wchar_p(download_dir), None, None, ctypes.pointer(free_bytes))
            info.append(f"下载目录可用空间: {free_bytes.value / (1024 * 1024 * 1024):.2f} GB")
        else:
            total, used, free = shutil.disk_usage(download_dir)
            info.append(f"下载目录可用空间: {free / (1024 * 1024 * 1024):.2f} GB")
    except Exception as e:
        info.append(f"获取磁盘空间信息失败: {e}")
    
    # 返回收集的信息
    return "\n".join(info)

# 在模块导入时输出系统信息
logger.info(f"系统信息:\n{debug_system_info()}")

def list_directory(directory):
    """列出目录内容，返回详细信息"""
    try:
        if not os.path.exists(directory):
            return f"目录不存在: {directory}"
        
        if not os.path.isdir(directory):
            return f"路径不是目录: {directory}"
        
        result = f"目录: {directory}\n"
        
        # 尝试使用系统命令获取更详细信息
        try:
            if sys.platform == 'win32':
                cmd = ['dir', '/a', directory]
                shell = True
            else:
                cmd = ['ls', '-la', directory]
                shell = False
            
            proc = subprocess.run(cmd, capture_output=True, text=True, shell=shell)
            if proc.returncode == 0:
                return result + proc.stdout
            else:
                result += f"系统命令失败: {proc.stderr}\n"
        except Exception as e:
            result += f"执行系统命令失败: {e}\n"
        
        # 回退到Python方法
        files = os.listdir(directory)
        for f in files:
            full_path = os.path.join(directory, f)
            try:
                stats = os.stat(full_path)
                size = stats.st_size
                mtime = time.ctime(stats.st_mtime)
                file_type = "目录" if os.path.isdir(full_path) else "文件"
                result += f"{f:30} {file_type:6} {size:10} 字节 {mtime}\n"
            except Exception as e:
                result += f"{f:30} - 无法获取信息: {e}\n"
        
        return result
    except Exception as e:
        return f"列出目录 {directory} 失败: {e}"

def compute_file_hash(file_obj, algorithm='sha256', chunk_size=8192):
    """
    计算文件的哈希值
    
    Args:
        file_obj: 已打开的文件对象
        algorithm: 哈希算法，默认sha256
        chunk_size: 读取文件的块大小
        
    Returns:
        str: 十六进制哈希值
    """
    hasher = hashlib.new(algorithm)
    
    # 保存当前文件位置
    current_pos = file_obj.tell()
    
    # 将文件指针移动到开始
    file_obj.seek(0)
    
    # 计算哈希值
    chunk = file_obj.read(chunk_size)
    while chunk:
        hasher.update(chunk)
        chunk = file_obj.read(chunk_size)
    
    # 恢复文件指针位置
    file_obj.seek(current_pos)
    
    return hasher.hexdigest()

def recv_all(sock: socket.socket, n: int) -> bytes:
    """
    确保从套接字接收指定数量的字节
    
    Args:
        sock: 套接字对象
        n: 需要接收的字节数
        
    Returns:
        bytes: 接收到的字节数据
        None: 如果连接关闭或出错
    """
    # 检查参数合法性
    if n <= 0:
        logger.error(f"接收字节数必须大于0，当前值: {n}")
        return None
        
    # 限制单次接收的最大字节数
    max_size = 50 * 1024 * 1024  # 50MB
    if n > max_size:
        logger.error(f"请求接收的数据块过大: {n} 字节，超过最大限制 {max_size} 字节")
        return None
        
    data = b''
    start_time = time.time()
    max_wait_time = 60  # 最大等待时间为60秒
    
    try:
        while len(data) < n:
            # 检查是否超时
            if time.time() - start_time > max_wait_time:
                logger.warning(f"接收数据超时，已接收 {len(data)}/{n} 字节")
                return None
                
            # 计算剩余需要接收的字节数
            remaining = n - len(data)
            # 一次最多接收8KB，防止大数据块
            packet = sock.recv(min(remaining, 8192))
            
            if not packet:  # 套接字已关闭
                logger.warning("套接字已关闭，无法接收更多数据")
                return None
                
            data += packet
            
        return data
    except (socket.error, ConnectionError) as e:
        logger.error(f"接收数据时出错: {e}")
        return None
    except Exception as e:
        logger.error(f"接收数据时发生未知错误: {e}")
        return None

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
        
        # 标记是否需要关闭套接字
        # 如果消息将被异步处理（创建新线程），则不在此关闭套接字
        should_close_sock = True
        
        if message.msg_type == MessageType.TRANSFER_REQUEST:
            # 处理传输请求
            self._handle_transfer_request(message, client_sock)
        
        elif message.msg_type == MessageType.TRANSFER_ACCEPT:
            # 处理传输接受 - 这将创建新线程处理传输
            self._handle_transfer_accept(message, client_sock)
            # 由传输处理线程负责关闭套接字
            should_close_sock = False
        
        elif message.msg_type == MessageType.TRANSFER_REJECT:
            # 处理传输拒绝
            self._handle_transfer_reject(message)
        
        elif message.msg_type == MessageType.FILE_INFO:
            # 处理文件信息 - 这将创建新线程处理接收
            self._handle_file_info(message, client_sock, client_addr)
            # 由接收线程负责关闭套接字
            should_close_sock = False
        
        elif message.msg_type in [MessageType.PAUSE, MessageType.RESUME, MessageType.CANCEL]:
            # 处理传输控制命令
            self._handle_transfer_control(message)
        
        else:
            # 其他消息类型
            logger.warning(f"未处理的消息类型: {message.msg_type}")
    
    except Exception as e:
        logger.error(f"处理连接 {client_addr} 出错: {e}")
        # 异常情况下总是关闭套接字
        should_close_sock = True
    
    finally:
        # 仅当标记为应该关闭时才关闭套接字
        if should_close_sock:
            try:
                client_sock.close()
                logger.debug(f"已关闭与 {client_addr} 的连接")
            except:
                pass

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
    
    # 记录当前系统状态，特别是目录信息
    logger.info(f"===== 准备接收文件时的系统状态 =====")
    logger.info(f"系统信息:\n{debug_system_info()}")
    
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
    
    # 检查是否为断点续传请求
    resume_offset = file_data.get("resume_offset", 0)
    if resume_offset > 0:
        logger.info(f"收到断点续传请求，从偏移量 {resume_offset} 开始")
        
        # 如果有临时文件，检查它的大小是否与断点位置一致
        temp_file_path = f"{file_info.save_path}.part"
        if os.path.exists(temp_file_path):
            temp_file_size = os.path.getsize(temp_file_path)
            if temp_file_size == resume_offset:
                logger.info(f"断点位置匹配，现有临时文件大小: {temp_file_size}，将继续接收")
            else:
                logger.warning(f"断点位置不匹配，临时文件大小: {temp_file_size}，请求偏移量: {resume_offset}")
                # 决定是否删除临时文件重新开始
                if temp_file_size < resume_offset:
                    logger.warning("临时文件比请求的偏移量小，将删除并重新接收")
                    os.remove(temp_file_path)
                else:
                    # 临时文件大于偏移量，可以截断
                    logger.info(f"将临时文件截断至 {resume_offset} 字节")
                    with open(temp_file_path, 'a+b') as f:
                        f.truncate(resume_offset)
    
    # 确保保存路径存在并且有权限写入
    save_dir = self.default_save_dir
    if not save_dir:
        # 如果默认保存目录未设置，使用用户下载目录
        save_dir = os.path.join(os.path.expanduser("~"), "Downloads", "SendNow")
    
    # 检查和记录保存目录详情
    logger.info(f"准备创建/验证保存目录: {save_dir}")
    logger.info(f"保存目录详细信息:\n{list_directory(os.path.dirname(save_dir))}")
    
    # 创建SendNow子目录
    if not os.path.exists(save_dir):
        try:
            logger.info(f"保存目录不存在，尝试创建: {save_dir}")
            os.makedirs(save_dir, exist_ok=True)
            logger.info(f"保存目录创建成功: {save_dir}")
        except Exception as e:
            logger.error(f"创建保存目录失败: {e}")
            # 尝试使用父目录
            save_dir = os.path.dirname(save_dir)
            logger.info(f"将使用父目录作为保存目录: {save_dir}")

    # 记录创建后的目录状态
    logger.info(f"保存目录状态:\n{list_directory(save_dir)}")
    
    # 确保保存目录是绝对路径
    save_dir = os.path.abspath(save_dir)
    
    # 检查文件名是否合法，替换非法字符
    file_name = file_info.file_name
    file_name = file_name.replace('/', '_').replace('\\', '_').replace(':', '_')
    
    # 构建完整保存路径
    full_save_path = os.path.join(save_dir, file_name)
    logger.info(f"完整保存路径: {full_save_path}")
    
    # 如果文件已存在，添加时间戳避免冲突
    if os.path.exists(full_save_path):
        base_name, extension = os.path.splitext(file_name)
        new_file_name = f"{base_name}_{int(time.time())}{extension}"
        full_save_path = os.path.join(save_dir, new_file_name)
        logger.info(f"文件已存在，将使用新名称: {full_save_path}")
    
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
            full_save_path = os.path.join(temp_dir, file_name)
            logger.info(f"改用临时目录: {temp_dir}, 新保存路径: {full_save_path}")
    except Exception as e:
        logger.error(f"创建保存目录失败: {e}")
        import tempfile
        temp_dir = tempfile.gettempdir()
        full_save_path = os.path.join(temp_dir, file_name)
        logger.info(f"改用临时目录: {temp_dir}, 新保存路径: {full_save_path}")
    
    # 设置文件保存路径
    file_info.save_path = full_save_path
    file_info.file_name = os.path.basename(full_save_path)  # 更新可能已更改的文件名
    # 保存断点续传位置信息
    file_info.resume_offset = resume_offset
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
    elif message.msg_type == MessageType.ERROR:
        # 检查是否是文件头部验证请求
        if message.payload.get("action") == "file_header_verify":
            self._handle_file_header_verify_request(message, addr)
        # 检查是否是文件头部验证响应
        elif message.payload.get("action") == "file_header_verify_response":
            self._handle_file_header_verify_response(message, addr)
        else:
            # 其他类型的错误消息处理
            logger.warning(f"收到错误消息: {message.payload}")
    elif message.msg_type == MessageType.FILE_HEADER_VERIFY:
        # 处理文件头部验证请求
        self._handle_file_header_verify_request(message, addr)
    elif message.msg_type == MessageType.FILE_HEADER_RESPONSE:
        # 处理文件头部验证响应
        self._handle_file_header_verify_response(message, addr)

def _send_file(self, task: TransferTask, client_sock: socket.socket = None):
    """发送文件实现"""
    needs_close = False
    max_retries = 3
    retry_count = 0
    last_successful_offset = 0  # 记录上次成功发送的偏移量，用于断点续传
    
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
        
        # 计算文件哈希值（如果尚未计算），确保使用SHA-256算法
        if not file_info.file_hash:
            logger.info("计算文件哈希值，使用FileInfo.compute_hash方法 (SHA-256)")
            
            # 添加调试信息
            logger.info(f"====== 发送文件详细信息 ======")
            logger.info(f"文件路径: {file_info.file_path}")
            logger.info(f"文件大小: {os.path.getsize(file_info.file_path)} 字节")
            
            # 计算并显示文件的前1024字节的哈希，用于调试
            with open(file_info.file_path, 'rb') as f:
                first_bytes = f.read(1024)
                import hashlib
                first_bytes_hash = hashlib.sha256(first_bytes).hexdigest()
                logger.info(f"发送文件起始部分(1KB)的SHA-256哈希: {first_bytes_hash}")
                # 文件内容的十六进制表示(前100字节)
                hex_content = ' '.join(f'{b:02x}' for b in first_bytes[:100])
                logger.info(f"发送文件起始部分的十六进制表示: {hex_content}")
            
            # 使用FileInfo的compute_hash方法，它会使用SHA-256
            hash_value = file_info.compute_hash()
            logger.info(f"文件哈希值计算完成: {hash_value}")
            
            # 确认哈希值已正确设置
            if not file_info.file_hash or file_info.file_hash != hash_value:
                logger.warning(f"手动设置文件哈希值: {hash_value}")
                file_info.file_hash = hash_value
        
        # 打开文件并发送数据
        file_size = file_info.file_size
        # 限制块大小不超过2MB
        chunk_size = min(file_info.chunk_size, 2 * 1024 * 1024)
        logger.info(f"文件传输将使用 {chunk_size} 字节的数据块大小")
        bytes_sent = 0
        
        # 定义块头部的魔数，用于验证数据完整性
        BLOCK_MAGIC = b'SNFT'  # 'SendNow File Transfer' 的缩写
        
        with open(file_info.file_path, 'rb') as f:
            while bytes_sent < file_size and not task.cancelled:
                # 检查是否暂停
                if task.paused:
                    time.sleep(0.1)
                    continue
                
                # 如果连接断开，尝试重新连接
                if client_sock is None or retry_count > 0:
                    try:
                        # 如果有旧的套接字，尝试关闭
                        if client_sock and needs_close:
                            try:
                                client_sock.close()
                            except:
                                pass
                        
                        logger.info(f"创建新的套接字连接到 {device.ip_address}:{device.port} (重试次数: {retry_count})")
                        client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        client_sock.settimeout(10.0)
                        client_sock.connect((device.ip_address, device.port))
                        needs_close = True
                        
                        # 发送文件信息，包含断点续传的偏移量
                        file_info_dict = file_info.to_dict()
                        file_info_dict["resume_offset"] = bytes_sent  # 添加断点续传信息
                        file_info_message = Message(MessageType.FILE_INFO, {"file_info": file_info_dict})
                        client_sock.sendall(file_info_message.to_bytes())
                        
                        # 等待接收方准备就绪
                        time.sleep(0.5)
                        task.socket = client_sock
                        logger.info(f"套接字重新连接成功，继续从 {bytes_sent} 字节处发送")
                    except Exception as conn_error:
                        logger.error(f"重新连接失败: {conn_error}")
                        if retry_count >= max_retries:
                            raise Exception(f"重试次数已达上限 ({max_retries}), 传输失败")
                        
                        retry_count += 1
                        logger.info(f"等待3秒后尝试第 {retry_count} 次重连...")
                        time.sleep(3)
                        continue
                elif client_sock:
                    # 检查套接字是否仍然有效
                    try:
                        client_sock.getpeername()  # 如果套接字已关闭会抛出异常
                    except Exception as e:
                        logger.warning(f"套接字已断开，尝试重新连接: {e}")
                        client_sock = None
                        retry_count += 1
                        continue
                
                # 重置重试计数器，因为已经成功建立连接
                retry_count = 0
                
                # 定位到文件的当前发送位置
                f.seek(bytes_sent)
                
                # 保留发送前的偏移量，确保使用准确的位置
                current_offset = bytes_sent
                
                # 计算本次发送的大小
                size_to_send = min(chunk_size, file_size - bytes_sent)
                
                # 读取文件块
                chunk = f.read(size_to_send)
                if not chunk:
                    break
                
                try:
                    # 使用固定格式的二进制头部代替JSON
                    # 魔数(4字节) + 块大小(4字节) + 偏移量(8字节) + 传输ID长度(1字节) + 传输ID(变长)
                    transfer_id_bytes = transfer_id.encode('utf-8')
                    transfer_id_len = min(len(transfer_id_bytes), 255)  # 限制ID长度不超过255
                    
                    # 构建头部，使用保存的准确偏移量
                    header = struct.pack(
                        '!4sIQB', 
                        BLOCK_MAGIC,          # 魔数：4字节
                        len(chunk),           # 数据块大小：4字节无符号整数
                        current_offset,       # 偏移量：8字节无符号整数
                        transfer_id_len       # 传输ID长度：1字节
                    ) + transfer_id_bytes[:transfer_id_len]  # 传输ID：变长，最多255字节
                    
                    # 发送数据块头部
                    client_sock.sendall(header)
                    
                    # 打印调试信息
                    logger.debug(f"已发送数据块头部: size={len(chunk)}, offset={current_offset}, ID长度={transfer_id_len}")
                    
                    # 发送数据
                    client_sock.sendall(chunk)
                    
                    # 更新已发送字节数和上次成功位置
                    last_successful_offset = bytes_sent
                    bytes_sent += len(chunk)
                    task.update_progress(bytes_sent)
                    
                    # 发送数据块后
                    logger.debug(f"已发送数据块: {len(chunk)} 字节, 总进度: {bytes_sent}/{file_size}")
                except (socket.error, BrokenPipeError) as e:
                    logger.error(f"发送数据时套接字错误: {e}")
                    if retry_count >= max_retries:
                        logger.error(f"重试次数已达上限 ({max_retries})，传输失败")
                        raise
                    
                    # 准备重连
                    client_sock = None
                    retry_count += 1
                    # 回退到最后一个成功的位置
                    bytes_sent = last_successful_offset
                    logger.info(f"连接断开，将从偏移量 {bytes_sent} 重试 (第 {retry_count} 次)")
                    time.sleep(2)  # 等待一会儿再重试
                    continue
                
                # 控制发送速度，避免网络拥堵
                time.sleep(0.001)
        
        # 发送完成消息
        if not task.cancelled:
            try:
                if client_sock:
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
                logger.error(f"发送完成消息失败: {e}")
                raise
    
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
    save_path = None
    max_retries = 3  # 最大重试次数
    retry_count = 0  # 当前重试次数
    temp_file_path = None
    received_data = bytearray()  # 存储接收到的所有数据
    
    try:
        # 确保传输的目录是固定的，方便排查问题
        fixed_save_dir = os.path.join(os.path.expanduser("~"), "Downloads", "SendNow")
        
        # 确保这个目录存在
        os.makedirs(fixed_save_dir, exist_ok=True)
        
        # 设置文件名 - 使用时间戳作为前缀，避免冲突
        timestamp = int(time.time())
        file_name = f"{timestamp}_{task.file_info.file_name}"
        fixed_save_path = os.path.join(fixed_save_dir, file_name)
        
        # 覆盖原有的保存路径
        task.file_info.save_path = fixed_save_path
        
        # 记录设置的固定保存路径
        logger.info(f"======================================================")
        logger.info(f"文件将保存到固定路径: {fixed_save_path}")
        logger.info(f"======================================================")
        
        # 确认文件信息已设置
        if not task.file_info or not task.file_info.save_path:
            raise ValueError(f"任务{task.transfer_id}的文件信息未设置或保存路径无效")
        
        # 打印完整的任务信息
        logger.info(f"===== 文件接收详细信息 =====")
        logger.info(f"任务ID: {task.transfer_id}")
        logger.info(f"文件名: {task.file_info.file_name}")
        logger.info(f"文件大小: {task.file_info.file_size} 字节")
        logger.info(f"保存路径: {task.file_info.save_path}")
        logger.info(f"文件哈希: {task.file_info.file_hash}")
        logger.info(f"==============================")
        
        # 设置任务状态为正在接收
        task.status = "receiving"
        task.file_info.status = "receiving"
        
        # 确保目标目录存在
        save_path = task.file_info.save_path
        save_dir = os.path.dirname(save_path)
        
        try:
            logger.info(f"尝试创建保存目录: {save_dir}")
            os.makedirs(save_dir, exist_ok=True)
            logger.info(f"保存目录已创建/存在: {save_dir}")
            
            # 验证目录是否确实存在
            if not os.path.exists(save_dir):
                logger.error(f"目录创建失败，路径不存在: {save_dir}")
                raise OSError(f"无法创建目录: {save_dir}")
                
            logger.info(f"检查目录是否可写入: {save_dir}")
            if not os.access(save_dir, os.W_OK):
                logger.error(f"无权限写入目录: {save_dir}")
                raise PermissionError(f"无权限写入: {save_dir}")
            logger.info(f"保存目录可写入: {save_dir}")
        except Exception as e:
            logger.error(f"创建保存目录失败: {e}")
            # 尝试使用临时目录
            import tempfile
            temp_dir = tempfile.gettempdir()
            old_path = save_path
            save_path = os.path.join(temp_dir, os.path.basename(save_path))
            save_dir = temp_dir
            task.file_info.save_path = save_path
            logger.info(f"改用临时目录: {temp_dir}")
            logger.info(f"更新保存路径: {old_path} -> {save_path}")
            
            # 再次尝试创建目录
            os.makedirs(save_dir, exist_ok=True)
            logger.info(f"临时目录已创建/存在: {save_dir}")
        
        # 检查目录写入权限
        if not os.access(save_dir, os.W_OK):
            logger.error(f"无权限写入目录: {save_dir}")
            # 尝试使用临时目录
            import tempfile
            temp_dir = tempfile.gettempdir()
            old_path = save_path
            save_path = os.path.join(temp_dir, os.path.basename(save_path))
            save_dir = temp_dir
            task.file_info.save_path = save_path
            logger.info(f"改用临时目录: {temp_dir}")
            logger.info(f"更新保存路径: {old_path} -> {save_path}")
            
            # 检查临时目录权限
            if not os.access(temp_dir, os.W_OK):
                logger.error(f"无法写入任何目录: {save_dir}, {temp_dir}")
                raise PermissionError(f"无法写入任何目录: {save_dir}, {temp_dir}")
            logger.info(f"临时目录可写入: {temp_dir}")
        
        # 创建临时文件名，用于部分下载
        temp_file_path = f"{save_path}.part"
        logger.info(f"将使用临时文件: {temp_file_path}")
        
        # 获取断点续传位置（如果有）
        resume_offset = getattr(task.file_info, "resume_offset", 0)
        
        # 检查是否存在断点续传信息文件
        resume_info_path = f"{temp_file_path}.resume"
        if os.path.exists(resume_info_path) and (resume_offset == 0):
            try:
                import json
                with open(resume_info_path, 'r') as f:
                    resume_info = json.load(f)
                
                # 验证断点续传信息
                if (resume_info.get("file_name") == task.file_info.file_name and 
                    resume_info.get("file_size") == task.file_info.file_size and 
                    resume_info.get("file_hash") == task.file_info.file_hash):
                    
                    # 验证临时文件大小
                    if os.path.exists(temp_file_path):
                        temp_size = os.path.getsize(temp_file_path)
                        if temp_size == resume_info.get("received_size"):
                            resume_offset = temp_size
                            logger.info(f"发现有效的断点续传信息，从偏移量 {resume_offset} 继续接收")
                            task.file_info.resume_offset = resume_offset
                        else:
                            logger.warning(f"临时文件大小 ({temp_size}) 与断点续传信息 ({resume_info.get('received_size')}) 不匹配")
                else:
                    logger.warning("断点续传信息与当前任务不匹配")
            except Exception as e:
                logger.error(f"读取断点续传信息失败: {e}")
        
        bytes_received = resume_offset
        expected_size = task.file_info.file_size
        last_progress_update = time.time()
        progress_update_interval = 0.5  # 更新间隔，秒
        
        # 检查临时文件是否存在，以及大小是否正确
        file_mode = 'wb'  # 默认为写入模式
        if resume_offset > 0 and os.path.exists(temp_file_path):
            temp_file_size = os.path.getsize(temp_file_path)
            if temp_file_size == resume_offset:
                logger.info(f"发现有效的临时文件，从偏移量 {resume_offset} 继续接收")
                file_mode = 'ab'  # 追加模式
            else:
                logger.warning(f"临时文件大小 ({temp_file_size}) 与断点位置 ({resume_offset}) 不匹配，将重新接收")
                # 默认使用写入模式
        elif resume_offset > 0:
            logger.warning(f"请求从偏移量 {resume_offset} 继续接收，但临时文件不存在，将重新接收")
            # 重置断点位置
            bytes_received = 0
            resume_offset = 0
        
        logger.info(f"正在接收文件数据到临时文件: {temp_file_path}，从位置 {bytes_received} 开始，模式: {file_mode}")
        
        # 打开文件进行写入
        try:
            logger.info(f"尝试打开临时文件进行写入: {temp_file_path}")
            
            # 检查是否需要重新开始接收
            if file_mode == 'wb' and bytes_received > 0:
                # 出现逻辑不一致，重置接收位置
                logger.warning(f"文件模式为wb但bytes_received={bytes_received}，重置为0")
                bytes_received = 0
                task.file_info.resume_offset = 0
            
            # 如果临时文件已存在但内容可能有问题，备份并重新开始
            if os.path.exists(temp_file_path) and file_mode == 'wb':
                backup_path = f"{temp_file_path}.bak.{int(time.time())}"
                logger.info(f"创建临时文件备份: {backup_path}")
                try:
                    import shutil
                    shutil.copy2(temp_file_path, backup_path)
                except Exception as e:
                    logger.error(f"备份临时文件失败: {e}")
            
            with open(temp_file_path, file_mode) as f:
                logger.info(f"成功打开临时文件: {temp_file_path}")
                
                # 如果是追加模式，确保文件指针在正确位置
                if file_mode == 'ab':
                    f.seek(0, 2)  # 移动到文件末尾
                    current_pos = f.tell()
                    logger.info(f"文件指针已移动到末尾(追加模式)，当前位置: {current_pos}")
                    
                    # 检查实际文件大小与断点位置是否一致
                    if current_pos != bytes_received:
                        logger.warning(f"文件当前位置 ({current_pos}) 与断点续传位置 ({bytes_received}) 不一致")
                        if current_pos > bytes_received:
                            logger.warning(f"文件比断点续传位置大，将截断到正确位置")
                            f.truncate(bytes_received)
                        else:
                            logger.warning(f"文件比断点续传位置小，可能丢失数据")
                            # 更新接收位置以匹配实际文件大小
                            bytes_received = current_pos
                
                # 检查实际文件大小
                f.flush()
                os.fsync(f.fileno())
                actual_size = os.path.getsize(temp_file_path)
                logger.info(f"文件初始大小: {actual_size} 字节")
                
                # 接收数据块直到文件接收完成
                while bytes_received < expected_size:
                    # 检查当前的套接字是否有效
                    try:
                        # 如果套接字无效，抛出异常
                        if not client_sock:
                            logger.error("套接字对象为空")
                            raise ConnectionError("套接字为空")
                        
                        # 设置30秒超时并检查套接字状态
                        client_sock.settimeout(30)
                        client_sock.getpeername()  # 如果套接字已关闭会抛出异常
                    except (OSError, AttributeError) as e:
                        # 套接字无效，需要重试
                        logger.warning(f"连接中断: {e}")
                        
                        # 如果超过最大重试次数，则放弃
                        if retry_count >= max_retries:
                            logger.error(f"重试次数已达上限 ({max_retries})，接收失败")
                            raise ConnectionError(f"重试次数已用尽：{e}")
                        
                        # 保存当前进度并尝试重新开始
                        logger.info(f"等待文件传输恢复，已接收 {bytes_received}/{expected_size} 字节")
                        retry_count += 1
                        
                        # 等待一段时间，由发送端重新连接
                        time.sleep(3)
                        continue
                    
                    try:
                        # 定义块头部的魔数，用于验证数据完整性
                        BLOCK_MAGIC = b'SNFT'  # 'SendNow File Transfer' 的缩写
                        
                        # 接收固定长度的头部 (魔数 + 块大小 + 偏移量 + ID长度)
                        fixed_header_size = 4 + 4 + 8 + 1  # 魔数(4) + 块大小(4) + 偏移量(8) + ID长度(1)
                        fixed_header = recv_all(client_sock, fixed_header_size)
                        
                        if not fixed_header or len(fixed_header) < fixed_header_size:
                            logger.error(f"接收头部错误，预期 {fixed_header_size} 字节，收到: {len(fixed_header) if fixed_header else 0} 字节")
                            if retry_count >= max_retries:
                                raise ConnectionError("接收头部错误")
                            
                            retry_count += 1
                            time.sleep(2)
                            continue
                        
                        # 解析固定部分头部
                        magic, chunk_size, offset, id_len = struct.unpack('!4sIQB', fixed_header)
                        
                        # 验证魔数
                        if magic != BLOCK_MAGIC:
                            logger.error(f"数据块魔数不匹配: 预期 {BLOCK_MAGIC}，收到 {magic}")
                            if retry_count >= max_retries:
                                raise ConnectionError(f"数据块魔数不匹配")
                            
                            retry_count += 1
                            time.sleep(2)
                            continue
                        
                        # 读取变长部分（传输ID）
                        if id_len > 0:
                            transfer_id_bytes = recv_all(client_sock, id_len)
                            if not transfer_id_bytes or len(transfer_id_bytes) < id_len:
                                logger.error("接收传输ID错误")
                                if retry_count >= max_retries:
                                    raise ConnectionError("接收传输ID错误")
                                
                                retry_count += 1
                                time.sleep(2)
                                continue
                            
                            # 解码传输ID（仅用于日志）
                            try:
                                block_transfer_id = transfer_id_bytes.decode('utf-8')
                                logger.debug(f"数据块传输ID: {block_transfer_id}")
                            except:
                                logger.warning("无法解码传输ID")
                        
                        # 添加数据块大小合理性检查
                        max_allowed_chunk_size = 10 * 1024 * 1024  # 10MB最大块大小
                        if chunk_size <= 0 or chunk_size > max_allowed_chunk_size:
                            logger.error(f"数据块大小异常: {chunk_size} 字节，超出合理范围 (0-{max_allowed_chunk_size}字节)")
                            if retry_count >= max_retries:
                                raise ConnectionError(f"数据块大小异常: {chunk_size}")
                            
                            retry_count += 1
                            time.sleep(2)
                            continue
                        
                        # 验证偏移量（应该等于已接收的字节数）
                        if offset != bytes_received:
                            logger.warning(f"数据块偏移量不匹配: 预期 {bytes_received}，收到 {offset}")
                            
                            # 检查是否是更新的数据块（偏移量大于当前接收位置）
                            if offset > bytes_received:
                                # 当前位置和数据块偏移量之间有空白，记录警告但不填充零
                                gap_size = offset - bytes_received
                                if gap_size > 10 * 1024 * 1024:  # 超过10MB的缺口认为是错误
                                    logger.error(f"偏移量差异过大 ({gap_size} 字节)，可能是错误数据")
                                    if retry_count >= max_retries:
                                        raise ConnectionError("偏移量差异过大")
                                    retry_count += 1
                                    time.sleep(2)
                                    continue
                                
                                # 记录错误但不再用零填充，可能导致文件损坏
                                logger.error(f"文件传输存在数据缺口 {gap_size} 字节，不再填充零。这可能导致文件损坏。")
                                
                                # 如果有大量数据缺失，可能是传输出现了严重问题
                                if gap_size > 1024 * 1024:  # 超过1MB的缺口
                                    logger.error(f"数据缺口过大，放弃当前传输并重试")
                                    if retry_count >= max_retries:
                                        raise ConnectionError("数据缺口过大")
                                    retry_count += 1
                                    time.sleep(2)
                                    continue
                                    
                                bytes_received = offset  # 更新已接收字节数到当前偏移量
                            elif offset < bytes_received:
                                # 收到了旧数据块，检查是否为重复
                                if offset + chunk_size <= bytes_received:
                                    # 完全重复的数据块，跳过
                                    logger.warning(f"跳过完全重复的数据块: 偏移量={offset}, 大小={chunk_size}")
                                    
                                    # 接收但不处理数据块
                                    dummy_chunk = recv_all(client_sock, chunk_size)
                                    if not dummy_chunk or len(dummy_chunk) < chunk_size:
                                        logger.error("接收重复数据块失败")
                                        if retry_count >= max_retries:
                                            raise ConnectionError("接收重复数据块失败")
                                        retry_count += 1
                                        time.sleep(2)
                                    continue
                                else:
                                    # 部分重叠的数据块，计算新数据的起始位置
                                    overlap = bytes_received - offset
                                    logger.warning(f"数据块部分重叠 {overlap} 字节，调整接收位置")
                                    
                                    # 接收完整数据块
                                    full_chunk = recv_all(client_sock, chunk_size)
                                    if not full_chunk or len(full_chunk) < chunk_size:
                                        logger.error("接收重叠数据块失败")
                                        if retry_count >= max_retries:
                                            raise ConnectionError("接收重叠数据块失败")
                                        retry_count += 1
                                        time.sleep(2)
                                        continue
                                    
                                    # 只使用非重叠部分
                                    chunk = full_chunk[overlap:]
                                    chunk_size = len(chunk)
                                    
                                    # 更新用于日志的偏移量
                                    offset = bytes_received
                        
                        logger.debug(f"成功接收数据块头部，块大小: {chunk_size} 字节，偏移量: {offset}")
                        
                        # 接收数据块
                        if chunk_size > 0:
                            logger.debug(f"开始接收数据块，大小: {chunk_size} 字节")
                            chunk = recv_all(client_sock, chunk_size)
                            if not chunk or len(chunk) < chunk_size:
                                logger.error(f"接收数据块错误，预期大小: {chunk_size}，实际大小: {len(chunk) if chunk else 0}")
                                if retry_count >= max_retries:
                                    raise ConnectionError("接收数据块错误")
                                
                                retry_count += 1
                                time.sleep(2)
                                continue
                            
                            # 重置重试计数器，因为接收成功
                            retry_count = 0
                            
                            # 写入文件 - 增强版本，确保数据确实写入磁盘
                            logger.debug(f"接收到数据块，大小: {len(chunk)} 字节，正在写入文件")
                            
                            try:
                                # 先记录当前文件位置
                                current_pos = f.tell()
                                
                                # 写入数据
                                bytes_written = f.write(chunk)
                                
                                # 立即刷新缓冲区
                                f.flush()
                                
                                # 强制操作系统写入物理介质
                                os.fsync(f.fileno())
                                
                                # 获取新位置
                                new_pos = f.tell()
                                actual_written = new_pos - current_pos
                                
                                # 验证写入是否完整
                                if actual_written != len(chunk):
                                    logger.warning(f"数据块写入不完整: 预期 {len(chunk)} 字节，实际写入 {actual_written} 字节")
                                    
                                    # 检查磁盘剩余空间
                                    import shutil
                                    disk_usage = shutil.disk_usage(os.path.dirname(temp_file_path))
                                    free_space = disk_usage.free
                                    logger.info(f"磁盘剩余空间: {free_space} 字节")
                                    
                                    if free_space < chunk_size * 2:
                                        logger.error("磁盘空间不足，可能导致写入失败")
                                
                                # 安全起见，只计算实际写入的字节数
                                logger.debug(f"实际写入字节数: {actual_written}")
                                bytes_received += actual_written
                                
                                # 将实际写入的数据保存到内存
                                if actual_written == len(chunk):
                                    received_data.extend(chunk)
                                else:
                                    received_data.extend(chunk[:actual_written])
                            except Exception as write_error:
                                logger.error(f"写入文件时出错: {write_error}")
                                logger.error(traceback.format_exc())
                                
                                # 添加更多错误信息
                                import errno
                                if isinstance(write_error, IOError) and write_error.errno == errno.ENOSPC:
                                    logger.error("磁盘空间不足错误")
                                
                                # 尽管写入失败，但我们已经接收了数据，保存到内存
                                received_data.extend(chunk)
                                
                                # 记录接收的字节数，即使写入失败
                                bytes_received += len(chunk)
                                
                                if retry_count >= max_retries:
                                    raise
                                
                                retry_count += 1
                                logger.info(f"写入失败，将在下一次循环中重试 (尝试 {retry_count}/{max_retries})")
                                continue
                            
                            # 更新任务进度
                            task.update_progress(bytes_received)
                            
                            # 更新进度
                            current_time = time.time()
                            if current_time - last_progress_update >= progress_update_interval:
                                # 替换对task.progress的直接引用，改用计算的百分比
                                progress_percent = (bytes_received / expected_size) * 100 if expected_size > 0 else 0
                                last_progress_update = current_time
                                logger.info(f"文件传输进度: {progress_percent:.2f}%，已接收: {bytes_received}/{expected_size} 字节")
                            
                            # 接收数据块后
                            logger.debug(f"已接收数据块: {len(chunk)} 字节, 总进度: {bytes_received}/{expected_size}")
                        else:
                            logger.warning("收到零大小数据块，跳过")
                        
                    except socket.timeout:
                        logger.warning("接收数据超时，尝试等待重新连接")
                        if retry_count >= max_retries:
                            logger.error("接收数据超时次数过多，放弃接收")
                            raise ConnectionError("接收数据超时")
                        
                        retry_count += 1
                        time.sleep(2)
                        continue
                    except Exception as e:
                        logger.error(f"接收数据出错: {e}")
                        if retry_count >= max_retries:
                            raise
                        
                        retry_count += 1
                        time.sleep(2)
                        continue
                
                # 最后一次进度更新，确保显示100%
                task.update_progress(bytes_received)
                logger.info(f"文件接收完成: {task.file_info.file_name}，大小: {bytes_received} 字节")
                logger.info(f"临时文件已完成: {temp_file_path}")
        except PermissionError as e:
            logger.error(f"无权限写入文件: {temp_file_path}, 错误: {e}")
            raise
        except IOError as e:
            logger.error(f"文件I/O错误: {temp_file_path}, 错误: {e}")
            raise
        
        # 验证接收到的数据大小
        logger.info(f"验证接收到的数据大小: 预期 {expected_size}，实际 {bytes_received}")
        
        # 确保文件实际大小与接收字节数匹配
        if os.path.exists(temp_file_path):
            # 重新打开文件以确保所有写入内容已同步
            with open(temp_file_path, 'ab') as f:
                # 刷新所有可能的缓冲区
                f.flush()
                os.fsync(f.fileno())
            
            # 再次读取文件大小
            temp_size = os.path.getsize(temp_file_path)
            logger.info(f"临时文件验证: {temp_file_path}, 大小: {temp_size} 字节")
            
            # 如果文件大小与接收字节数不一致，但我们有完整数据在内存中
            if temp_size != bytes_received and len(received_data) >= bytes_received:
                logger.warning(f"文件大小不匹配：接收了{bytes_received}字节，但文件大小为{temp_size}字节")
                logger.info("尝试从内存缓冲区重新写入文件...")
                
                # 从内存重写文件
                with open(temp_file_path, 'wb') as f:
                    f.write(received_data[:bytes_received])
                    f.flush()
                    os.fsync(f.fileno())
                
                # 再次检查文件大小
                new_size = os.path.getsize(temp_file_path)
                logger.info(f"重写后文件大小: {new_size} 字节")
                
                if new_size == bytes_received:
                    logger.info("文件修复成功，大小现在匹配")
                else:
                    logger.error(f"文件修复失败，大小仍然不匹配：{new_size} vs {bytes_received}")
            
            # 更新bytes_received以匹配实际文件大小
            if temp_size != bytes_received:
                logger.warning(f"调整bytes_received从{bytes_received}到{temp_size}以匹配文件实际大小")
                bytes_received = temp_size
                task.update_progress(bytes_received)
        
        if bytes_received != expected_size:
            logger.error(f"文件大小不匹配: 预期 {expected_size}，实际接收 {bytes_received}")
            task.status = "failed"
            task.error_message = "文件大小不匹配"
            if os.path.exists(temp_file_path):
                # 保存不完整文件以备分析
                incomplete_copy = f"{temp_file_path}.incomplete"
                try:
                    import shutil
                    shutil.copy2(temp_file_path, incomplete_copy)
                    logger.info(f"已保存不完整文件以供分析: {incomplete_copy}")
                except Exception as e:
                    logger.error(f"保存不完整文件副本失败: {e}")
                
                # 删除不完整文件
                os.remove(temp_file_path)
                logger.info(f"删除不完整文件: {temp_file_path}")
            return
        
        # 检查临时文件是否存在和大小是否正确
        if os.path.exists(temp_file_path):
            temp_size = os.path.getsize(temp_file_path)
            logger.info(f"临时文件验证: {temp_file_path}, 大小: {temp_size} 字节")
            if temp_size != expected_size:
                logger.error(f"临时文件大小不匹配: 预期 {expected_size}，实际 {temp_size}")
                # 尝试继续处理
        else:
            logger.error(f"临时文件不存在: {temp_file_path}")
            raise FileNotFoundError(f"临时文件丢失: {temp_file_path}")
        
        # 验证文件哈希(如果有)
        if task.file_info.file_hash:
            try:
                logger.info(f"开始验证文件哈希值: {task.file_info.file_hash}，使用FileInfo.verify_hash方法")
                
                # 添加调试信息
                logger.info(f"====== 文件详细信息 ======")
                logger.info(f"临时文件路径: {temp_file_path}")
                logger.info(f"文件大小: {os.path.getsize(temp_file_path)} 字节")
                
                # 检查文件是否为空或包含全零数据
                with open(temp_file_path, 'rb') as check_f:
                    first_block = check_f.read(8192)
                    if not first_block or all(b == 0 for b in first_block):
                        logger.error("文件内容异常：文件起始部分全为空或零")
                        
                        # 如果文件前面是全零，尝试查找非零起始位置
                        logger.info("尝试检测文件中非零数据的起始位置...")
                        check_f.seek(0)
                        position = 0
                        while True:
                            block = check_f.read(8192)
                            if not block:
                                break
                                
                            for i, byte in enumerate(block):
                                if byte != 0:
                                    position = position + i
                                    logger.info(f"在偏移量 {position} 处找到非零数据")
                                    check_f.seek(position)
                                    nonzero_block = check_f.read(100)
                                    hex_content = ' '.join(f'{b:02x}' for b in nonzero_block)
                                    logger.info(f"非零数据的十六进制表示: {hex_content}")
                                    
                                    # 退出所有循环
                                    break
                            else:
                                position += len(block)
                                continue
                            break
                
                # 计算并显示文件的前1024字节的哈希，用于调试
                with open(temp_file_path, 'rb') as f:
                    first_bytes = f.read(1024)
                    import hashlib
                    first_bytes_hash = hashlib.sha256(first_bytes).hexdigest()
                    logger.info(f"文件起始部分(1KB)的SHA-256哈希: {first_bytes_hash}")
                    # 文件内容的十六进制表示(前100字节)
                    hex_content = ' '.join(f'{b:02x}' for b in first_bytes[:100])
                    logger.info(f"文件起始部分的十六进制表示: {hex_content}")
                
                # 创建临时的FileInfo对象用于验证
                from transfer import FileInfo
                temp_file_info = FileInfo(file_path=temp_file_path)
                temp_file_info.file_hash = task.file_info.file_hash
                
                # 使用FileInfo的verify_hash方法验证
                is_valid = temp_file_info.verify_hash(temp_file_path)
                
                if not is_valid:
                    logger.error(f"文件哈希不匹配: 预期 {task.file_info.file_hash}")
                    # 重新计算哈希并记录，用于调试
                    calculated_hash = temp_file_info.calculate_file_hash(temp_file_path)
                    logger.error(f"计算得到的哈希值: {calculated_hash}")
                    
                    # 请求发送方提供文件头部信息以帮助诊断
                    self._request_file_header_verification(task, calculated_hash)
                    
                    # 尝试与发送端沟通，了解实际文件大小和文件头信息
                    logger.info("文件可能已损坏。请让发送方确认文件头部内容以帮助诊断问题。")
                    task.status = "failed"
                    task.error_message = "文件哈希不匹配"
                    
                    # 调试用：保留不匹配的文件以供分析
                    mismatch_debug_path = f"{temp_file_path}.mismatch"
                    try:
                        import shutil
                        shutil.copy2(temp_file_path, mismatch_debug_path)
                        logger.info(f"已保存不匹配的文件副本用于调试: {mismatch_debug_path}")
                    except Exception as e:
                        logger.error(f"保存调试文件失败: {e}")
                    
                    os.remove(temp_file_path)  # 删除不完整文件
                    return
                logger.info("文件哈希验证通过")
            except Exception as e:
                logger.error(f"计算文件哈希值出错: {e}")
                logger.error(traceback.format_exc())
                # 继续处理，不因哈希计算失败而中断
        
        # 将临时文件重命名为最终文件
        try:
            # 确保目标目录存在
            final_dir = os.path.dirname(save_path)
            if not os.path.exists(final_dir):
                os.makedirs(final_dir, exist_ok=True)
                logger.info(f"创建目标目录: {final_dir}")

            # 如果目标文件已存在，先删除
            if os.path.exists(save_path):
                logger.info(f"目标文件已存在，正在删除: {save_path}")
                os.remove(save_path)
            
            logger.info(f"将临时文件重命名为最终文件: {temp_file_path} -> {save_path}")
            # 确保文件系统操作完成
            os.fsync(os.open(os.path.dirname(temp_file_path), os.O_RDONLY))
            os.rename(temp_file_path, save_path)
            # 再次确保文件系统操作完成
            os.fsync(os.open(os.path.dirname(save_path), os.O_RDONLY))
            logger.info(f"文件保存成功: {save_path}")
            
            # 验证最终文件是否存在及大小是否正确
            if os.path.exists(save_path):
                final_size = os.path.getsize(save_path)
                logger.info(f"最终文件验证: 大小 {final_size} 字节")
                if final_size != expected_size:
                    logger.error(f"最终文件大小不匹配: 预期 {expected_size}，实际 {final_size}")
            else:
                logger.error(f"最终文件不存在: {save_path}")
                raise FileNotFoundError(f"无法找到最终文件: {save_path}")
        except Exception as e:
            logger.error(f"重命名临时文件失败: {e}")
            logger.error(traceback.format_exc())
            
            # 尝试用复制方式替代重命名
            try:
                logger.info(f"尝试通过复制方式创建最终文件: {temp_file_path} -> {save_path}")
                shutil.copy2(temp_file_path, save_path)
                logger.info(f"文件复制成功: {save_path}")
                
                # 删除临时文件
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)
                    logger.info(f"临时文件已删除: {temp_file_path}")
            except Exception as copy_error:
                logger.error(f"复制文件失败: {copy_error}")
                raise
        
        # 发送完成确认消息
        try:
            self._send_transfer_complete(task)
            logger.info("已发送完成确认消息")
        except Exception as e:
            logger.warning(f"发送完成确认消息失败: {e}")
            # 继续执行，不影响本地文件保存
        
        # 最终验证 - 再次确认文件存在
        if os.path.exists(save_path):
            final_size = os.path.getsize(save_path)
            logger.info(f"最终文件验证: {save_path}, 大小: {final_size} 字节")
        else:
            logger.error(f"最终文件不存在: {save_path}")
            
            # 如果文件不存在但我们有完整数据，尝试保存
            if received_data and len(received_data) == expected_size:
                logger.info(f"尝试从内存中恢复文件")
                
                try:
                    # 尝试保存到下载目录
                    downloads_dir = os.path.join(os.path.expanduser("~"), "Downloads")
                    backup_path = os.path.join(downloads_dir, f"BACKUP_{os.path.basename(save_path)}")
                    
                    # 写入数据
                    with open(backup_path, 'wb') as f:
                        f.write(received_data)
                        f.flush()
                        os.fsync(f.fileno())
                    
                    logger.info(f"已创建备份文件: {backup_path}, 大小: {len(received_data)} 字节")
                    
                    # 再次尝试保存到原路径
                    try:
                        shutil.copy2(backup_path, save_path)
                        logger.info(f"已将备份复制到最终位置: {save_path}")
                    except Exception as e:
                        logger.error(f"无法复制备份到最终位置: {e}")
                except Exception as e:
                    logger.error(f"从内存保存文件失败: {e}")
        
        # 更新任务状态为完成
        task.status = "completed"
        task.file_info.status = "completed"
        task.end_time = time.time()
        logger.info(f"文件接收任务完成: {task.file_info.file_name}")
        
        # 放置在日志中醒目的位置
        logger.info("="*50)
        logger.info(f"文件已保存到: {save_path}")
        logger.info("="*50)
        
        # 关闭连接
        if client_sock:
            try:
                client_sock.close()
                logger.info("客户端连接已关闭")
            except Exception as e:
                logger.warning(f"关闭客户端连接时出错: {e}")
        
    except ConnectionError as e:
        logger.error(f"连接错误: {e}")
        task.status = "failed"
        task.file_info.status = "failed"
        task.error_message = f"连接错误: {str(e)}"
    except Exception as e:
        logger.error(f"接收文件出错: {e}")
        logger.error(traceback.format_exc())
        task.status = "failed"
        task.file_info.status = "failed"
        task.error_message = f"接收文件出错: {str(e)}"
    finally:
        # 不调用不存在的方法，直接更新状态
        task.file_info.status = task.status
        
        # 关闭套接字
        try:
            if client_sock:
                client_sock.close()
                logger.debug("已关闭接收用套接字")
        except Exception as e:
            logger.debug(f"关闭套接字时出错: {e}")
        
        # 如果任务失败且临时文件仍存在，保留它用于断点续传
        if (task.status == "failed" and temp_file_path and 
                os.path.exists(temp_file_path)):
            try:
                # 获取当前临时文件的大小
                temp_size = os.path.getsize(temp_file_path)
                if temp_size > 0:
                    logger.info(f"保留不完整的临时文件用于断点续传: {temp_file_path}, 已接收: {temp_size} 字节")
                    
                    # 保存断点续传信息
                    resume_info_path = f"{temp_file_path}.resume"
                    with open(resume_info_path, 'w') as f:
                        import json
                        json.dump({
                            "file_name": task.file_info.file_name,
                            "file_size": task.file_info.file_size,
                            "file_hash": task.file_info.file_hash,
                            "received_size": temp_size,
                            "transfer_id": task.transfer_id,
                            "timestamp": time.time()
                        }, f)
                    logger.info(f"已保存断点续传信息: {resume_info_path}")
                else:
                    # 如果文件大小为0，删除它
                    os.remove(temp_file_path)
                    logger.info(f"已删除空的临时文件: {temp_file_path}")
            except Exception as e:
                logger.error(f"处理不完整临时文件时出错: {e}")
                try:
                    # 出错时保险起见不删除临时文件
                    logger.info(f"保留不完整的临时文件: {temp_file_path}")
                except:
                    pass
        
        # 从接收线程列表中移除
        if task.transfer_id in self.receiver_threads:
            del self.receiver_threads[task.transfer_id]

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

def _send_transfer_complete(self, task: TransferTask):
    """发送传输完成消息给对方"""
    try:
        # 构建完成消息
        complete_message = {
            "transfer_id": task.transfer_id,
            "completed": True,
            "file_id": task.file_info.file_id,
            "file_hash": task.file_info.file_hash
        }
        
        # 创建完成消息
        message = Message(MessageType.COMPLETE, complete_message)
        
        # 尝试发送
        if task.device:
            self.network_manager.send_message(task.device, message)
            logger.info(f"已发送传输完成确认消息: {task.file_info.file_name}")
        else:
            logger.warning(f"无法发送完成消息：设备信息缺失")
            
    except Exception as e:
        logger.error(f"发送完成消息失败: {e}")
        # 这不影响本地文件的完成状态

def _request_file_header_verification(self, task: TransferTask, calculated_hash: str):
    """
    请求发送方提供文件头部内容以进行验证和诊断
    
    Args:
        task: 传输任务
        calculated_hash: 接收方计算出的文件哈希值
    """
    if not task or not task.device:
        logger.error("无法请求文件头部验证：任务信息不完整")
        return
        
    try:
        # 创建请求头部内容的消息
        request_payload = {
            "transfer_id": task.transfer_id,
            "file_id": task.file_info.file_id,
            "action": "file_header_verify",
            "calculated_hash": calculated_hash,
            "expected_hash": task.file_info.file_hash
        }
        
        # 使用专门的消息类型
        verify_message = Message(MessageType.FILE_HEADER_VERIFY, request_payload)
        
        # 发送请求
        logger.info(f"正在向发送方请求文件头部诊断数据: {task.device.device_name}")
        self.network_manager.send_message(task.device, verify_message)
        
        # 记录请求已发送
        logger.info(f"已发送文件头部诊断请求，等待发送方回应")
    except Exception as e:
        logger.error(f"发送文件头部验证请求失败: {e}")
        import traceback
        logger.error(traceback.format_exc())

def _handle_file_header_verify_request(self, message: Message, addr: Tuple[str, int]):
    """
    处理文件头部验证请求
    
    Args:
        message: 请求消息
        addr: 发送方地址
    """
    payload = message.payload
    transfer_id = payload.get("transfer_id")
    file_id = payload.get("file_id")
    calculated_hash = payload.get("calculated_hash")
    expected_hash = payload.get("expected_hash")
    
    if not transfer_id or not file_id:
        logger.error("无效的文件头部验证请求: 缺少必要参数")
        return
        
    # 在发送任务中查找对应的文件
    task = self.send_tasks.get(transfer_id)
    if not task:
        logger.error(f"找不到对应的发送任务: {transfer_id}")
        return
        
    if task.file_info.file_id != file_id:
        logger.error(f"文件ID不匹配: 预期 {task.file_info.file_id}, 收到 {file_id}")
        return
        
    try:
        # 获取文件头部信息用于诊断
        file_path = task.file_info.file_path
        if not file_path or not os.path.exists(file_path):
            logger.error(f"源文件不存在: {file_path}")
            return
            
        # 读取文件头部(前8KB)用于诊断
        with open(file_path, 'rb') as f:
            header_data = f.read(8192)  # 读取前8KB
            
            # 计算头部的哈希值
            header_hash = hashlib.sha256(header_data).hexdigest()
            
            # 显示头部的十六进制表示(前256字节)
            hex_header = ' '.join(f'{b:02x}' for b in header_data[:256])
            
            # 获取文件基本信息
            file_size = os.path.getsize(file_path)
            
            # 创建响应消息
            response_payload = {
                "transfer_id": transfer_id,
                "file_id": file_id,
                "action": "file_header_verify_response",
                "source_size": file_size,
                "header_hash": header_hash,
                "header_hex": hex_header,
                "file_hash": task.file_info.file_hash
            }
            
            # 使用专门的消息类型
            response_message = Message(MessageType.FILE_HEADER_RESPONSE, response_payload)
            
            # 创建用于回应的设备信息
            from network import DeviceInfo
            recipient_device = DeviceInfo(
                device_id="temp_id",
                device_name="接收方",
                ip_address=addr[0],
                port=addr[1]
            )
            
            # 发送响应
            logger.info(f"正在发送文件头部诊断数据到: {addr[0]}:{addr[1]}")
            logger.info(f"文件大小: {file_size} 字节")
            logger.info(f"头部哈希: {header_hash}")
            logger.info(f"头部十六进制(部分): {hex_header[:100]}...")
            
            # 发送响应
            self.network_manager.send_message(recipient_device, response_message)
            logger.info("文件头部诊断数据已发送")
    except Exception as e:
        logger.error(f"处理文件头部验证请求失败: {e}")
        import traceback
        logger.error(traceback.format_exc())

def _handle_file_header_verify_response(self, message: Message, addr: Tuple[str, int]):
    """
    处理接收到的文件头部验证响应
    
    Args:
        message: 响应消息
        addr: 发送方地址
    """
    payload = message.payload
    transfer_id = payload.get("transfer_id")
    file_id = payload.get("file_id")
    source_size = payload.get("source_size")
    header_hash = payload.get("header_hash")
    header_hex = payload.get("header_hex")
    file_hash = payload.get("file_hash")
    
    if not transfer_id or not file_id:
        logger.error("无效的文件头部验证响应: 缺少必要参数")
        return
    
    # 在接收任务中查找对应的文件
    task = self.receive_tasks.get(transfer_id)
    if not task:
        logger.error(f"找不到对应的接收任务: {transfer_id}")
        return
    
    # 记录诊断信息
    logger.info("=" * 50)
    logger.info("收到文件头部诊断响应")
    logger.info(f"传输ID: {transfer_id}")
    logger.info(f"文件ID: {file_id}")
    logger.info(f"源文件大小: {source_size} 字节")
    logger.info(f"头部哈希: {header_hash}")
    logger.info(f"文件哈希: {file_hash}")
    logger.info(f"头部十六进制(部分): {header_hex[:100]}...")
    
    # 对比本地接收的文件
    # 如果存在保存的不匹配文件，读取其头部进行对比
    mismatch_debug_path = f"{task.file_info.save_path}.mismatch"
    if os.path.exists(mismatch_debug_path):
        try:
            with open(mismatch_debug_path, 'rb') as f:
                local_header = f.read(8192)  # 读取相同大小的头部
                local_header_hash = hashlib.sha256(local_header).hexdigest()
                local_header_hex = ' '.join(f'{b:02x}' for b in local_header[:256])
                
                logger.info("本地接收文件头部信息:")
                logger.info(f"本地头部哈希: {local_header_hash}")
                logger.info(f"本地头部十六进制(部分): {local_header_hex[:100]}...")
                
                # 对比头部哈希
                if header_hash != local_header_hash:
                    logger.error("文件头部哈希不匹配，文件传输可能存在问题")
                    # 查找头部差异的位置
                    min_len = min(len(local_header), len(header_hex.split()))
                    for i in range(min_len):
                        remote_byte = int(header_hex.split()[i], 16) if i < len(header_hex.split()) else None
                        local_byte = local_header[i] if i < len(local_header) else None
                        
                        if remote_byte != local_byte:
                            logger.error(f"在位置 {i} 处发现差异: 源文件={remote_byte:02x}, 本地文件={local_byte:02x}")
                            # 只报告前10个差异
                            if i >= 10:
                                logger.error("差异过多，停止报告")
                                break
                else:
                    logger.info("文件头部哈希匹配，可能是传输过程中后续部分出现问题")
        except Exception as e:
            logger.error(f"分析本地文件时出错: {e}")
    else:
        logger.warning(f"找不到本地不匹配文件副本: {mismatch_debug_path}")
    
    logger.info("=" * 50)
    logger.info("诊断结论: 请检查网络连接质量，可能由于网络原因导致文件传输过程中数据损坏")
    logger.info("建议尝试重新传输文件或使用更可靠的网络连接")
    logger.info("=" * 50)

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
setattr(TransferManager, "_send_transfer_complete", _send_transfer_complete)

# 添加新增的诊断方法注册
setattr(TransferManager, "_request_file_header_verification", _request_file_header_verification)
setattr(TransferManager, "_handle_file_header_verify_request", _handle_file_header_verify_request)
setattr(TransferManager, "_handle_file_header_verify_response", _handle_file_header_verify_response) 