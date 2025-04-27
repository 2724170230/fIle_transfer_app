import os
import socket
import json
import threading
import time
import hashlib
import logging
from PyQt5.QtCore import QObject, pyqtSignal

from .common import BUFFER_SIZE, SERVICE_PORT, logger
from .utils import ensure_directory_exists, is_directory_writable

class FileTransferServer(QObject):
    """文件传输服务器，用于接收客户端发送的文件"""
    
    # 定义信号
    statusChanged = pyqtSignal(str)  # 状态变化信号
    transferRequest = pyqtSignal(dict)  # 收到传输请求信号
    transferProgress = pyqtSignal(str, int, int)  # 传输进度信号（文件名，当前字节数，总字节数）
    transferComplete = pyqtSignal(str, str)  # 传输完成信号（文件名，保存路径）
    transferFailed = pyqtSignal(str, str)  # 传输失败信号（文件名，错误信息）
    pendingTransferRequest = pyqtSignal(dict, object)  # 等待用户确认的传输请求（文件信息，客户端套接字）
    
    def __init__(self, host='0.0.0.0', port=SERVICE_PORT):
        super().__init__()
        self.host = host
        self.port = port
        self.server_socket = None
        self.running = False
        self.transfer_thread = None
        self.save_dir = os.path.expanduser("~/Downloads/SendNow")
        
        # 待处理的传输请求
        self.pending_requests = {}
        
        # 确保保存目录存在
        ensure_directory_exists(self.save_dir)
    
    def start(self):
        """启动文件传输服务器"""
        if self.running:
            return
        
        try:
            # 创建服务器套接字
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            
            # 设置运行标志
            self.running = True
            
            # 启动服务器线程
            self.transfer_thread = threading.Thread(target=self._server_loop, daemon=True)
            self.transfer_thread.start()
            
            logger.info(f"文件传输服务器已启动 ({self.host}:{self.port})")
            self.statusChanged.emit("服务器已启动")
        
        except Exception as e:
            logger.error(f"启动文件传输服务器失败: {str(e)}")
            self.statusChanged.emit(f"启动失败: {str(e)}")
    
    def stop(self):
        """停止文件传输服务器"""
        if not self.running:
            return
        
        # 设置停止标志
        self.running = False
        
        try:
            # 关闭服务器套接字
            if self.server_socket:
                self.server_socket.close()
            
            logger.info("文件传输服务器已停止")
            self.statusChanged.emit("服务器已停止")
        
        except Exception as e:
            logger.error(f"停止文件传输服务器失败: {str(e)}")
            self.statusChanged.emit(f"停止失败: {str(e)}")
    
    def set_save_directory(self, directory):
        """设置文件保存目录"""
        try:
            # 确保目录存在
            ensure_directory_exists(directory)
            
            # 测试目录是否可写
            if not is_directory_writable(directory):
                raise Exception("目录不可写")
            
            # 设置保存目录
            self.save_dir = directory
            logger.info(f"文件保存目录已设置为: {directory}")
            return True
        
        except Exception as e:
            logger.error(f"设置保存目录失败: {str(e)}")
            return False
    
    def _server_loop(self):
        """服务器主循环，接受客户端连接并处理文件传输"""
        while self.running:
            try:
                # 接受客户端连接
                client_socket, client_address = self.server_socket.accept()
                
                # 处理传输请求
                threading.Thread(
                    target=self._handle_transfer_request,
                    args=(client_socket, client_address),
                    daemon=True
                ).start()
                
            except Exception as e:
                if self.running:  # 只在服务器正常运行时记录错误
                    logger.error(f"接受客户端连接失败: {str(e)}")
                    self.statusChanged.emit(f"连接失败: {str(e)}")
                time.sleep(0.1)  # 避免CPU占用过高
    
    def _handle_transfer_request(self, client_socket, client_address):
        """处理客户端的传输请求"""
        try:
            # 接收文件信息
            info_data = client_socket.recv(4096)
            if not info_data:
                client_socket.close()
                return
            
            # 解析文件信息
            file_info = json.loads(info_data.decode('utf-8'))
            file_info['sender'] = client_address[0]  # 添加发送者IP
            
            logger.info(f"收到文件传输请求: {file_info['name']} ({file_info['size']} 字节) 来自 {client_address[0]}")
            
            # 发送待确认的传输请求信号，等待用户确认
            request_id = str(time.time())
            self.pending_requests[request_id] = {
                'file_info': file_info,
                'client_socket': client_socket,
                'client_address': client_address
            }
            
            # 向UI发送信号，等待用户确认
            self.pendingTransferRequest.emit(file_info, client_socket)
            
        except Exception as e:
            logger.error(f"处理传输请求失败: {str(e)}")
            try:
                client_socket.close()
            except:
                pass
    
    def accept_transfer(self, client_socket, client_address, file_info, custom_save_dir=None):
        """接受文件传输请求"""
        # 向客户端发送接受响应
        try:
            response = {"status": "accepted"}
            client_socket.sendall(json.dumps(response).encode('utf-8'))
            
            # 启动文件接收线程
            save_dir = custom_save_dir if custom_save_dir else self.save_dir
            threading.Thread(
                target=self._handle_client,
                args=(client_socket, client_address, file_info, save_dir),
                daemon=True
            ).start()
            
            logger.info(f"已接受文件传输请求: {file_info['name']}")
            
        except Exception as e:
            logger.error(f"接受传输请求失败: {str(e)}")
            try:
                client_socket.close()
            except:
                pass
    
    def reject_transfer(self, client_socket):
        """拒绝文件传输请求"""
        try:
            # 向客户端发送拒绝响应
            response = {"status": "rejected", "reason": "User rejected the transfer"}
            client_socket.sendall(json.dumps(response).encode('utf-8'))
            client_socket.close()
            
            logger.info("已拒绝文件传输请求")
            
        except Exception as e:
            logger.error(f"拒绝传输请求失败: {str(e)}")
            try:
                client_socket.close()
            except:
                pass
    
    def _handle_client(self, client_socket, client_address, file_info, save_dir):
        """处理客户端连接，接收文件数据"""
        filename = file_info['name']
        file_size = file_info['size']
        file_hash = file_info.get('hash', '')  # 可选的文件哈希值
        
        # 确保保存目录存在
        ensure_directory_exists(save_dir)
        
        # 构建保存路径
        save_path = os.path.join(save_dir, filename)
        
        # 如果文件已存在，添加数字后缀
        base_name, ext = os.path.splitext(filename)
        counter = 1
        while os.path.exists(save_path):
            new_name = f"{base_name}_{counter}{ext}"
            save_path = os.path.join(save_dir, new_name)
            counter += 1
        
        try:
            # 发出传输请求信号
            self.transferRequest.emit(file_info)
            
            # 接收文件数据
            with open(save_path, 'wb') as f:
                received = 0
                hash_obj = hashlib.md5()
                
                while received < file_size:
                    # 计算剩余字节数
                    remaining = file_size - received
                    chunk_size = min(BUFFER_SIZE, remaining)
                    
                    # 接收数据块
                    chunk = client_socket.recv(chunk_size)
                    if not chunk:
                        raise Exception("连接中断")
                    
                    # 写入文件
                    f.write(chunk)
                    hash_obj.update(chunk)
                    
                    # 更新接收计数
                    received += len(chunk)
                    
                    # 发送进度信号
                    self.transferProgress.emit(filename, received, file_size)
            
            # 验证文件哈希值
            received_hash = hash_obj.hexdigest()
            if file_hash and received_hash != file_hash:
                raise Exception(f"文件哈希值不匹配: 预期 {file_hash}，实际 {received_hash}")
            
            # 发送传输完成信号
            logger.info(f"文件接收完成: {filename} -> {save_path}")
            self.transferComplete.emit(filename, save_path)
            
            # 向客户端发送成功响应
            response = {"status": "success", "message": "File received successfully"}
            client_socket.sendall(json.dumps(response).encode('utf-8'))
        
        except Exception as e:
            error_msg = str(e)
            logger.error(f"文件接收失败: {filename} - {error_msg}")
            
            # 发送传输失败信号
            self.transferFailed.emit(filename, error_msg)
            
            # 向客户端发送失败响应
            try:
                response = {"status": "error", "message": error_msg}
                client_socket.sendall(json.dumps(response).encode('utf-8'))
            except:
                pass
            
            # 删除不完整的文件
            try:
                if os.path.exists(save_path):
                    os.remove(save_path)
            except:
                pass
        
        finally:
            # 关闭客户端连接
            try:
                client_socket.close()
            except:
                pass 