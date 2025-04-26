import socket
import threading
import os
import json
from PyQt5.QtCore import QObject, pyqtSignal

class FileTransferSignals(QObject):
    """用于在文件传输过程中发出信号的类"""
    progress_updated = pyqtSignal(int)  # 传输进度信号
    transfer_complete = pyqtSignal(str)  # 传输完成信号
    transfer_error = pyqtSignal(str)     # 传输错误信号

class FileTransfer:
    def __init__(self, port=5000):
        self.port = port
        self.signals = FileTransferSignals()
        self.server_socket = None
        self.is_receiving = False
    
    def start_server(self):
        """启动文件接收服务器"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind(('0.0.0.0', self.port))
        self.server_socket.listen(1)
        self.is_receiving = True
        
        # 在新线程中运行服务器
        threading.Thread(target=self._run_server, daemon=True).start()
    
    def stop_server(self):
        """停止文件接收服务器"""
        self.is_receiving = False
        if self.server_socket:
            self.server_socket.close()
    
    def _run_server(self):
        """运行文件接收服务器"""
        while self.is_receiving:
            try:
                client_socket, _ = self.server_socket.accept()
                # 接收文件信息
                file_info = client_socket.recv(1024).decode()
                file_info = json.loads(file_info)
                file_name = file_info['file_name']
                file_size = file_info['file_size']
                
                # 确认接收
                client_socket.send(b'ready')
                
                # 接收文件数据
                received_size = 0
                with open(os.path.join('received_files', file_name), 'wb') as f:
                    while received_size < file_size:
                        data = client_socket.recv(8192)
                        if not data:
                            break
                        f.write(data)
                        received_size += len(data)
                        # 发送进度信号
                        progress = int((received_size / file_size) * 100)
                        self.signals.progress_updated.emit(progress)
                
                # 发送完成信号
                self.signals.transfer_complete.emit(file_name)
                client_socket.close()
                
            except Exception as e:
                self.signals.transfer_error.emit(str(e))
    
    def send_file(self, file_path, target_ip):
        """发送文件到目标IP"""
        try:
            # 获取文件信息
            file_name = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            
            # 连接到接收方
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect((target_ip, self.port))
            
            # 发送文件信息
            file_info = {
                'file_name': file_name,
                'file_size': file_size
            }
            client_socket.send(json.dumps(file_info).encode())
            
            # 等待接收方准备就绪
            client_socket.recv(1024)
            
            # 发送文件数据
            sent_size = 0
            with open(file_path, 'rb') as f:
                while sent_size < file_size:
                    data = f.read(8192)
                    if not data:
                        break
                    client_socket.send(data)
                    sent_size += len(data)
                    # 发送进度信号
                    progress = int((sent_size / file_size) * 100)
                    self.signals.progress_updated.emit(progress)
            
            # 发送完成信号
            self.signals.transfer_complete.emit(file_name)
            client_socket.close()
            
        except Exception as e:
            self.signals.transfer_error.emit(str(e)) 