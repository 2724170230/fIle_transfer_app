import socket
import threading
import json
import os
import time

class NetworkManager:
    def __init__(self, receive_callback=None, progress_callback=None):
        self.server_socket = None
        self.receive_callback = receive_callback  # 接收完成回调
        self.progress_callback = progress_callback  # 进度回调
        self.running = False
    
    def start_server(self, host='0.0.0.0', port=9999):
        """启动接收服务器"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((host, port))
        self.server_socket.listen(5)
        self.running = True
        
        # 在新线程中监听连接
        threading.Thread(target=self._accept_connections, daemon=True).start()
        print(f"服务器已启动，监听于 {host}:{port}")
    
    def _accept_connections(self):
        """接受客户端连接"""
        while self.running:
            try:
                client, addr = self.server_socket.accept()
                print(f"接受来自 {addr} 的连接")
                # 在新线程中处理客户端请求
                threading.Thread(target=self._handle_client, args=(client, addr), daemon=True).start()
            except Exception as e:
                if self.running:
                    print(f"接受连接出错: {e}")
    
    def _handle_client(self, client_socket, addr):
        """处理客户端连接和文件接收"""
        try:
            # 接收文件信息
            file_info_raw = b''
            while b'\n' not in file_info_raw:
                chunk = client_socket.recv(1024)
                if not chunk:
                    return
                file_info_raw += chunk
            
            # 解析文件信息
            file_info_str = file_info_raw.split(b'\n')[0].decode()
            file_info = json.loads(file_info_str)
            
            filename = file_info['filename']
            filesize = file_info['filesize']
            
            print(f"接收文件: {filename}, 大小: {filesize} 字节")
            
            # 通知UI开始接收文件
            if self.progress_callback:
                self.progress_callback(filename, 0)
            
            # 确定保存路径
            save_path = os.path.join(os.path.expanduser("~/Downloads"), filename)
            
            # 接收文件内容
            with open(save_path, 'wb') as f:
                bytes_received = 0
                # 从socket读取额外的数据（在文件信息之后可能有部分文件内容）
                extra_data = file_info_raw.split(b'\n', 1)
                if len(extra_data) > 1:
                    f.write(extra_data[1])
                    bytes_received += len(extra_data[1])
                
                # 继续接收文件内容
                while bytes_received < filesize:
                    chunk = client_socket.recv(min(4096, filesize - bytes_received))
                    if not chunk:
                        break
                    f.write(chunk)
                    bytes_received += len(chunk)
                    
                    # 更新进度
                    progress = int(bytes_received * 100 / filesize)
                    if self.progress_callback:
                        self.progress_callback(filename, progress)
            
            # 完成接收
            if self.receive_callback:
                self.receive_callback(save_path)
                
            print(f"文件 {filename} 接收完成，保存至 {save_path}")
        
        except Exception as e:
            print(f"接收文件错误: {e}")
        finally:
            client_socket.close()
    
    def send_file(self, host, port, filepath):
        """发送文件到指定主机"""
        threading.Thread(target=self._send_file_thread, args=(host, port, filepath), daemon=True).start()
    
    def _send_file_thread(self, host, port, filepath):
        """在线程中发送文件"""
        try:
            # 建立连接
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.connect((host, port))
            
            # 准备文件信息
            filename = os.path.basename(filepath)
            filesize = os.path.getsize(filepath)
            file_info = {
                "filename": filename,
                "filesize": filesize
            }
            
            print(f"发送文件: {filename}, 大小: {filesize} 字节, 到: {host}:{port}")
            
            # 发送文件信息
            client.sendall(json.dumps(file_info).encode() + b'\n')
            
            # 发送文件内容
            with open(filepath, 'rb') as f:
                # 每次发送4KB数据
                bytes_sent = 0
                while bytes_sent < filesize:
                    chunk = f.read(4096)
                    if not chunk:
                        break
                    client.sendall(chunk)
                    bytes_sent += len(chunk)
                    
                    # 更新进度
                    progress = int(bytes_sent * 100 / filesize)
                    if self.progress_callback:
                        self.progress_callback(filename, progress)
            
            # 关闭连接
            client.close()
            print(f"文件 {filename} 发送完成")
            return True
        except Exception as e:
            print(f"发送文件错误: {e}")
            return False
    
    def stop_server(self):
        """停止服务器"""
        self.running = False
        if self.server_socket:
            try:
                self.server_socket.close()
                print("服务器已关闭")
            except:
                pass 