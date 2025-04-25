import os
import time
import hashlib
import threading
import logging
import socket
import json
from queue import Queue
from typing import Dict, List, Tuple, Optional, Callable, Any, Set

from network import NetworkManager, Message, MessageType, DeviceInfo, BUFFER_SIZE, TRANSFER_PORT

# 配置日志
logger = logging.getLogger("SendNow.Transfer")

class FileInfo:
    """文件信息类，用于传输过程中的文件元数据"""
    
    def __init__(self, file_path: str = None, file_id: str = None, file_name: str = None, 
                 file_size: int = 0, file_hash: str = None):
        self.file_id = file_id or hashlib.md5(f"{time.time()}_{file_path or file_name}".encode()).hexdigest()[:16]
        self.file_path = file_path  # 本地文件路径（发送方）
        self.file_name = file_name or (os.path.basename(file_path) if file_path else "未命名文件")
        self.file_size = file_size or (os.path.getsize(file_path) if file_path and os.path.exists(file_path) else 0)
        self.file_hash = file_hash  # 文件完整性校验（可选）
        self.transfer_id = None     # 传输会话ID
        self.save_path = None       # 保存路径（接收方）
        self.transferred = 0        # 已传输字节数
        self.chunk_size = 1024 * 64  # 传输块大小，默认64KB
        self.status = "pending"     # 状态：pending, transferring, paused, completed, failed, cancelled
        self.last_update = time.time()  # 最后更新时间
    
    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "file_id": self.file_id,
            "file_name": self.file_name,
            "file_size": self.file_size,
            "file_hash": self.file_hash,
            "transfer_id": self.transfer_id,
            "chunk_size": self.chunk_size,
            "status": self.status
        }
    
    @staticmethod
    def from_dict(data: dict) -> 'FileInfo':
        """从字典创建文件信息对象"""
        file_info = FileInfo(
            file_id=data.get("file_id"),
            file_name=data.get("file_name"),
            file_size=data.get("file_size", 0),
            file_hash=data.get("file_hash")
        )
        file_info.transfer_id = data.get("transfer_id")
        file_info.chunk_size = data.get("chunk_size", 1024 * 64)
        file_info.status = data.get("status", "pending")
        return file_info
    
    def get_progress(self) -> float:
        """获取传输进度百分比"""
        if self.file_size == 0:
            return 0.0
        return min(100.0, (self.transferred / self.file_size) * 100)
    
    def get_speed(self, elapsed_time: float) -> float:
        """计算传输速度 (bytes/s)"""
        if elapsed_time <= 0:
            return 0.0
        return self.transferred / elapsed_time
    
    def calculate_hash(self) -> str:
        """计算文件的哈希值，用于完整性校验"""
        if not self.file_path or not os.path.exists(self.file_path):
            return ""
        
        hasher = hashlib.md5()
        with open(self.file_path, 'rb') as f:
            # 读取文件的块并更新哈希
            buf = f.read(8192)
            while buf:
                hasher.update(buf)
                buf = f.read(8192)
        
        self.file_hash = hasher.hexdigest()
        return self.file_hash
    
    def verify_hash(self, file_path: str = None) -> bool:
        """验证文件的完整性"""
        if not self.file_hash:
            logger.warning("无法验证文件 - 没有哈希值")
            return False
        
        path = file_path or self.save_path
        if not path or not os.path.exists(path):
            logger.error(f"文件不存在: {path}")
            return False
        
        hasher = hashlib.md5()
        with open(path, 'rb') as f:
            buf = f.read(8192)
            while buf:
                hasher.update(buf)
                buf = f.read(8192)
        
        calculated_hash = hasher.hexdigest()
        is_valid = calculated_hash == self.file_hash
        
        if not is_valid:
            logger.warning(f"文件哈希不匹配: 预期={self.file_hash}, 实际={calculated_hash}")
        
        return is_valid
    
    def __str__(self) -> str:
        return f"{self.file_name} ({self.get_formatted_size()}) - {self.status} {self.get_progress():.1f}%"
    
    def get_formatted_size(self) -> str:
        """获取格式化的文件大小"""
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"

