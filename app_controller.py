import os
import time
import logging
import threading
from typing import List, Dict, Optional, Callable

from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QTimer

from network import NetworkManager, DeviceInfo, Message, MessageType
from transfer import TransferManager, FileInfo, TransferTask

# 添加DeviceNameGenerator模块的导入
from localsend_ui_design import DeviceNameGenerator

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("SendNow.Controller")

class AppController(QObject):
    """应用控制器，连接UI与后端功能"""
    
    # 设备发现信号
    deviceFound = pyqtSignal(object)  # 新设备发现
    deviceLost = pyqtSignal(object)   # 设备丢失
    
    # 传输信号
    transferRequest = pyqtSignal(object, list)    # 传输请求
    transferProgress = pyqtSignal(object, float, float)  # 传输进度
    transferComplete = pyqtSignal(object, bool)   # 传输完成
    transferError = pyqtSignal(object, str)       # 传输错误
    
    def __init__(self):
        super().__init__()
        
        # 获取设备信息
        self.device_name, self.device_id = DeviceNameGenerator.get_persistent_name_and_id()
        
        # 初始化网络管理器
        self.network_manager = NetworkManager(self.device_id, self.device_name)
        
        # 初始化传输管理器
        default_save_dir = os.path.join(os.path.expanduser("~"), "Downloads", "SendNow")
        self.transfer_manager = TransferManager(self.network_manager, default_save_dir)
        
        # 注册回调函数
        self.network_manager.on_device_found = self._on_device_found
        self.network_manager.on_device_lost = self._on_device_lost
        
        self.transfer_manager.on_transfer_request = self._on_transfer_request
        self.transfer_manager.on_file_progress = self._on_file_progress
        self.transfer_manager.on_transfer_complete = self._on_transfer_complete
        self.transfer_manager.on_transfer_error = self._on_transfer_error
        
        # 设备缓存
        self.devices = {}
        
        # 初始化自动保存传输请求设置
        self.auto_accept_transfers = False
        
        logger.info(f"应用控制器初始化完成: 设备={self.device_name}({self.device_id})")
    
    def start(self):
        """启动应用服务"""
        self.network_manager.start()
        self.transfer_manager.start()
        logger.info("应用服务已启动")
    
    def stop(self):
        """停止应用服务"""
        self.transfer_manager.stop()
        self.network_manager.stop()
        logger.info("应用服务已停止")
    
    def set_save_directory(self, directory: str) -> bool:
        """设置文件保存目录"""
        return self.transfer_manager.set_save_directory(directory)
    
    def get_save_directory(self) -> str:
        """获取文件保存目录"""
        return self.transfer_manager.default_save_dir
    
    def set_auto_accept_transfers(self, auto_accept: bool):
        """设置是否自动接受传输请求"""
        self.auto_accept_transfers = auto_accept
        logger.info(f"自动接受传输请求: {auto_accept}")
    
    def get_devices(self) -> List[DeviceInfo]:
        """获取已发现的设备列表"""
        return self.network_manager.get_devices()
    
    def send_files(self, device_id: str, file_paths: List[str]) -> List[str]:
        """发送文件到指定设备"""
        # 查找设备
        device = None
        
        # 打印调试信息
        logger.info(f"尝试发送文件到设备 {device_id}")
        logger.info(f"当前已发现设备: {len(self.devices)}")
        for d_id, d in self.devices.items():
            logger.info(f"  - {d.device_name} ({d.device_id}) @ {d.ip_address}")
        
        # 先精确匹配设备ID
        if device_id in self.devices:
            device = self.devices[device_id]
            logger.info(f"找到设备(精确匹配): {device.device_name} ({device.device_id})")
        else:
            # 尝试模糊匹配，去掉可能的前缀（如 "#"）
            clean_id = device_id.lstrip('#')
            # 先在缓存的设备中查找
            for d_id, d in self.devices.items():
                if d.device_id.lstrip('#') == clean_id:
                    device = d
                    logger.info(f"找到设备(模糊匹配/缓存): {device.device_name} ({device.device_id})")
                    break
            
            # 如果缓存中没找到，尝试直接从网络管理器获取最新设备列表
            if not device:
                for d in self.network_manager.get_devices():
                    if d.device_id.lstrip('#') == clean_id:
                        device = d
                        # 更新设备缓存
                        self.devices[d.device_id] = d
                        logger.info(f"找到设备(模糊匹配/网络): {device.device_name} ({device.device_id})")
                        break
        
        if not device:
            logger.error(f"找不到设备: {device_id}")
            return []
        
        # 检查文件路径有效性
        if not file_paths:
            logger.warning("文件路径为空")
            return []
        
        logger.info(f"发送 {len(file_paths)} 个文件到 {device.device_name}")
        
        return self.transfer_manager.send_files(device, file_paths)
    
    def accept_transfer(self, transfer_id: str) -> bool:
        """接受文件传输请求"""
        return self.transfer_manager.accept_transfer(transfer_id)
    
    def reject_transfer(self, transfer_id: str, reason: str = "拒绝传输") -> bool:
        """拒绝文件传输请求"""
        return self.transfer_manager.reject_transfer(transfer_id, reason)
    
    def pause_transfer(self, transfer_id: str) -> bool:
        """暂停传输"""
        return self.transfer_manager.pause_transfer(transfer_id)
    
    def resume_transfer(self, transfer_id: str) -> bool:
        """恢复传输"""
        return self.transfer_manager.resume_transfer(transfer_id)
    
    def cancel_transfer(self, transfer_id: str) -> bool:
        """取消传输"""
        return self.transfer_manager.cancel_transfer(transfer_id)
    
    def get_send_tasks(self) -> List[TransferTask]:
        """获取发送任务"""
        return self.transfer_manager.get_send_tasks()
    
    def get_receive_tasks(self) -> List[TransferTask]:
        """获取接收任务"""
        return self.transfer_manager.get_receive_tasks()
    
    def get_pending_transfers(self) -> List[FileInfo]:
        """获取待处理的传输请求"""
        return self.transfer_manager.get_pending_transfers()
    
    def _on_device_found(self, device: DeviceInfo):
        """设备发现回调"""
        logger.info(f"发现设备: {device.device_name} ({device.device_id})")
        self.devices[device.device_id] = device
        self.deviceFound.emit(device)
    
    def _on_device_lost(self, device: DeviceInfo):
        """设备丢失回调"""
        logger.info(f"设备丢失: {device.device_name} ({device.device_id})")
        if device.device_id in self.devices:
            del self.devices[device.device_id]
        self.deviceLost.emit(device)
    
    def _on_transfer_request(self, device: DeviceInfo, files: List[FileInfo]) -> bool:
        """传输请求回调"""
        logger.info(f"收到来自 {device.device_name} 的传输请求，文件数量: {len(files)}")
        self.transferRequest.emit(device, files)
        return self.auto_accept_transfers
    
    def _on_file_progress(self, file_info: FileInfo, progress: float, speed: float):
        """文件传输进度回调"""
        # 为避免UI更新太频繁，只在进度变化较大时才触发信号
        self.transferProgress.emit(file_info, progress, speed)
    
    def _on_transfer_complete(self, file_info: FileInfo, is_sender: bool):
        """文件传输完成回调"""
        logger.info(f"传输完成: {file_info.file_name} ({'发送' if is_sender else '接收'})")
        self.transferComplete.emit(file_info, is_sender)
    
    def _on_transfer_error(self, file_info: FileInfo, error_message: str):
        """文件传输错误回调"""
        logger.error(f"传输错误: {file_info.file_name} - {error_message}")
        self.transferError.emit(file_info, error_message) 