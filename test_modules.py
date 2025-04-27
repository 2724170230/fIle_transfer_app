"""
SendNow文件传输测试模块 (File Transfer Test Module)

该模块用于独立测试SendNow应用的文件传输功能，不依赖于完整的UI界面。
主要功能：
- 创建并初始化FileTransferServer和FileTransferClient实例
- 测试文件发送和接收过程
- 监控传输状态、进度和结果
- 自动完成完整的文件传输测试流程

通过该测试模块可以验证文件传输功能的正确性和稳定性，帮助开发者快速诊断传输问题。
"""

"""
测试模块化后的文件传输功能
"""
import os
import sys
import tempfile
import time
from PyQt5.QtCore import QCoreApplication, QTimer

from transfer import FileTransferServer, FileTransferClient

def test_transfer():
    """测试文件传输功能"""
    app = QCoreApplication(sys.argv)
    
    print("开始测试模块化后的文件传输功能...")
    
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
    server = FileTransferServer()
    server.set_save_directory(save_dir)
    
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
    
    def on_pending_transfer_request(file_info, client_socket):
        print(f"待处理传输请求: {file_info}")
        # 自动接受传输
        server.accept_transfer(client_socket, (file_info['sender'], 0), file_info)
    
    # 连接服务器信号
    server.statusChanged.connect(on_server_status)
    server.transferRequest.connect(on_transfer_request)
    server.transferProgress.connect(on_server_progress)
    server.transferComplete.connect(on_transfer_complete)
    server.transferFailed.connect(on_transfer_failed)
    server.pendingTransferRequest.connect(on_pending_transfer_request)
    
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

if __name__ == "__main__":
    test_transfer() 