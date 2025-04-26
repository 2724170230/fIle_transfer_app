import os
import socket
import json
import threading
import time
import logging
import tempfile
import hashlib
from PyQt5.QtCore import QObject, pyqtSignal

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("FileTransfer")

# 默认传输参数
BUFFER_SIZE = 8192  # 8KB缓冲区
CHUNK_SIZE = 1024 * 1024  # 1MB块大小
SERVICE_PORT = 45679  # 默认传输服务端口
DEFAULT_SAVE_DIR = os.path.expanduser("~/Downloads/SendNow")  # 默认保存目录

class FileTransferStatus:
    """文件传输状态常量"""
    WAITING = "waiting"
    CONNECTING = "connecting"
    TRANSFERRING = "transferring"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class FileTransferServer(QObject):
    """文件传输服务器，用于接收客户端发送的文件"""
    
    # 定义信号
    statusChanged = pyqtSignal(str)  # 状态变化信号
    transferRequest = pyqtSignal(dict)  # 收到传输请求信号
    transferProgress = pyqtSignal(str, int, int)  # 传输进度信号（文件名，当前字节数，总字节数）
    transferComplete = pyqtSignal(str, str)  # 传输完成信号（文件名，保存路径）
    transferFailed = pyqtSignal(str, str)  # 传输失败信号（文件名，错误信息）
    pendingTransferRequest = pyqtSignal(dict, object)  # 等待用户确认的传输请求（文件信息，客户端套接字）
    
    def __init__(self, host='0.0.0.0', port=SERVICE_PORT, save_dir=None):
        super().__init__()
        self.host = host
        self.port = port
        self.server_socket = None
        self.running = False
        self.transfer_thread = None
        
        # 设置保存目录
        self.save_dir = save_dir if save_dir else DEFAULT_SAVE_DIR
            
        # 待处理的传输请求
        self.pending_requests = {}
        
        # 确保保存目录存在
        os.makedirs(self.save_dir, exist_ok=True)
    
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
            os.makedirs(directory, exist_ok=True)
            
            # 测试目录是否可写
            test_file = os.path.join(directory, ".test_write")
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
            
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
        os.makedirs(save_dir, exist_ok=True)
        
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
                    chunk_size = min(8192, remaining)
                    
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
        hash_obj = hashlib.md5()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                hash_obj.update(chunk)
        file_hash = hash_obj.hexdigest()
        
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
            self.client_socket.settimeout(10)  # 设置超时时间为10秒
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
                    chunk = f.read(8192)
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

# 如果作为独立脚本运行，执行测试代码
if __name__ == "__main__":
    # 测试文件传输功能
    import sys
    from PyQt5.QtCore import QCoreApplication
    
    app = QCoreApplication(sys.argv)
    
    # 创建保存目录
    save_dir = os.path.join(tempfile.gettempdir(), "sendnow_test")
    os.makedirs(save_dir, exist_ok=True)
    print(f"文件将保存到: {save_dir}")
    
    # 创建测试文件
    test_file = os.path.join(tempfile.gettempdir(), "sendnow_test_file.txt")
    with open(test_file, 'w') as f:
        f.write("Hello, SendNow! " * 1000)  # 创建一个有一些内容的测试文件
    
    print(f"测试文件: {test_file}")
    
    # 创建服务器
    server = FileTransferServer(save_dir=save_dir)
    server.auto_accept = True  # 测试模式自动接受
    
    # 注册服务器回调
    def on_server_status(status):
        print(f"服务器状态: {status}")
    
    def on_transfer_request(info):
        print(f"传输请求: {info['name']} ({info['size']} 字节) 来自 {info['sender']}")
    
    def on_server_progress(filename, current, total):
        percent = (current * 100) // total
        print(f"服务器接收进度: {filename} - {current}/{total} 字节 ({percent}%)")
    
    def on_transfer_complete(filename, path):
        print(f"传输完成: {filename} -> {path}")
    
    def on_transfer_failed(filename, error):
        print(f"传输失败: {filename} - {error}")
    
    # 连接服务器信号
    server.statusChanged.connect(on_server_status)
    server.transferRequest.connect(on_transfer_request)
    server.transferProgress.connect(on_server_progress)
    server.transferComplete.connect(on_transfer_complete)
    server.transferFailed.connect(on_transfer_failed)
    
    # 启动服务器
    server.start()
    
    # 创建客户端
    client = FileTransferClient()
    
    # 注册客户端回调
    def on_client_status(status):
        print(f"客户端状态: {status}")
    
    def on_client_progress(filename, current, total):
        percent = (current * 100) // total
        print(f"发送进度: {filename} - {current}/{total} 字节 ({percent}%)")
    
    def on_client_complete(filename, response):
        print(f"发送完成: {filename} - {response}")
        app.quit()  # 测试完成后退出应用
    
    def on_client_failed(filename, error):
        print(f"发送失败: {filename} - {error}")
        app.quit()  # 测试失败后退出应用
    
    # 连接客户端信号
    client.statusChanged.connect(on_client_status)
    client.transferProgress.connect(on_client_progress)
    client.transferComplete.connect(on_client_complete)
    client.transferFailed.connect(on_client_failed)
    
    # 等待1秒后开始发送
    def start_sending():
        print("开始发送文件...")
        client.send_file(test_file, "127.0.0.1")
    
    QTimer = app.startTimer(1000)
    app.timerEvent = lambda event: start_sending() if event.timerId() == QTimer else None
    
    # 运行应用
    sys.exit(app.exec_()) 