"""
以下代码及注释全部由AI Agent生成
"""

"""
文件传输客户端模块 (File Transfer Client Module)

该模块实现了文件传输应用程序的客户端功能，负责向服务器发送文件。
主要功能：
- 与文件传输服务器建立连接
- 向服务器发送文件信息和数据
- 监控传输进度并发出信号
- 处理传输结果和错误情况

作为应用程序传输模块的一部分，提供可靠的文件发送能力，支持MD5哈希校验确保文件完整性。
"""

import os
import socket
import json
import threading
import time
import hashlib
import logging
from PyQt5.QtCore import QObject, pyqtSignal

from .common import BUFFER_SIZE, SERVICE_PORT, logger
from .utils import compute_file_hash

class FileTransferClient(QObject):
    """文件传输客户端，用于向服务器发送文件"""
    
    # 定义信号
    statusChanged = pyqtSignal(str)  # 状态变化信号
    transferProgress = pyqtSignal(str, int, int)  # 传输进度信号（文件名，当前字节数，总字节数）
    transferComplete = pyqtSignal(str, dict)  # 传输完成信号（文件名，服务器响应）
    transferFailed = pyqtSignal(str, str)  # 传输失败信号（文件名，错误信息）
    
    def __init__(self):
        super().__init__()
        self.client_socket = None
        self.transfer_thread = None
    
    def send_file(self, file_path, server_host, server_port=SERVICE_PORT):
        """发送文件到指定服务器"""
        # 检查文件是否存在
        if not os.path.isfile(file_path):
            self.transferFailed.emit(os.path.basename(file_path), "文件不存在")
            return False
        
        # 获取文件信息
        filename = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        
        # 计算文件MD5哈希值
        file_hash = compute_file_hash(file_path)
        
        # 创建文件信息
        file_info = {
            "name": filename,
            "size": file_size,
            "hash": file_hash,
            "type": os.path.splitext(filename)[1][1:],  # 文件类型（扩展名）
            "timestamp": int(time.time())
        }
        
        # 启动传输线程
        self.transfer_thread = threading.Thread(
            target=self._send_file_thread,
            args=(file_path, file_info, server_host, server_port),
            daemon=True
        )
        self.transfer_thread.start()
        
        return True
    
    def _send_file_thread(self, file_path, file_info, server_host, server_port):
        """文件发送线程"""
        filename = file_info["name"]
        file_size = file_info["size"]
        
        try:
            # 连接到服务器
            self.statusChanged.emit(f"正在连接到 {server_host}:{server_port}...")
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.settimeout(60)  # 设置超时时间为60秒（1分钟）
            self.client_socket.connect((server_host, server_port))
            
            # 发送文件信息
            self.statusChanged.emit("正在发送文件信息...")
            info_json = json.dumps(file_info)
            self.client_socket.sendall(info_json.encode('utf-8'))
            
            # 等待服务器确认
            response_data = self.client_socket.recv(4096)
            if not response_data:
                raise Exception("服务器没有响应")
            
            response = json.loads(response_data.decode('utf-8'))
            
            # 检查服务器响应
            if response.get("status") != "accepted":
                reason = response.get("reason", "未知原因")
                raise Exception(f"服务器拒绝了传输请求: {reason}")
            
            # 发送文件数据
            self.statusChanged.emit(f"正在发送文件: {filename}")
            
            with open(file_path, 'rb') as f:
                sent = 0
                
                while sent < file_size:
                    # 读取数据块
                    chunk = f.read(BUFFER_SIZE)
                    if not chunk:
                        break
                    
                    # 发送数据块
                    self.client_socket.sendall(chunk)
                    
                    # 更新发送计数
                    sent += len(chunk)
                    
                    # 发送进度信号
                    self.transferProgress.emit(filename, sent, file_size)
            
            # 等待服务器确认传输完成
            response_data = self.client_socket.recv(4096)
            if not response_data:
                raise Exception("服务器没有确认传输完成")
            
            # 解析服务器响应
            response = json.loads(response_data.decode('utf-8'))
            
            # 检查传输结果
            if response.get("status") == "success":
                logger.info(f"文件发送成功: {filename}")
                self.statusChanged.emit("传输已完成")
                self.transferComplete.emit(filename, response)
            else:
                error_msg = response.get("message", "未知错误")
                raise Exception(f"服务器报告错误: {error_msg}")
        
        except Exception as e:
            error_msg = str(e)
            logger.error(f"文件发送失败: {filename} - {error_msg}")
            self.statusChanged.emit(f"传输失败: {error_msg}")
            self.transferFailed.emit(filename, error_msg)
        
        finally:
            # 关闭客户端连接
            if self.client_socket:
                try:
                    self.client_socket.close()
                except:
                    pass 