class TransferTask:
    """传输任务类，管理单个文件的传输"""
    
    def __init__(self, file_info: FileInfo, device: DeviceInfo, is_sender: bool):
        self.file_info = file_info
        self.device = device
        self.is_sender = is_sender  # True=发送方，False=接收方
        self.transfer_id = file_info.transfer_id or hashlib.md5(f"{device.device_id}_{file_info.file_id}_{time.time()}".encode()).hexdigest()[:16]
        self.file_info.transfer_id = self.transfer_id
        
        # 传输状态
        self.status = "pending"  # pending, transferring, paused, completed, failed, cancelled
        self.start_time = None
        self.end_time = None
        self.socket = None
        self.paused = False
        self.cancelled = False
        
        # 进度跟踪
        self.total_chunks = self._calculate_total_chunks()
        self.current_chunk = 0
        self.last_update_time = time.time()
        self.last_bytes = 0
        self.current_speed = 0  # bytes/s
        
        # 回调函数
        self.on_progress: Optional[Callable[[FileInfo, float, float], None]] = None
        self.on_complete: Optional[Callable[[FileInfo, bool], None]] = None
        self.on_error: Optional[Callable[[FileInfo, str], None]] = None
    
    def _calculate_total_chunks(self) -> int:
        """计算文件需要的总块数"""
        if self.file_info.file_size == 0:
            return 0
        chunks = self.file_info.file_size // self.file_info.chunk_size
        if self.file_info.file_size % self.file_info.chunk_size > 0:
            chunks += 1
        return chunks
    
    def update_progress(self, bytes_transferred: int):
        """更新传输进度"""
        self.file_info.transferred = bytes_transferred
        self.current_chunk = bytes_transferred // self.file_info.chunk_size
        
        # 更新速度计算
        current_time = time.time()
        time_diff = current_time - self.last_update_time
        
        if time_diff >= 1.0:  # 每秒至少更新一次
            bytes_diff = bytes_transferred - self.last_bytes
            self.current_speed = bytes_diff / time_diff
            self.last_bytes = bytes_transferred
            self.last_update_time = current_time
            
            # 触发进度回调
            if self.on_progress:
                progress = self.file_info.get_progress()
                self.on_progress(self.file_info, progress, self.current_speed)
    
    def get_formatted_speed(self) -> str:
        """获取格式化的传输速度"""
        speed = self.current_speed
        for unit in ['B/s', 'KB/s', 'MB/s', 'GB/s']:
            if speed < 1024.0:
                return f"{speed:.1f} {unit}"
            speed /= 1024.0
        return f"{speed:.1f} TB/s"
    
    def get_estimated_time(self) -> int:
        """获取估计的剩余时间（秒）"""
        if self.current_speed <= 0:
            return -1  # 无法估计
        
        remaining_bytes = self.file_info.file_size - self.file_info.transferred
        return int(remaining_bytes / self.current_speed)
    
    def get_formatted_remaining_time(self) -> str:
        """获取格式化的估计剩余时间"""
        seconds = self.get_estimated_time()
        if seconds < 0:
            return "计算中..."
        
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        
        if hours > 0:
            return f"{hours}小时{minutes}分钟"
        elif minutes > 0:
            return f"{minutes}分钟{seconds}秒"
        else:
            return f"{seconds}秒"

