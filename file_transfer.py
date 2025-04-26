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

class FileTransferStatus:
    """文件传输状态常量"""
    WAITING = "waiting"
    CONNECTING = "connecting"
    TRANSFERRING = "transferring"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class FileTransferServer(QObject):
    """文件接收服务器"""
    
    # 信号定义
    statusChanged = pyqtSignal(str)                   # 状态改变
    transferRequest = pyqtSignal(dict)                # 收到传输请求
    transferProgress = pyqtSignal(str, int, int)      # 传输进度(文件名, 当前, 总大小)
    transferComplete = pyqtSignal(str, str)           # 传输完成(文件名, 保存路径)
    transferFailed = pyqtSignal(str, str)             # 传输失败(文件名, 错误信息)
    
    def __init__(self, save_dir=None, port=SERVICE_PORT):
        super().__init__()
        
        # 配置参数
        self.port = port
        self.save_dir = save_dir or os.path.join(os.path.expanduser("~"), "Downloads")
        
        # 确保保存目录存在
        os.makedirs(self.save_dir, exist_ok=True)
        
        # 运行状态
        self.is_running = False
        self.server_socket = None
        self.transfer_threads = []  # 活动传输线程列表
    
    def start(self):
        """启动文件接收服务器"""
        if self.is_running:
            return
        
        self.is_running = True
        self.statusChanged.emit("正在启动文件接收服务...")
        
        # 启动服务器线程
        self.server_thread = threading.Thread(target=self._server_loop, daemon=True)
        self.server_thread.start()
        
        logger.info(f"文件接收服务已启动，监听端口: {self.port}")
    
    def stop(self):
        """停止文件接收服务器"""
        if not self.is_running:
            return
        
        self.is_running = False
        self.statusChanged.emit("正在停止文件接收服务...")
        
        # 关闭服务器套接字
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        
        # 等待服务器线程结束
        if hasattr(self, 'server_thread') and self.server_thread.is_alive():
            self.server_thread.join(timeout=1.0)
        
        # 关闭所有传输线程
        for thread in self.transfer_threads[:]:
            if thread.is_alive():
                thread.join(timeout=0.5)
        
        self.transfer_threads.clear()
        self.statusChanged.emit("文件接收服务已停止")
        logger.info("文件接收服务已停止")
    
    def set_save_directory(self, directory):
        """设置文件保存目录"""
        if os.path.isdir(directory):
            self.save_dir = directory
            os.makedirs(self.save_dir, exist_ok=True)
            logger.info(f"文件保存目录已设置为: {self.save_dir}")
            return True
        return False
    
    def _server_loop(self):
        """服务器监听循环"""
        try:
            # 创建服务器套接字
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind(('', self.port))
            self.server_socket.listen(5)
            self.server_socket.settimeout(1.0)  # 设置超时，以便能够定期检查is_running标志
            
            self.statusChanged.emit(f"文件接收服务已启动，端口: {self.port}")
            
            while self.is_running:
                try:
                    # 接受客户端连接
                    client_socket, client_address = self.server_socket.accept()
                    logger.info(f"收到来自 {client_address[0]} 的连接")
                    
                    # 创建新线程处理文件传输
                    transfer_thread = threading.Thread(
                        target=self._handle_client,
                        args=(client_socket, client_address),
                        daemon=True
                    )
                    self.transfer_threads.append(transfer_thread)
                    transfer_thread.start()
                    
                    # 清理已结束的线程
                    self._cleanup_threads()
                
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.is_running:  # 仅在运行状态记录错误
                        logger.error(f"接受客户端连接时发生错误: {str(e)}")
        
        except Exception as e:
            logger.error(f"文件接收服务器错误: {str(e)}")
        finally:
            # 确保套接字关闭
            if self.server_socket:
                try:
                    self.server_socket.close()
                except:
                    pass
            
            logger.info("文件接收服务器线程已结束")
    
    def _cleanup_threads(self):
        """清理已结束的传输线程"""
        active_threads = []
        for thread in self.transfer_threads:
            if thread.is_alive():
                active_threads.append(thread)
        self.transfer_threads = active_threads
    
    def _handle_client(self, client_socket, client_address):
        """处理客户端连接和文件传输"""
        file_info = None
        temp_file = None
        total_received = 0
        
        try:
            # 设置超时
            client_socket.settimeout(30.0)  # 30秒超时
            
            # 接收文件元数据
            header_data = b""
            while b"\n" not in header_data:
                chunk = client_socket.recv(BUFFER_SIZE)
                if not chunk:
                    raise Exception("连接在接收元数据前关闭")
                header_data += chunk
                if len(header_data) > 10240:  # 限制头部大小为10KB
                    raise Exception("元数据过大")
            
            # 分离头部和可能的文件数据部分
            header_end = header_data.index(b"\n")
            file_data = header_data[header_end + 1:]
            header_data = header_data[:header_end]
            
            # 解析文件信息
            file_info = json.loads(header_data.decode('utf-8'))
            file_name = file_info.get('name', 'unknown_file')
            file_size = int(file_info.get('size', 0))
            file_hash = file_info.get('hash', '')
            
            logger.info(f"接收文件: {file_name} ({file_size} 字节)")
            
            # 触发传输请求信号
            self.transferRequest.emit({
                'name': file_name,
                'size': file_size,
                'sender': client_address[0]
            })
            
            # 创建临时文件
            temp_fd, temp_path = tempfile.mkstemp(prefix="sendnow_")
            temp_file = os.fdopen(temp_fd, 'wb')
            
            # 写入已接收的数据
            if file_data:
                temp_file.write(file_data)
                total_received = len(file_data)
                self.transferProgress.emit(file_name, total_received, file_size)
            
            # 计算哈希值（用于校验）
            hash_obj = hashlib.md5()
            if file_data:
                hash_obj.update(file_data)
            
            # 接收文件数据
            last_progress_time = time.time()
            while total_received < file_size:
                # 接收数据块
                chunk = client_socket.recv(BUFFER_SIZE)
                if not chunk:
                    break
                
                # 写入文件并更新计数
                temp_file.write(chunk)
                hash_obj.update(chunk)
                total_received += len(chunk)
                
                # 更新进度（限制更新频率，避免信号过多）
                current_time = time.time()
                if current_time - last_progress_time >= 0.1 or total_received == file_size:
                    self.transferProgress.emit(file_name, total_received, file_size)
                    last_progress_time = current_time
            
            # 检查传输是否完成
            if total_received < file_size:
                raise Exception(f"文件传输不完整: 已接收 {total_received}/{file_size} 字节")
            
            # 关闭临时文件
            temp_file.close()
            temp_file = None
            
            # 验证文件哈希
            calculated_hash = hash_obj.hexdigest()
            if file_hash and calculated_hash != file_hash:
                raise Exception(f"文件校验失败: 期望 {file_hash}, 实际 {calculated_hash}")
            
            # 移动到最终位置
            file_path = os.path.join(self.save_dir, file_name)
            # 如果文件已存在，添加序号
            base_name, ext = os.path.splitext(file_name)
            counter = 1
            while os.path.exists(file_path):
                file_path = os.path.join(self.save_dir, f"{base_name}_{counter}{ext}")
                counter += 1
            
            os.rename(temp_path, file_path)
            logger.info(f"文件保存成功: {file_path}")
            
            # 发送传输完成信号
            self.transferComplete.emit(file_name, file_path)
            
            # 发送确认信息
            response = {"status": "success", "message": "文件接收完成"}
            client_socket.sendall(json.dumps(response).encode('utf-8') + b"\n")
        
        except Exception as e:
            logger.error(f"文件接收错误: {str(e)}")
            
            # 发送传输失败信号
            if file_info and 'name' in file_info:
                self.transferFailed.emit(file_info['name'], str(e))
            
            # 尝试发送错误响应
            try:
                response = {"status": "error", "message": str(e)}
                client_socket.sendall(json.dumps(response).encode('utf-8') + b"\n")
            except:
                pass
        
        finally:
            # 清理资源
            if temp_file:
                try:
                    temp_file.close()
                except:
                    pass
            
            # 关闭客户端套接字
            try:
                client_socket.close()
            except:
                pass

