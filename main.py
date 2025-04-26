import sys
import os
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtCore import Qt, QThread

from localsend_ui_design import MainWindow
from network_manager import NetworkManager
from device_discovery import DeviceDiscovery

class SendNowApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = MainWindow()
        self.ui.setupUi(self)
        
        # 初始化网络管理器
        self.network_manager = NetworkManager(
            receive_callback=self.on_file_received,
            progress_callback=self.update_progress
        )
        
        # 初始化设备发现
        self.device_discovery = DeviceDiscovery()
        
        # 启动服务器
        self.start_server()
        
        # 连接信号和槽
        self.ui.sendButton.clicked.connect(self.send_file)
        self.ui.refreshButton.clicked.connect(self.refresh_devices)
        
    def start_server(self):
        """在后台线程启动服务器"""
        self.server_thread = QThread()
        self.network_manager.moveToThread(self.server_thread)
        self.server_thread.started.connect(lambda: self.network_manager.start_server())
        self.server_thread.start()
    
    def update_progress(self, filename, progress):
        """更新进度条"""
        self.ui.progressBar.setValue(progress)
        self.ui.statusLabel.setText(f"正在传输: {filename} ({progress}%)")
    
    def on_file_received(self, filepath):
        """文件接收完成的回调"""
        self.ui.progressBar.setValue(100)
        self.ui.statusLabel.setText(f"文件已保存至: {filepath}")
    
    def send_file(self):
        """发送文件"""
        selected_device = self.ui.deviceList.currentItem()
        if not selected_device:
            self.ui.statusLabel.setText("请先选择接收设备")
            return
            
        device_info = selected_device.data(Qt.UserRole)
        if not device_info:
            return
            
        # 在新线程中发送文件
        self.sender_thread = QThread()
        self.network_manager.moveToThread(self.sender_thread)
        self.sender_thread.started.connect(
            lambda: self.network_manager.send_file(
                device_info['ip'],
                self.ui.filePathEdit.text()
            )
        )
        self.sender_thread.start()
    
    def refresh_devices(self):
        """刷新设备列表"""
        self.ui.deviceList.clear()
        self.ui.statusLabel.setText("正在搜索设备...")
        
        # 在新线程中搜索设备
        self.discovery_thread = QThread()
        self.device_discovery.moveToThread(self.discovery_thread)
        self.discovery_thread.started.connect(self.device_discovery.discover)
        self.device_discovery.device_found.connect(self.add_device_to_list)
        self.discovery_thread.start()
    
    def add_device_to_list(self, device_info):
        """添加设备到列表"""
        from PyQt5.QtWidgets import QListWidgetItem
        item = QListWidgetItem(f"{device_info['name']} ({device_info['ip']})")
        item.setData(Qt.UserRole, device_info)
        self.ui.deviceList.addItem(item)

def main():
    app = QApplication(sys.argv)
    window = SendNowApp()
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main() 