class TransferManager:
    """传输管理器，处理文件传输任务"""
    
    def __init__(self, network_manager: NetworkManager, default_save_dir: str = None):
        self.network_manager = network_manager
        self.default_save_dir = default_save_dir or os.path.join(os.path.expanduser("~"), "Downloads", "SendNow")
        
        # 确保保存目录存在
        os.makedirs(self.default_save_dir, exist_ok=True)
        
        # 传输任务管理
        self.send_tasks: Dict[str, TransferTask] = {}  # 发送任务，键为transfer_id
        self.receive_tasks: Dict[str, TransferTask] = {}  # 接收任务，键为transfer_id
        self.pending_transfers: Dict[str, FileInfo] = {}  # 等待确认的传输请求，键为transfer_id
        
        # 传输服务器线程
        self.transfer_server_thread = None
        self.running = False
        
        # 文件发送和接收线程池
        self.sender_threads: Dict[str, threading.Thread] = {}
        self.receiver_threads: Dict[str, threading.Thread] = {}
        
        # 回调函数
        self.on_transfer_request: Optional[Callable[[DeviceInfo, List[FileInfo]], bool]] = None
        self.on_file_progress: Optional[Callable[[FileInfo, float, float], None]] = None
        self.on_transfer_complete: Optional[Callable[[FileInfo, bool], None]] = None
        self.on_transfer_error: Optional[Callable[[FileInfo, str], None]] = None
        
        logger.info(f"初始化传输管理器，默认保存目录: {self.default_save_dir}")
    
    def start(self):
        """启动传输管理器"""
        if self.running:
            logger.warning("传输管理器已经在运行")
            return
        
        self.running = True
        
        # 启动传输服务器线程，用于监听传入的传输请求
        self.transfer_server_thread = threading.Thread(target=self._transfer_server_loop)
        self.transfer_server_thread.daemon = True
        self.transfer_server_thread.start()
        
        # 注册网络消息处理回调
        self.network_manager.on_message_received = self._handle_network_message
        
        logger.info("传输管理器已启动")
    
    def stop(self):
        """停止传输管理器"""
        if not self.running:
            return
        
        self.running = False
        
        # 取消所有传输任务
        for task in list(self.send_tasks.values()):
            self.cancel_transfer(task.transfer_id)
        
        for task in list(self.receive_tasks.values()):
            self.cancel_transfer(task.transfer_id)
        
        # 等待服务器线程结束
        if self.transfer_server_thread:
            self.transfer_server_thread.join(1.0)
        
        logger.info("传输管理器已停止")
    
    def set_save_directory(self, directory: str):
        """设置默认保存目录"""
        if os.path.isdir(directory):
            self.default_save_dir = directory
            os.makedirs(self.default_save_dir, exist_ok=True)
            logger.info(f"设置默认保存目录: {self.default_save_dir}")
            return True
        else:
            logger.error(f"无效的目录路径: {directory}")
            return False
            
    def send_files(self, device: DeviceInfo, file_paths: List[str]) -> List[str]:
        """发送文件到指定设备
        
        参数:
            device: 目标设备
            file_paths: 文件路径列表
            
        返回:
            List[str]: 传输ID列表
        """
        if not file_paths or not device:
            logger.warning("文件路径列表为空或设备无效")
            return []
        
        # 检查文件是否存在
        valid_paths = []
        for path in file_paths:
            if not os.path.isfile(path):
                logger.warning(f"文件不存在: {path}")
                continue
            valid_paths.append(path)
        
        if not valid_paths:
            logger.warning("没有有效的文件路径")
            return []
        
        # 创建文件信息对象
        file_infos = []
        for path in valid_paths:
            file_info = FileInfo(file_path=path)
            # 可选: 计算文件哈希用于完整性校验
            # file_info.calculate_hash()
            file_infos.append(file_info)
        
        # 发送传输请求
        transfer_request_payload = {
            "sender": {
                "device_id": self.network_manager.device_id,
                "device_name": self.network_manager.device_name,
                "ip_address": self.network_manager.host_ip,
                "port": TRANSFER_PORT
            },
            "files": [info.to_dict() for info in file_infos]
        }
        
        transfer_request = Message(MessageType.TRANSFER_REQUEST, transfer_request_payload)
        success = self.network_manager.send_message(device, transfer_request)
        
        if not success:
            logger.error(f"发送传输请求失败: {device.device_name}")
            return []
        
        # 创建传输任务
        transfer_ids = []
        for file_info in file_infos:
            task = TransferTask(file_info, device, is_sender=True)
            transfer_id = task.transfer_id
            
            # 设置回调
            task.on_progress = self.on_file_progress
            task.on_complete = self.on_transfer_complete
            task.on_error = self.on_transfer_error
            
            # 添加到任务队列
            self.send_tasks[transfer_id] = task
            transfer_ids.append(transfer_id)
            
            logger.info(f"创建发送任务: {file_info.file_name} -> {device.device_name}, ID={transfer_id}")
        
        return transfer_ids
    
    def accept_transfer(self, transfer_id: str, save_dir: str = None) -> bool:
        """接受传输请求"""
        # 获取对应的文件信息
        file_info = self.pending_transfers.get(transfer_id)
        if not file_info:
            logger.error(f"找不到传输请求: {transfer_id}")
            return False
        
        # 设置保存路径
        directory = save_dir or self.default_save_dir
        os.makedirs(directory, exist_ok=True)
        file_info.save_path = os.path.join(directory, file_info.file_name)
        
        # 检查是否已存在同名文件，如果存在则修改文件名
        counter = 1
        original_path = file_info.save_path
        while os.path.exists(file_info.save_path):
            name, ext = os.path.splitext(file_info.file_name)
            file_info.save_path = os.path.join(directory, f"{name} ({counter}){ext}")
            counter += 1
        
        # 发送接受传输的响应
        sender_id = transfer_id.split('_')[0]  # transfer_id格式为 "sender_id_file_id"
        sender_device = None
        for device in self.network_manager.get_devices():
            if device.device_id == sender_id:
                sender_device = device
                break
        
        if not sender_device:
            logger.error(f"找不到发送方设备，ID={sender_id}")
            return False
        
        # 发送接受传输的消息
        response = {
            "transfer_id": transfer_id,
            "accepted": True,
            "receiver_id": self.network_manager.device_id,
            "save_path": file_info.save_path
        }
        
        message = Message(MessageType.TRANSFER_ACCEPT, response)
        success = self.network_manager.send_message(sender_device, message)
        
        if not success:
            logger.error(f"发送传输接受响应失败: {transfer_id}")
            return False
        
        # 创建接收任务
        task = TransferTask(file_info, sender_device, is_sender=False)
        task.on_progress = self._on_file_progress
        task.on_complete = self._on_file_complete
        task.on_error = self._on_file_error
        self.receive_tasks[transfer_id] = task
        
        # 从待处理列表中移除
        del self.pending_transfers[transfer_id]
        
        logger.info(f"接受传输请求: {transfer_id}, 保存到 {file_info.save_path}")
        return True
    
    def reject_transfer(self, transfer_id: str, reason: str = "拒绝传输") -> bool:
        """拒绝传输请求"""
        # 获取对应的文件信息
        file_info = self.pending_transfers.get(transfer_id)
        if not file_info:
            logger.error(f"找不到传输请求: {transfer_id}")
            return False
        
        # 发送拒绝传输的响应
        sender_id = transfer_id.split('_')[0]  # transfer_id格式为 "sender_id_file_id"
        sender_device = None
        for device in self.network_manager.get_devices():
            if device.device_id == sender_id:
                sender_device = device
                break
        
        if not sender_device:
            logger.error(f"找不到发送方设备，ID={sender_id}")
            return False
        
        # 发送拒绝传输的消息
        response = {
            "transfer_id": transfer_id,
            "accepted": False,
            "reason": reason
        }
        
        message = Message(MessageType.TRANSFER_REJECT, response)
        success = self.network_manager.send_message(sender_device, message)
        
        # 从待处理列表中移除
        del self.pending_transfers[transfer_id]
        
        logger.info(f"拒绝传输请求: {transfer_id}, 原因: {reason}")
        return success
    
    def pause_transfer(self, transfer_id: str) -> bool:
        """暂停传输"""
        # 查找对应的传输任务
        task = self.send_tasks.get(transfer_id) or self.receive_tasks.get(transfer_id)
        if not task:
            logger.error(f"找不到传输任务: {transfer_id}")
            return False
        
        # 更新状态
        task.paused = True
        task.file_info.status = "paused"
        
        # 如果是发送方，则发送暂停消息
        if task.is_sender:
            pause_message = {
                "transfer_id": transfer_id,
                "action": "pause"
            }
            message = Message(MessageType.PAUSE, pause_message)
            self.network_manager.send_message(task.device, message)
        
        logger.info(f"暂停传输: {transfer_id}")
        return True
    
    def resume_transfer(self, transfer_id: str) -> bool:
        """恢复传输"""
        # 查找对应的传输任务
        task = self.send_tasks.get(transfer_id) or self.receive_tasks.get(transfer_id)
        if not task:
            logger.error(f"找不到传输任务: {transfer_id}")
            return False
        
        # 更新状态
        task.paused = False
        task.file_info.status = "transferring"
        
        # 如果是发送方，则发送恢复消息
        if task.is_sender:
            resume_message = {
                "transfer_id": transfer_id,
                "action": "resume"
            }
            message = Message(MessageType.RESUME, resume_message)
            self.network_manager.send_message(task.device, message)
        
        logger.info(f"恢复传输: {transfer_id}")
        return True
    
    def cancel_transfer(self, transfer_id: str) -> bool:
        """取消传输"""
        # 查找对应的传输任务
        task = self.send_tasks.get(transfer_id) or self.receive_tasks.get(transfer_id)
        if not task:
            logger.error(f"找不到传输任务: {transfer_id}")
            return False
        
        # 更新状态
        task.cancelled = True
        task.file_info.status = "cancelled"
        
        # 如果是发送方，则发送取消消息
        if task.is_sender:
            cancel_message = {
                "transfer_id": transfer_id,
                "action": "cancel"
            }
            message = Message(MessageType.CANCEL, cancel_message)
            self.network_manager.send_message(task.device, message)
        
        # 如果是接收方，且文件已经部分下载，则删除部分文件
        if not task.is_sender and task.file_info.save_path and os.path.exists(task.file_info.save_path):
            try:
                os.remove(task.file_info.save_path)
                logger.info(f"删除未完成的文件: {task.file_info.save_path}")
            except Exception as e:
                logger.error(f"删除未完成文件失败: {e}")
        
        # 从任务列表中移除
        if transfer_id in self.send_tasks:
            del self.send_tasks[transfer_id]
        
        if transfer_id in self.receive_tasks:
            del self.receive_tasks[transfer_id]
        
        logger.info(f"取消传输: {transfer_id}")
        return True
    
    def get_send_tasks(self) -> List[TransferTask]:
        """获取发送任务列表"""
        return list(self.send_tasks.values())
    
    def get_receive_tasks(self) -> List[TransferTask]:
        """获取接收任务列表"""
        return list(self.receive_tasks.values())
    
    def get_pending_transfers(self) -> List[FileInfo]:
        """获取待确认的传输请求列表"""
        return list(self.pending_transfers.values())
        
    def _on_file_progress(self, file_info: FileInfo, progress: float, speed: float):
        """文件进度回调处理"""
        # 将回调转发到注册的回调函数
        if self.on_file_progress:
            self.on_file_progress(file_info, progress, speed)
    
    def _on_file_complete(self, file_info: FileInfo, is_sender: bool):
        """文件完成回调处理"""
        # 将回调转发到注册的回调函数
        if self.on_transfer_complete:
            self.on_transfer_complete(file_info, is_sender)
    
    def _on_file_error(self, file_info: FileInfo, error_message: str):
        """文件错误回调处理"""
        # 将回调转发到注册的回调函数
        if self.on_transfer_error:
            self.on_transfer_error(file_info, error_message)
            
    def _handle_network_message(self, sender: DeviceInfo, message: Message):
        """处理网络消息"""
        if message.msg_type == MessageType.TRANSFER_REQUEST:
            # 处理传输请求
            files_data = message.payload.get("files", [])
            if not files_data:
                logger.warning(f"收到空传输请求: {sender.device_name}")
                return
                
            # 创建文件信息对象
            files = [FileInfo.from_dict(data) for data in files_data]
            for file_info in files:
                transfer_id = f"{sender.device_id}_{file_info.file_id}"
                file_info.transfer_id = transfer_id
                self.pending_transfers[transfer_id] = file_info
                
            # 调用传输请求回调，询问是否接受传输
            accepted = False
            if self.on_transfer_request:
                accepted = self.on_transfer_request(sender, files)
                
            # 如果自动接受，则直接处理
            if accepted:
                for file_info in files:
                    self.accept_transfer(file_info.transfer_id)
                    
        elif message.msg_type == MessageType.TRANSFER_ACCEPT:
            # 处理传输接受消息
            transfer_id = message.payload.get("transfer_id")
            if not transfer_id or transfer_id not in self.send_tasks:
                logger.warning(f"收到未知传输ID的接受消息: {transfer_id}")
                return
                
            # 启动文件发送
            task = self.send_tasks[transfer_id]
            task.status = "transferring"
            task.file_info.status = "transferring"
            
            # 创建发送线程
            thread = threading.Thread(target=self._file_sender_thread, args=(task,))
            thread.daemon = True
            thread.start()
            self.sender_threads[transfer_id] = thread
            
        elif message.msg_type == MessageType.TRANSFER_REJECT:
            # 处理传输拒绝消息
            transfer_id = message.payload.get("transfer_id")
            reason = message.payload.get("reason", "未提供原因")
            
            if not transfer_id or transfer_id not in self.send_tasks:
                logger.warning(f"收到未知传输ID的拒绝消息: {transfer_id}")
                return
                
            # 取消任务
            task = self.send_tasks[transfer_id]
            task.status = "rejected"
            task.file_info.status = "rejected"
            
            # 触发错误回调
            if self.on_transfer_error:
                self.on_transfer_error(task.file_info, f"传输被拒绝: {reason}")
                
            # 从任务列表中移除
            del self.send_tasks[transfer_id]
            
    def _transfer_server_loop(self):
        """传输服务器循环，监听文件传输请求"""
        try:
            # 创建传输服务器套接字
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind(('0.0.0.0', TRANSFER_PORT))
            server_socket.settimeout(1.0)  # 设置超时以支持中断
            server_socket.listen(5)
            
            logger.info(f"传输服务器启动在端口 {TRANSFER_PORT}")
            
            while self.running:
                try:
                    client_socket, address = server_socket.accept()
                    client_ip = address[0]
                    
                    logger.info(f"接收到来自 {client_ip} 的传输连接")
                    
                    # 创建处理线程
                    thread = threading.Thread(target=self._handle_client, args=(client_socket,))
                    thread.daemon = True
                    thread.start()
                    
                except socket.timeout:
                    # 超时继续循环
                    continue
                except Exception as e:
                    if self.running:  # 只有在运行时才记录错误
                        logger.error(f"传输服务器错误: {e}")
                    
            # 关闭服务器套接字
            server_socket.close()
            logger.info("传输服务器关闭")
            
        except Exception as e:
            logger.error(f"传输服务器启动失败: {e}")
            
    def _file_sender_thread(self, task: TransferTask):
        """文件发送线程"""
        # 此方法在单独的线程中运行，处理文件发送
        try:
            # 创建客户端套接字
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.settimeout(10.0)  # 10秒连接超时
            
            # 连接到接收方
            try:
                client_socket.connect((task.device.ip_address, TRANSFER_PORT))
            except Exception as e:
                logger.error(f"连接到接收方失败: {e}")
                if self.on_transfer_error:
                    self.on_transfer_error(task.file_info, f"连接失败: {e}")
                return
                
            # 设置任务状态
            task.socket = client_socket
            task.status = "transferring"
            task.file_info.status = "transferring"
            task.start_time = time.time()
            
            # 发送文件信息消息
            file_info_msg = {
                "type": MessageType.FILE_INFO,
                "payload": task.file_info.to_dict()
            }
            client_socket.sendall(json.dumps(file_info_msg).encode('utf-8'))
            
            # 发送文件数据
            with open(task.file_info.file_path, 'rb') as f:
                task.current_chunk = 0
                bytes_sent = 0
                
                while True:
                    if task.cancelled:
                        break
                        
                    if task.paused:
                        time.sleep(0.1)
                        continue
                        
                    chunk = f.read(task.file_info.chunk_size)
                    if not chunk:
                        break
                        
                    client_socket.sendall(chunk)
                    bytes_sent += len(chunk)
                    task.update_progress(bytes_sent)
                    task.current_chunk += 1
                    
            # 发送完成消息
            if not task.cancelled:
                complete_msg = {
                    "type": MessageType.COMPLETE,
                    "payload": {"file_id": task.file_info.file_id}
                }
                client_socket.sendall(json.dumps(complete_msg).encode('utf-8'))
                
                # 更新状态
                task.status = "completed"
                task.file_info.status = "completed"
                task.end_time = time.time()
                
                # 触发完成回调
                if self.on_transfer_complete:
                    self.on_transfer_complete(task.file_info, True)
                    
            # 关闭套接字
            client_socket.close()
            
        except Exception as e:
            logger.error(f"文件发送错误: {e}")
            
            # 更新状态
            task.status = "failed"
            task.file_info.status = "failed"
            
            # 触发错误回调
            if self.on_transfer_error:
                self.on_transfer_error(task.file_info, str(e))
                
        finally:
            # 无论如何都要从发送线程中移除
            if task.transfer_id in self.sender_threads:
                del self.sender_threads[task.transfer_id]
                
    def _handle_client(self, client_socket):
        """处理客户端连接"""
        # 此方法在单独的线程中运行，处理文件接收
        task = None
        
        try:
            # 设置超时
            client_socket.settimeout(30.0)
            
            # 接收文件信息
            data = client_socket.recv(BUFFER_SIZE)
            if not data:
                return
                
            # 解析文件信息
            try:
                file_info_msg = json.loads(data.decode('utf-8'))
                if file_info_msg["type"] != MessageType.FILE_INFO:
                    logger.error("无效的文件信息消息")
                    return
                    
                file_info = FileInfo.from_dict(file_info_msg["payload"])
                
            except Exception as e:
                logger.error(f"解析文件信息失败: {e}")
                return
                
            # 查找对应的接收任务
            transfer_id = file_info.transfer_id
            if transfer_id not in self.receive_tasks:
                logger.error(f"找不到接收任务: {transfer_id}")
                return
                
            task = self.receive_tasks[transfer_id]
            task.socket = client_socket
            task.status = "transferring"
            task.file_info.status = "transferring"
            task.start_time = time.time()
            
            # 确保目标目录存在
            os.makedirs(os.path.dirname(task.file_info.save_path), exist_ok=True)
            
            # 接收文件数据
            with open(task.file_info.save_path, 'wb') as f:
                bytes_received = 0
                
                while True:
                    if task.cancelled:
                        break
                        
                    if task.paused:
                        time.sleep(0.1)
                        continue
                        
                    try:
                        data = client_socket.recv(BUFFER_SIZE)
                        if not data:
                            break
                            
                        # 检查是否是完成消息
                        try:
                            msg = json.loads(data.decode('utf-8'))
                            if msg.get("type") == MessageType.COMPLETE:
                                logger.info(f"接收到完成消息: {transfer_id}")
                                break
                        except:
                            # 不是JSON，是文件数据
                            pass
                            
                        # 写入文件数据
                        f.write(data)
                        bytes_received += len(data)
                        task.update_progress(bytes_received)
                        
                    except socket.timeout:
                        # 接收超时
                        logger.warning(f"接收超时: {transfer_id}")
                        break
                        
            # 更新状态
            if not task.cancelled:
                # 可选：验证文件哈希
                if task.file_info.file_hash:
                    if not task.file_info.verify_hash():
                        task.status = "failed"
                        task.file_info.status = "failed"
                        
                        if self.on_transfer_error:
                            self.on_transfer_error(task.file_info, "文件校验失败")
                            
                        # 删除不完整的文件
                        try:
                            os.remove(task.file_info.save_path)
                        except:
                            pass
                            
                        return
                        
                task.status = "completed"
                task.file_info.status = "completed"
                task.end_time = time.time()
                
                # 触发完成回调
                if self.on_transfer_complete:
                    self.on_transfer_complete(task.file_info, False)
                    
        except Exception as e:
            logger.error(f"处理客户端连接错误: {e}")
            
            if task:
                # 更新状态
                task.status = "failed"
                task.file_info.status = "failed"
                
                # 触发错误回调
                if self.on_transfer_error:
                    self.on_transfer_error(task.file_info, str(e))
                    
                # 删除不完整的文件
                try:
                    if task.file_info.save_path and os.path.exists(task.file_info.save_path):
                        os.remove(task.file_info.save_path)
                except:
                    pass
                    
        finally:
            # 关闭套接字
            try:
                client_socket.close()
            except:
                pass
                
            # 从接收线程中移除
            if task and task.transfer_id in self.receiver_threads:
                del self.receiver_threads[task.transfer_id] 