class FileTransferClient(QObject):
    """文件发送客户端"""
    
    # 信号定义
    statusChanged = pyqtSignal(str)                   # 状态改变
    transferProgress = pyqtSignal(str, int, int)      # 传输进度(文件名, 当前, 总大小)
    transferComplete = pyqtSignal(str, str)           # 传输完成(文件名, 接收方响应)
    transferFailed = pyqtSignal(str, str)             # 传输失败(文件名, 错误信息)
    
    def __init__(self):
        super().__init__()
        self.current_transfer = None  # 当前传输线程
    
    def send_file(self, file_path, target_ip, target_port=SERVICE_PORT, timeout=30):
        """发送文件到指定IP地址"""
        # 检查文件是否存在
        if not os.path.isfile(file_path):
            self.transferFailed.emit(os.path.basename(file_path), "文件不存在")
            return False
        
        # 如果有正在进行的传输，返回错误
        if self.current_transfer and self.current_transfer.is_alive():
            self.transferFailed.emit(os.path.basename(file_path), "已有正在进行的传输")
            return False
        
        # 启动新的传输线程
        self.current_transfer = threading.Thread(
            target=self._send_file_thread,
            args=(file_path, target_ip, target_port, timeout),
            daemon=True
        )
        self.current_transfer.start()
        
        return True
    
    def _send_file_thread(self, file_path, target_ip, target_port, timeout):
        """文件发送线程"""
        file_name = os.path.basename(file_path)
        client_socket = None
        
        try:
            # 计算文件大小和哈希值
            file_size = os.path.getsize(file_path)
            file_hash = self._calculate_file_hash(file_path)
            
            # 准备元数据
            file_info = {
                "name": file_name,
                "size": file_size,
                "hash": file_hash
            }
            
            # 更新状态
            self.statusChanged.emit(f"正在连接到 {target_ip}:{target_port}...")
            
            # 创建客户端套接字
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.settimeout(timeout)
            client_socket.connect((target_ip, target_port))
            
            # 发送文件元数据
            header = json.dumps(file_info).encode('utf-8') + b"\n"
            client_socket.sendall(header)
            
            # 更新状态
            self.statusChanged.emit(f"正在发送: {file_name}")
            
            # 发送文件数据
            with open(file_path, 'rb') as f:
                bytes_sent = 0
                last_progress_time = time.time()
                
                while bytes_sent < file_size:
                    # 读取文件块
                    chunk = f.read(BUFFER_SIZE)
                    if not chunk:
                        break
                    
                    # 发送数据
                    client_socket.sendall(chunk)
                    bytes_sent += len(chunk)
                    
                    # 更新进度（限制更新频率）
                    current_time = time.time()
                    if current_time - last_progress_time >= 0.1 or bytes_sent == file_size:
                        self.transferProgress.emit(file_name, bytes_sent, file_size)
                        last_progress_time = current_time
            
            # 接收响应
            response_data = b""
            while b"\n" not in response_data:
                chunk = client_socket.recv(BUFFER_SIZE)
                if not chunk:
                    break
                response_data += chunk
                if len(response_data) > 10240:  # 限制响应大小
                    break
            
            # 解析响应
            if b"\n" in response_data:
                response_json = response_data.split(b"\n")[0].decode('utf-8')
                response = json.loads(response_json)
                
                # 检查传输状态
                if response.get("status") == "success":
                    logger.info(f"文件发送成功: {file_name}")
                    self.transferComplete.emit(file_name, response.get("message", "传输成功"))
                else:
                    error_msg = response.get("message", "未知错误")
                    logger.error(f"文件发送失败: {error_msg}")
                    self.transferFailed.emit(file_name, error_msg)
            else:
                # 无有效响应但数据已发送完成
                logger.info(f"文件数据已发送，但未收到确认响应: {file_name}")
                self.transferComplete.emit(file_name, "传输可能已完成，但未收到确认")
        
        except Exception as e:
            logger.error(f"文件发送错误: {str(e)}")
            self.transferFailed.emit(file_name, str(e))
        
        finally:
            # 关闭套接字
            if client_socket:
                try:
                    client_socket.close()
                except:
                    pass
            
            # 更新状态
            self.statusChanged.emit("传输已完成")
    
    def _calculate_file_hash(self, file_path):
        """计算文件MD5哈希值"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

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