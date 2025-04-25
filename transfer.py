import os
import time
import hashlib
import threading
import logging
import socket
import json
from queue import Queue
from typing import Dict, List, Tuple, Optional, Callable, Any, Set
import uuid

from network import NetworkManager, Message, MessageType, DeviceInfo, BUFFER_SIZE, TRANSFER_PORT

# 配置日志
logger = logging.getLogger("SendNow.Transfer")

class FileInfo:
    """文件信息类，保存文件传输所需的元数据"""
    
    def __init__(self, file_path: str, transfer_id: str = None, device_id: str = None,
                 file_id: str = None, chunk_size: int = 8192, save_path: str = None):
        self.file_path = file_path
        self.file_id = file_id or str(uuid.uuid4())
        self.transfer_id = transfer_id or str(uuid.uuid4())
        self.device_id = device_id
        
        # 文件基本信息
        self.file_name = os.path.basename(file_path)
        self.file_size = 0
        self.file_hash = None
        self.mime_type = self._get_mime_type()
        self.chunk_size = chunk_size
        self.save_path = save_path
        
        # 状态信息
        self.status = "pending"  # pending, transferring, completed, failed, cancelled
        self.created_at = time.time()
        
        # 如果文件存在，获取其大小
        if os.path.exists(file_path):
            try:
                self.file_size = os.path.getsize(file_path)
            except OSError as e:
                logger.error(f"获取文件大小失败: {e}")
                self.file_size = 0
    
    def _get_mime_type(self) -> str:
        """获取文件的MIME类型"""
        try:
            # 优先使用文件扩展名判断
            _, ext = os.path.splitext(self.file_path)
            if ext:
                ext = ext.lower()
                # 常见文件类型映射
                mime_map = {
                    '.txt': 'text/plain',
                    '.html': 'text/html',
                    '.htm': 'text/html',
                    '.pdf': 'application/pdf',
                    '.doc': 'application/msword',
                    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                    '.xls': 'application/vnd.ms-excel',
                    '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    '.ppt': 'application/vnd.ms-powerpoint',
                    '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
                    '.jpg': 'image/jpeg',
                    '.jpeg': 'image/jpeg',
                    '.png': 'image/png',
                    '.gif': 'image/gif',
                    '.mp3': 'audio/mpeg',
                    '.mp4': 'video/mp4',
                    '.zip': 'application/zip',
                    '.rar': 'application/x-rar-compressed',
                    '.tar': 'application/x-tar',
                    '.gz': 'application/gzip',
                }
                if ext in mime_map:
                    return mime_map[ext]
            
            # 如果文件存在，可以通过读取文件头来判断
            if os.path.exists(self.file_path):
                import mimetypes
                mime_type, _ = mimetypes.guess_type(self.file_path)
                if mime_type:
                    return mime_type
            
            # 默认二进制流
            return 'application/octet-stream'
        except Exception as e:
            logger.warning(f"获取MIME类型失败: {e}")
            return 'application/octet-stream'
    
    def compute_hash(self) -> str:
        """计算文件的SHA-256哈希值"""
        if not os.path.exists(self.file_path):
            logger.error(f"无法计算哈希: 文件不存在 {self.file_path}")
            return None
            
        hash_obj = hashlib.sha256()
        try:
            with open(self.file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    hash_obj.update(chunk)
            self.file_hash = hash_obj.hexdigest()
            return self.file_hash
        except Exception as e:
            logger.error(f"计算文件哈希时出错: {e}")
            return None
    
    def calculate_file_hash(self, file_path: str = None) -> str:
        """计算指定文件的SHA-256哈希值
        
        Args:
            file_path: 指定要计算哈希的文件路径，默认使用self.file_path
            
        Returns:
            str: 文件的哈希值，如果失败则返回None
        """
        path_to_check = file_path or self.file_path
        if not path_to_check or not os.path.exists(path_to_check):
            logger.error(f"无法计算哈希: 文件不存在 {path_to_check}")
            return None
            
        hash_obj = hashlib.sha256()
        try:
            with open(path_to_check, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    hash_obj.update(chunk)
            return hash_obj.hexdigest()
        except Exception as e:
            logger.error(f"计算文件哈希时出错: {e}")
            return None
            
    def verify_hash(self, file_path: str = None) -> bool:
        """验证文件的完整性
        
        Args:
            file_path: 要验证的文件路径，默认使用self.save_path
            
        Returns:
            bool: 验证成功返回True，否则返回False
        """
        if not self.file_hash:
            logger.warning("无法验证哈希: 没有原始哈希值")
            return False
            
        path_to_verify = file_path or self.save_path
        if not path_to_verify or not os.path.exists(path_to_verify):
            logger.error(f"无法验证哈希: 文件不存在 {path_to_verify}")
            return False
            
        calculated_hash = self.calculate_file_hash(path_to_verify)
        if not calculated_hash:
            return False
            
        is_valid = calculated_hash == self.file_hash
        if not is_valid:
            logger.error(f"哈希验证失败: 预期={self.file_hash}, 实际={calculated_hash}")
        else:
            logger.info(f"哈希验证成功: {path_to_verify}")
            
        return is_valid
    
    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "file_id": self.file_id,
            "transfer_id": self.transfer_id,
            "device_id": self.device_id,
            "file_name": self.file_name,
            "file_size": self.file_size,
            "file_hash": self.file_hash,
            "mime_type": self.mime_type,
            "chunk_size": self.chunk_size,
            "status": self.status,
            "created_at": self.created_at
        }
    
    @staticmethod
    def from_dict(data: dict) -> 'FileInfo':
        """从字典创建FileInfo对象"""
        file_info = FileInfo(
            file_path=data.get("file_path", ""),
            transfer_id=data.get("transfer_id"),
            device_id=data.get("device_id"),
            file_id=data.get("file_id"),
            chunk_size=data.get("chunk_size", 8192)
        )
        file_info.file_name = data.get("file_name", file_info.file_name)
        file_info.file_size = data.get("file_size", file_info.file_size)
        file_info.file_hash = data.get("file_hash")
        file_info.mime_type = data.get("mime_type", file_info.mime_type)
        file_info.status = data.get("status", file_info.status)
        file_info.created_at = data.get("created_at", file_info.created_at)
        file_info.save_path = data.get("save_path")
        
        return file_info
    
    def __str__(self) -> str:
        """返回文件信息的字符串表示"""
        return f"FileInfo({self.file_name}, 大小: {self.file_size} bytes, 状态: {self.status})"

class TransferTask:
    """传输任务类，表示一个文件的传输任务"""
    
    def __init__(self, file_info: FileInfo, device: DeviceInfo = None, is_sender: bool = True, save_path: str = None):
        self.file_info = file_info
        self.device = device
        self.is_sender = is_sender
        self.transfer_id = file_info.transfer_id
        self.status = "pending"  # pending, transferring, paused, completed, failed, cancelled
        self.socket = None
        self.bytes_transferred = 0
        self.start_time = None
        self.end_time = None
        self.last_update_time = time.time()
        self.paused = False
        self.cancelled = False
        self.save_path = save_path
        self.error_message = None
        
    def update_progress(self, bytes_transferred: int):
        """更新传输进度"""
        self.bytes_transferred = bytes_transferred
        self.last_update_time = time.time()
        
    def get_progress(self) -> float:
        """获取传输进度百分比"""
        if self.file_info.file_size <= 0:
            return 0.0
        return min(1.0, self.bytes_transferred / self.file_info.file_size)
        
    def get_speed(self) -> float:
        """获取传输速度 (bytes/s)"""
        if not self.start_time:
            return 0.0
            
        elapsed = time.time() - self.start_time
        if elapsed <= 0:
            return 0.0
            
        return self.bytes_transferred / elapsed
        
    def get_formatted_speed(self) -> str:
        """获取格式化的传输速度"""
        speed = self.get_speed()
        for unit in ['B/s', 'KB/s', 'MB/s', 'GB/s']:
            if speed < 1024.0:
                return f"{speed:.1f} {unit}"
            speed /= 1024.0
        return f"{speed:.1f} TB/s"
        
    def get_remaining_time(self) -> int:
        """获取预计剩余时间（秒）"""
        if self.status in ["completed", "failed", "cancelled"]:
            return 0
            
        speed = self.get_speed()
        if speed <= 0:
            return -1  # 无法估计
            
        remaining_bytes = self.file_info.file_size - self.bytes_transferred
        return int(remaining_bytes / speed)
        
    def format_remaining_time(self) -> str:
        """格式化剩余时间"""
        secs = self.get_remaining_time()
        if secs < 0:
            return "计算中..."
            
        if secs < 60:
            return f"{secs}秒"
        elif secs < 3600:
            mins = secs // 60
            return f"{mins}分钟"
        else:
            hours = secs // 3600
            mins = (secs % 3600) // 60
            return f"{hours}小时{mins}分钟"
            
    def cancel(self):
        """取消传输任务"""
        self.cancelled = True
        self.status = "cancelled"
        self.file_info.status = "cancelled"
        
    def pause(self):
        """暂停传输任务"""
        self.paused = True
        self.status = "paused"
        self.file_info.status = "paused"
        
    def resume(self):
        """恢复传输任务"""
        self.paused = False
        self.status = "transferring"
        self.file_info.status = "transferring"
        
    def __str__(self) -> str:
        """返回传输任务的字符串表示"""
        progress = self.get_progress() * 100
        return f"传输任务: {self.file_info.file_name} ({progress:.1f}%), 状态: {self.status}"

class TransferManager:
    """传输管理器，处理文件传输任务"""
    
    def __init__(self, network_manager: NetworkManager, default_save_dir: str = None):
        """初始化传输管理器
        
        Args:
            network_manager: 网络管理器实例
            default_save_dir: 默认文件保存目录，如果不提供则使用~/Downloads
        """
        self.network_manager = network_manager
        
        # 启用文件哈希验证
        self.use_hash_verification = True
        
        # 传输任务状态存储
        self.pending_transfers = {}    # 等待接受的传输请求
        self.accepted_transfers = {}   # 已接受的传输请求
        self.pending_sends = {}        # 等待对方接受的发送请求
        
        # 活动任务
        self.sender_tasks = {}         # 发送任务 {transfer_id: TransferTask}
        self.receiver_tasks = {}       # 接收任务 {transfer_id: TransferTask}
        
        # 用于发送/接收文件的线程
        self.sender_threads = {}       # 发送线程 {transfer_id: Thread}
        self.receiver_threads = {}     # 接收线程 {transfer_id: Thread}
        
        # 传输服务器
        self.server_socket = None
        self.server_thread = None
        self.running = False
        
        # 回调函数
        self.on_transfer_request = None     # 收到传输请求时回调
        self.on_transfer_accepted = None    # 传输请求被接受时回调
        self.on_transfer_rejected = None    # 传输请求被拒绝时回调
        self.on_transfer_complete = None    # 传输完成时回调
        self.on_transfer_error = None       # 传输错误时回调
        self.on_progress_update = None      # 进度更新回调
        self.on_file_progress = None        # 与app_controller保持兼容的旧回调函数
        
        # 默认设置
        self.default_save_dir = default_save_dir or os.path.join(os.path.expanduser("~"), "Downloads")
        
        # 注册网络消息处理器
        if network_manager:
            network_manager.on_message_received = self._handle_network_message
            
        # 创建默认保存目录
        os.makedirs(self.default_save_dir, exist_ok=True)
        
        logger.info(f"传输管理器初始化完成，默认保存目录: {self.default_save_dir}")
    
    def start(self):
        """启动传输管理器"""
        if self.running:
            logger.warning("传输管理器已经在运行")
            return
        
        self.running = True
        
        # 启动传输服务器线程，用于监听传入的传输请求
        self.server_thread = threading.Thread(target=self._transfer_server_loop)
        self.server_thread.daemon = True
        self.server_thread.start()
        
        logger.info("传输管理器已启动")
    
    def stop(self):
        """停止传输管理器"""
        if not self.running:
            return
        
        self.running = False
        
        # 取消所有传输任务
        for task in list(self.sender_tasks.values()):
            self.cancel_transfer(task.transfer_id)
        
        for task in list(self.receiver_tasks.values()):
            self.cancel_transfer(task.transfer_id)
        
        # 等待服务器线程结束
        if self.server_thread:
            self.server_thread.join(1.0)
        
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
        
        Args:
            device: 目标设备信息
            file_paths: 要发送的文件路径列表
            
        Returns:
            List[str]: 已创建的传输任务ID列表
        """
        if not device or not file_paths:
            logger.error("无效的设备或文件路径")
            return []
            
        # 检查是否有可发送的文件
        valid_paths = [path for path in file_paths if os.path.exists(path) and os.path.isfile(path)]
        if not valid_paths:
            logger.error("没有找到有效的文件")
            return []
            
        # 创建文件信息对象
        file_infos = []
        for file_path in valid_paths:
            # 创建文件信息对象
            file_info = FileInfo(
                file_path=file_path,
                device_id=device.device_id,
                chunk_size=8192
            )
            
            # 如果启用了哈希验证，计算文件哈希
            if self.use_hash_verification:
                logger.info(f"计算文件哈希: {file_info.file_name}")
                file_info.compute_hash()
                
            file_infos.append(file_info)
            
        # 构造传输请求
        transfer_ids = []
        for file_info in file_infos:
            # 请求负载
            request_payload = {
                "sender_id": self.network_manager.device_id,
                "sender_name": self.network_manager.device_name,
                "file_infos": [info.to_dict() for info in file_infos],
                "timestamp": time.time()
            }
            
            # 创建传输请求消息
            request_message = Message(MessageType.TRANSFER_REQUEST, request_payload)
            
            # 发送请求
            success = self.network_manager.send_message(device, request_message)
            if not success:
                logger.error(f"发送传输请求失败: {file_info.file_name}")
                continue
                
            logger.info(f"已发送传输请求: {len(file_infos)} 文件到 {device.device_name}")
            
            # 将请求添加到待处理列表
            for info in file_infos:
                self.pending_transfers[info.transfer_id] = info
                transfer_ids.append(info.transfer_id)
                
        return transfer_ids
        
    def accept_transfer(self, transfer_id: str, save_path: str = None) -> bool:
        """接受文件传输请求
        
        Args:
            transfer_id: 传输ID
            save_path: 保存文件的路径，如果不提供则使用默认保存目录
            
        Returns:
            bool: 是否成功发送接受消息
        """
        if transfer_id not in self.pending_transfers:
            logger.error(f"未找到待处理的传输请求: {transfer_id}")
            return False
        
        # 使用提供的保存路径或默认路径    
        actual_save_path = save_path or self.default_save_dir
            
        # 获取请求信息
        request_info = self.pending_transfers[transfer_id]
        if isinstance(request_info, dict):
            file_info = request_info.get("file_info")
            sender = request_info.get("sender")
        else:
            # 向后兼容，如果直接存储了FileInfo对象
            file_info = request_info
            sender = None
            for device in self.network_manager.get_devices():
                if device.device_id == file_info.device_id:
                    sender = device
                    break
        
        if not file_info:
            logger.error(f"无效的传输请求数据: {transfer_id}")
            return False
            
        # 设置保存路径
        file_info.save_path = os.path.join(actual_save_path, file_info.file_name)
        
        # 检查目录是否存在，不存在则创建
        os.makedirs(os.path.dirname(file_info.save_path), exist_ok=True)
        
        # 创建任务对象
        task = self.create_transfer_task(file_info, transfer_id, actual_save_path)
        
        # 添加到已接受列表
        self.accepted_transfers[transfer_id] = {
            "file_info": file_info,
            "save_path": actual_save_path,
            "status": "accepted",
            "timestamp": time.time(),
            "task": task
        }
        
        # 发送接受消息
        response_payload = {
            "transfer_id": transfer_id,
            "file_id": file_info.file_id,
            "accepted": True,
            "receiver_id": self.network_manager.device_id,
            "receiver_name": self.network_manager.device_name
        }
        
        accept_message = Message(MessageType.TRANSFER_ACCEPT, response_payload)
        
        if sender:
            success = self.network_manager.send_message(sender, accept_message)
        else:
            logger.warning(f"找不到发送方设备，尝试使用device_id发送: {file_info.device_id}")
            # 尝试从device_id创建一个临时设备对象
            temp_device = DeviceInfo(
                device_id=file_info.device_id,
                device_name="未知设备",
                ip_address=file_info.device_id.split('@')[-1] if '@' in file_info.device_id else "0.0.0.0"
            )
            success = self.network_manager.send_message(temp_device, accept_message)
        
        if success:
            logger.info(f"已接受文件传输: {file_info.file_name}, 保存到 {actual_save_path}")
            # 从待处理列表移除
            if transfer_id in self.pending_transfers:
                del self.pending_transfers[transfer_id]
        else:
            logger.error(f"发送接受消息失败: {transfer_id}")
            # 清理已接受记录
            if transfer_id in self.accepted_transfers:
                del self.accepted_transfers[transfer_id]
                
        return success
        
    def create_transfer_task(self, file_info: FileInfo, transfer_id: str, save_path: str) -> TransferTask:
        """创建文件传输任务
        
        Args:
            file_info: 文件信息
            transfer_id: 传输ID
            save_path: 保存路径
            
        Returns:
            TransferTask: 创建的传输任务
        """
        # 确保传输ID已设置
        file_info.transfer_id = transfer_id
        
        # 设置保存路径
        if os.path.isdir(save_path):
            full_save_path = os.path.join(save_path, file_info.file_name)
        else:
            full_save_path = save_path
            
        file_info.save_path = full_save_path
        
        # 创建任务
        sender = None
        if transfer_id in self.pending_transfers:
            sender = self.pending_transfers[transfer_id]["sender"]
            
        task = TransferTask(
            file_info=file_info,
            device=sender,
            is_sender=False,
            save_path=full_save_path
        )
        
        # 添加到任务列表
        self.receiver_tasks[transfer_id] = task
        return task
    
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
        task = self.sender_tasks.get(transfer_id) or self.receiver_tasks.get(transfer_id)
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
        task = self.sender_tasks.get(transfer_id) or self.receiver_tasks.get(transfer_id)
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
        task = self.sender_tasks.get(transfer_id) or self.receiver_tasks.get(transfer_id)
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
        if transfer_id in self.sender_tasks:
            del self.sender_tasks[transfer_id]
        
        if transfer_id in self.receiver_tasks:
            del self.receiver_tasks[transfer_id]
        
        logger.info(f"取消传输: {transfer_id}")
        return True
    
    def get_send_tasks(self) -> List[TransferTask]:
        """获取发送任务列表"""
        return list(self.sender_tasks.values())
    
    def get_receive_tasks(self) -> List[TransferTask]:
        """获取接收任务列表"""
        return list(self.receiver_tasks.values())
    
    def get_pending_transfers(self) -> List[FileInfo]:
        """获取待确认的传输请求列表"""
        return list(self.pending_transfers.values())
        
    def _on_file_progress(self, file_info: FileInfo, progress: float, speed: float):
        """文件进度回调处理
        
        同时支持新的on_progress_update和旧的on_file_progress回调接口
        """
        # 将回调转发到注册的回调函数
        if self.on_progress_update:
            self.on_progress_update(file_info, progress, speed)
            
        # 向后兼容旧的回调接口
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
            
    def _handle_network_message(self, message: Message, addr: Tuple[str, int]):
        """处理收到的网络消息
        
        Args:
            message: 收到的消息
            addr: 发送方地址
        """
        if not message:
            return
            
        try:
            message_type = message.msg_type
            payload = message.payload
            
            if message_type == MessageType.TRANSFER_REQUEST:
                self._handle_transfer_request(payload, addr)
            elif message_type == MessageType.TRANSFER_ACCEPT:
                self._handle_transfer_accept(payload)
            elif message_type == MessageType.TRANSFER_REJECT:
                self._handle_transfer_reject(payload)
            elif message_type == MessageType.PAUSE:
                self._handle_pause_message(payload)
            elif message_type == MessageType.RESUME:
                self._handle_resume_message(payload)
            elif message_type == MessageType.CANCEL:
                self._handle_cancel_message(payload)
            else:
                logger.warning(f"未处理的消息类型: {message_type}")
        except Exception as e:
            logger.error(f"处理网络消息时出错: {e}")

    def _handle_transfer_request(self, payload: dict, addr: Tuple[str, int]):
        """处理传输请求
        
        Args:
            payload: 请求负载
            addr: 发送方地址
        """
        try:
            # 提取发送方信息
            sender_id = payload.get("sender_id")
            sender_name = payload.get("sender_name")
            
            if not sender_id or not sender_name:
                logger.error("传输请求缺少发送方信息")
                return
                
            # 创建发送方设备信息
            sender_device = DeviceInfo(
                device_id=sender_id,
                device_name=sender_name,
                ip_address=addr[0],
                port=TRANSFER_PORT
            )
            
            # 提取文件信息
            file_infos_data = payload.get("file_infos", [])
            if not file_infos_data:
                logger.error("传输请求不包含文件信息")
                return
                
            # 处理每个文件
            for file_data in file_infos_data:
                # 设置设备ID以便跟踪来源
                if "device_id" not in file_data:
                    file_data["device_id"] = sender_id
                
                file_info = FileInfo.from_dict(file_data)
                transfer_id = file_info.transfer_id
                
                # 存储待处理传输
                self.pending_transfers[transfer_id] = {
                    "file_info": file_info,
                    "sender": sender_device,
                    "timestamp": time.time()
                }
                
                logger.info(f"收到文件传输请求: {file_info.file_name} 来自 {sender_name}")
                
                # 触发回调
                if self.on_transfer_request:
                    # 检查回调函数期望的参数
                    import inspect
                    sig = inspect.signature(self.on_transfer_request)
                    params = list(sig.parameters.keys())
                    
                    if len(params) == 3 and params[0] == 'self':
                        # 新格式: on_transfer_request(self, file_info, sender_device, transfer_id)
                        self.on_transfer_request(file_info, sender_device, transfer_id)
                    elif len(params) == 3:
                        # 新格式: on_transfer_request(file_info, sender_device, transfer_id)
                        self.on_transfer_request(file_info, sender_device, transfer_id)
                    elif len(params) == 2 and params[0] == 'self':
                        # 旧格式: on_transfer_request(self, device, files)
                        # 我们需要收集所有文件并一次性调用
                        file_infos = [info["file_info"] for info in self.pending_transfers.values() 
                                      if isinstance(info, dict) and info.get("sender") == sender_device]
                        if file_infos:
                            return self.on_transfer_request(sender_device, file_infos)
                    elif len(params) == 2:
                        # 旧格式: on_transfer_request(device, files)
                        file_infos = [info["file_info"] for info in self.pending_transfers.values() 
                                      if isinstance(info, dict) and info.get("sender") == sender_device]
                        if file_infos:
                            return self.on_transfer_request(sender_device, file_infos)
                                              
        except Exception as e:
            logger.error(f"处理传输请求出错: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def _handle_transfer_accept(self, payload: dict):
        """处理传输接受消息"""
        transfer_id = payload.get("transfer_id")
        if not transfer_id or transfer_id not in self.sender_tasks:
            logger.warning(f"收到未知传输ID的接受消息: {transfer_id}")
            return
            
        # 启动文件发送
        task = self.sender_tasks[transfer_id]
        task.status = "transferring"
        task.file_info.status = "transferring"
        
        # 创建发送线程
        thread = threading.Thread(target=self._file_sender_thread, args=(task,))
        thread.daemon = True
        thread.start()
        self.sender_threads[transfer_id] = thread
        
    def _handle_transfer_reject(self, payload: dict):
        """处理传输拒绝消息"""
        transfer_id = payload.get("transfer_id")
        reason = payload.get("reason", "未提供原因")
        
        if not transfer_id or transfer_id not in self.sender_tasks:
            logger.warning(f"收到未知传输ID的拒绝消息: {transfer_id}")
            return
            
        # 取消任务
        task = self.sender_tasks[transfer_id]
        task.status = "rejected"
        task.file_info.status = "rejected"
        
        # 触发错误回调
        if self.on_transfer_error:
            self.on_transfer_error(task.file_info, f"传输被拒绝: {reason}")
            
        # 从任务列表中移除
        del self.sender_tasks[transfer_id]
        
    def _handle_pause_message(self, payload: dict):
        """处理暂停消息"""
        transfer_id = payload.get("transfer_id")
        if not transfer_id or transfer_id not in self.sender_tasks:
            logger.warning(f"收到未知传输ID的暂停消息: {transfer_id}")
            return
            
        # 暂停任务
        task = self.sender_tasks[transfer_id]
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
        
    def _handle_resume_message(self, payload: dict):
        """处理恢复消息"""
        transfer_id = payload.get("transfer_id")
        if not transfer_id or transfer_id not in self.sender_tasks:
            logger.warning(f"收到未知传输ID的恢复消息: {transfer_id}")
            return
            
        # 恢复任务
        task = self.sender_tasks[transfer_id]
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
        
    def _handle_cancel_message(self, payload: dict):
        """处理取消消息"""
        transfer_id = payload.get("transfer_id")
        if not transfer_id or transfer_id not in self.sender_tasks:
            logger.warning(f"收到未知传输ID的取消消息: {transfer_id}")
            return
            
        # 取消任务
        task = self.sender_tasks[transfer_id]
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
        del self.sender_tasks[transfer_id]
        
    def _transfer_server_loop(self):
        """传输服务器循环，监听文件传输请求"""
        try:
            # 创建传输服务器套接字
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind(('0.0.0.0', TRANSFER_PORT))
            self.server_socket.settimeout(1.0)  # 设置超时以支持中断
            self.server_socket.listen(5)
            
            logger.info(f"传输服务器启动在端口 {TRANSFER_PORT}")
            
            while self.running:
                try:
                    client_socket, address = self.server_socket.accept()
                    client_ip = address[0]
                    
                    logger.info(f"接收到来自 {client_ip} 的传输连接")
                    
                    # 创建处理线程
                    thread = threading.Thread(target=self._handle_client, args=(client_socket, address))
                    thread.daemon = True
                    thread.start()
                    
                except socket.timeout:
                    # 超时继续循环
                    continue
                except Exception as e:
                    if self.running:  # 只有在运行时才记录错误
                        logger.error(f"传输服务器错误: {e}")
                    
            # 关闭服务器套接字
            self.server_socket.close()
            logger.info("传输服务器关闭")
            
        except Exception as e:
            logger.error(f"传输服务器启动失败: {e}")
            
    def _file_sender_thread(self, task):
        """文件发送线程，处理单个文件的发送"""
        logger.info(f"开始发送文件: {task.file_info.file_name}")
        client_socket = None
        file_handle = None
        retry_count = 0
        max_retries = 3  # 最大重试次数
        
        try:
            # 创建到接收方的TCP连接
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.settimeout(30.0)  # 设置超时时间
            
            try:
                # 连接到接收方
                client_socket.connect((task.device.ip_address, task.device.port))
            except (ConnectionRefusedError, socket.timeout, OSError) as e:
                logger.error(f"连接到接收方失败: {e}")
                task.status = "failed"
                task.file_info.status = "failed"
                if self.on_transfer_error:
                    self.on_transfer_error(task.file_info, f"连接失败: {str(e)}")
                return
                
            # 准备文件信息
            task.status = "transferring"
            task.file_info.status = "transferring"
            task.start_time = time.time()
            
            # 如果启用了哈希验证但还没有计算哈希值，则现在计算
            if self.use_hash_verification and not task.file_info.file_hash:
                logger.info(f"计算文件哈希: {task.file_info.file_name}")
                task.file_info.compute_hash()
                
            # 检查文件是否存在
            if not os.path.exists(task.file_info.file_path):
                raise FileNotFoundError(f"文件不存在: {task.file_info.file_path}")
                
            # 首先发送文件信息消息
            file_info_message = Message(MessageType.FILE_INFO, task.file_info.to_dict())
            client_socket.sendall(file_info_message.to_bytes())
            
            # 打开文件并开始传输
            file_handle = open(task.file_info.file_path, 'rb')
            bytes_sent = 0
            chunk_size = task.file_info.chunk_size
            last_progress_update = time.time()
            
            while bytes_sent < task.file_info.file_size:
                # 检查任务是否被取消
                if task.cancelled:
                    logger.info(f"传输已取消: {task.file_info.file_name}")
                    break
                    
                # 检查任务是否被暂停
                if task.paused:
                    time.sleep(0.1)  # 暂停状态下减少CPU使用
                    continue
                    
                # 读取文件块
                chunk = file_handle.read(chunk_size)
                if not chunk:  # 文件结束
                    break
                    
                # 尝试发送数据块
                try:
                    bytes_actually_sent = client_socket.send(chunk)
                    if bytes_actually_sent == 0:
                        # 连接已断开
                        raise ConnectionError("连接已断开")
                        
                    bytes_sent += bytes_actually_sent
                    
                    # 如果只发送了部分数据，调整文件指针
                    if bytes_actually_sent < len(chunk):
                        file_handle.seek(file_handle.tell() - (len(chunk) - bytes_actually_sent))
                        
                    task.update_progress(bytes_sent)
                    
                    # 定期更新进度通知
                    now = time.time()
                    if now - last_progress_update > 0.5:  # 每0.5秒更新一次
                        last_progress_update = now
                        if self.on_progress_update:
                            self.on_progress_update(task.file_info, bytes_sent / task.file_info.file_size)
                            
                except (ConnectionError, socket.timeout, socket.error) as e:
                    logger.warning(f"发送数据时发生错误: {e}，尝试重试 ({retry_count+1}/{max_retries})")
                    retry_count += 1
                    
                    # 如果已达到最大重试次数，则失败
                    if retry_count >= max_retries:
                        raise ConnectionError(f"发送数据失败，已达最大重试次数: {e}")
                        
                    # 否则等待一会儿再重试
                    time.sleep(1)
                    continue
                    
                # 重置重试计数器（成功发送后）
                retry_count = 0
                
            # 发送完成消息
            if not task.cancelled and bytes_sent >= task.file_info.file_size:
                # 添加文件哈希到完成消息中（如果有）
                completion_payload = {"status": "success"}
                if task.file_info.file_hash:
                    completion_payload["file_hash"] = task.file_info.file_hash
                    
                complete_message = Message(MessageType.COMPLETE, completion_payload)
                client_socket.sendall(complete_message.to_bytes())
                
                logger.info(f"文件发送完成: {task.file_info.file_name}")
                task.status = "completed"
                task.file_info.status = "completed"
                task.end_time = time.time()
                
                if self.on_transfer_complete:
                    self.on_transfer_complete(task.file_info, True)
                    
        except FileNotFoundError as e:
            logger.error(f"文件不存在: {e}")
            task.status = "failed"
            task.file_info.status = "failed"
            if self.on_transfer_error:
                self.on_transfer_error(task.file_info, f"文件不存在: {str(e)}")
                
        except Exception as e:
            logger.error(f"发送文件时出错: {e}")
            task.status = "failed"
            task.file_info.status = "failed"
            if self.on_transfer_error:
                self.on_transfer_error(task.file_info, f"发送失败: {str(e)}")
                
        finally:
            # 清理资源
            if file_handle:
                try:
                    file_handle.close()
                except:
                    pass
                    
            if client_socket:
                try:
                    client_socket.close()
                except:
                    pass
                    
            # 从发送线程列表中移除
            if task.transfer_id in self.sender_threads:
                del self.sender_threads[task.transfer_id]
                
    def _handle_client(self, client_socket, client_address):
        """处理客户端连接的方法"""
        logger.info(f"接受来自 {client_address} 的连接")
        task = None

        try:
            # 接收文件信息
            data = client_socket.recv(4096)
            if not data:
                logger.warning("接收到空数据")
                return

            try:
                # 使用Message类解析信息
                message = Message.from_bytes(data)
                
                # 检查消息类型
                if message.type != MessageType.FILE_INFO:
                    logger.error(f"接收到非文件信息消息: {message.type}")
                    return
                    
                file_info_dict = message.payload
                
                # 创建FileInfo对象
                file_info = FileInfo.from_dict(file_info_dict)
                logger.info(f"接收到文件信息: {file_info.file_name}, 大小: {file_info.file_size} 字节")
                
                # 使用传输ID查找任务
                transfer_id = file_info.transfer_id
                if transfer_id in self.accepted_transfers:
                    # 如果这是一个已接受的传输
                    save_path = self.accepted_transfers[transfer_id]["save_path"]
                    task = self.create_transfer_task(file_info, transfer_id, save_path)
                    self.receiver_tasks[transfer_id] = task
                    logger.info(f"开始接收文件: {file_info.file_name} 到 {save_path}")
                else:
                    logger.warning(f"未接受的传输请求: {transfer_id}")
                    client_socket.close()
                    return
                    
            except Exception as e:
                logger.error(f"解析文件信息失败: {e}")
                return
                
            # 设置任务状态
            task.socket = client_socket
            task.status = "transferring"
            task.file_info.status = "transferring"
            task.start_time = time.time()
            
            # 确保目标目录存在
            os.makedirs(os.path.dirname(task.save_path), exist_ok=True)
            
            # 接收文件数据
            with open(task.save_path, 'wb') as f:
                bytes_received = 0
                last_progress_update = time.time()
                
                # 预先开一个4KB的buffer
                buf_size = task.file_info.chunk_size
                
                while bytes_received < task.file_info.file_size:
                    if task.cancelled:
                        logger.info(f"传输已取消: {task.file_info.file_name}")
                        break
                        
                    if task.paused:
                        time.sleep(0.1)
                        continue
                        
                    try:
                        # 检查是否有完成消息或文件数据
                        client_socket.settimeout(1.0)
                        chunk = client_socket.recv(buf_size)
                        
                        if not chunk:  # 连接已关闭
                            logger.warning("连接提前关闭")
                            break
                            
                        # 尝试解析为Message对象（检查是否是完成消息）
                        try:
                            message = Message.from_bytes(chunk)
                            if message.type == MessageType.COMPLETE:
                                logger.info(f"收到完成消息: {message.payload}")
                                # 确认文件传输完成
                                if "file_hash" in message.payload and self.use_hash_verification:
                                    sender_hash = message.payload["file_hash"]
                                    # 计算已接收文件的哈希
                                    f.flush()
                                    calculated_hash = task.file_info.calculate_file_hash(task.save_path)
                                    
                                    if sender_hash != calculated_hash:
                                        logger.error(f"文件哈希验证失败: {task.file_info.file_name}")
                                        task.status = "failed"
                                        task.file_info.status = "failed"
                                        if self.on_transfer_error:
                                            self.on_transfer_error(task.file_info, "文件验证失败")
                                        return
                                        
                                    logger.info(f"文件哈希验证成功: {task.file_info.file_name}")
                                break
                            else:
                                # 如果不是完成消息，写入文件数据
                                f.write(chunk)
                                bytes_received += len(chunk)
                        except:
                            # 不是有效消息，假定是文件数据
                            f.write(chunk)
                            bytes_received += len(chunk)
                            
                        # 更新进度
                        task.update_progress(bytes_received)
                        
                        # 定期触发进度回调
                        now = time.time()
                        if now - last_progress_update > 0.5:  # 每0.5秒更新一次进度
                            last_progress_update = now
                            if self.on_progress_update:
                                self.on_progress_update(task.file_info, bytes_received / task.file_info.file_size)
                                
                    except socket.timeout:
                        # 超时，但继续循环
                        continue
                    except Exception as e:
                        logger.error(f"接收数据时出错: {e}")
                        raise
                        
            # 完成接收
            if not task.cancelled and bytes_received >= task.file_info.file_size:
                logger.info(f"文件接收完成: {task.file_info.file_name}")
                task.status = "completed"
                task.file_info.status = "completed"
                task.end_time = time.time()
                if self.on_transfer_complete:
                    self.on_transfer_complete(task.file_info, False)
            else:
                logger.warning(f"文件接收不完整: {bytes_received}/{task.file_info.file_size} 字节")
                task.status = "failed"
                task.file_info.status = "failed"
                if self.on_transfer_error:
                    self.on_transfer_error(task.file_info, "文件传输不完整")
                    
        except Exception as e:
            logger.error(f"处理客户端连接时出错: {e}")
            if task:
                task.status = "failed"
                task.file_info.status = "failed"
                if self.on_transfer_error:
                    self.on_transfer_error(task.file_info, f"接收失败: {str(e)}")
                    
        finally:
            # 关闭套接字
            try:
                client_socket.close()
            except:
                pass
                
            # 清理任务引用
            if task and task.transfer_id in self.receiver_tasks:
                task.socket = None 