import sys
import os
import threading
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                           QHBoxLayout, QPushButton, QLabel, QLineEdit, 
                           QFileDialog, QProgressBar, QMessageBox)
from PyQt5.QtCore import Qt
from file_transfer import FileTransfer

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("文件传输应用")
        self.setMinimumSize(500, 300)
        
        # 创建文件传输实例
        self.file_transfer = FileTransfer()
        self.file_transfer.signals.progress_updated.connect(self.update_progress)
        self.file_transfer.signals.transfer_complete.connect(self.transfer_complete)
        self.file_transfer.signals.transfer_error.connect(self.transfer_error)
        
        # 创建主窗口部件
        self.setup_ui()
        
        # 创建接收文件目录
        os.makedirs('received_files', exist_ok=True)
    
    def setup_ui(self):
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建主布局
        main_layout = QVBoxLayout(central_widget)
        
        # 服务器控制部分
        server_group = QWidget()
        server_layout = QHBoxLayout(server_group)
        self.server_status_label = QLabel("服务器状态：未运行")
        self.server_button = QPushButton("启动服务器")
        self.server_button.clicked.connect(self.toggle_server)
        server_layout.addWidget(self.server_status_label)
        server_layout.addWidget(self.server_button)
        main_layout.addWidget(server_group)
        
        # 发送文件部分
        send_group = QWidget()
        send_layout = QVBoxLayout(send_group)
        
        # IP地址输入
        ip_layout = QHBoxLayout()
        ip_label = QLabel("目标IP：")
        self.ip_input = QLineEdit()
        ip_layout.addWidget(ip_label)
        ip_layout.addWidget(self.ip_input)
        send_layout.addLayout(ip_layout)
        
        # 文件选择
        file_layout = QHBoxLayout()
        self.file_path_label = QLabel("未选择文件")
        self.select_file_button = QPushButton("选择文件")
        self.select_file_button.clicked.connect(self.select_file)
        file_layout.addWidget(self.file_path_label)
        file_layout.addWidget(self.select_file_button)
        send_layout.addLayout(file_layout)
        
        # 发送按钮
        self.send_button = QPushButton("发送文件")
        self.send_button.clicked.connect(self.send_file)
        send_layout.addWidget(self.send_button)
        
        main_layout.addWidget(send_group)
        
        # 进度条
        self.progress_bar = QProgressBar()
        main_layout.addWidget(self.progress_bar)
        
        # 状态标签
        self.status_label = QLabel("")
        main_layout.addWidget(self.status_label)
        
        # 添加一些弹性空间
        main_layout.addStretch()
    
    def toggle_server(self):
        if self.server_button.text() == "启动服务器":
            self.file_transfer.start_server()
            self.server_button.setText("停止服务器")
            self.server_status_label.setText("服务器状态：运行中")
        else:
            self.file_transfer.stop_server()
            self.server_button.setText("启动服务器")
            self.server_status_label.setText("服务器状态：未运行")
    
    def select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择文件")
        if file_path:
            self.file_path_label.setText(file_path)
    
    def send_file(self):
        file_path = self.file_path_label.text()
        target_ip = self.ip_input.text()
        
        if file_path == "未选择文件":
            QMessageBox.warning(self, "错误", "请先选择要发送的文件")
            return
        
        if not target_ip:
            QMessageBox.warning(self, "错误", "请输入目标IP地址")
            return
        
        # 在新线程中发送文件
        self.status_label.setText("正在发送文件...")
        self.send_button.setEnabled(False)
        threading.Thread(target=lambda: self.file_transfer.send_file(file_path, target_ip),
                       daemon=True).start()
    
    def update_progress(self, value):
        self.progress_bar.setValue(value)
    
    def transfer_complete(self, file_name):
        self.status_label.setText(f"文件 {file_name} 传输完成")
        self.progress_bar.setValue(100)
        self.send_button.setEnabled(True)
        QMessageBox.information(self, "成功", f"文件 {file_name} 传输完成")
    
    def transfer_error(self, error_msg):
        self.status_label.setText(f"传输错误: {error_msg}")
        self.send_button.setEnabled(True)
        QMessageBox.critical(self, "错误", f"传输错误: {error_msg}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_()) 