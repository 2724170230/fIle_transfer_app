import sys
import os
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

from localsend_ui_design import MainWindow
from network_manager import NetworkManager
from device_discovery import DeviceDiscovery

class App:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.window = MainWindow()
        
        # 初始化网络管理器
        self.network_manager = NetworkManager(
            receive_callback=self.file_received,
            progress_callback=self.update_progress
        )
        
        # 初始化设备发现
        self.device_discovery = DeviceDiscovery(
            device_found_callback=self.device_found
        )
        
        # 设置设备信息
        device_name, device_id = self.window.receivePanel.device_name, self.window.receivePanel.device_id
        self.device_discovery.set_device_info(device_name, device_id)
        
        # 将网络管理器传递给UI组件
        self.window.sendPanel.set_network_manager(self.network_manager)
        self.window.receivePanel.set_network_manager(self.network_manager)
        
        # 连接UI信号到功能
        self.connect_signals()
        
        # 创建必要的目录
        self.create_directories()
        
        # 启动服务
        self.start_services()
    
    def create_directories(self):
        """创建必要的目录"""
        # 创建icons目录
        os.makedirs("icons", exist_ok=True)
        
        # 创建默认下载目录
        os.makedirs(os.path.expanduser("~/Downloads"), exist_ok=True)
    
    def connect_signals(self):
        """连接UI信号到功能"""
        # 连接发送按钮
        self.window.sendPanel.sendButton.clicked.connect(
            self.window.sendPanel.sendFileToDevice
        )
        
    def start_services(self):
        """启动服务"""
        # 启动设备发现
        self.device_discovery.start_discovery()
    
    def file_received(self, file_path):
        """文件接收完成回调"""
        self.window.receivePanel.fileReceived(file_path)
    
    def update_progress(self, filename, progress):
        """更新传输进度回调"""
        # 根据当前显示的面板决定通知哪个
        if self.window.stack.currentWidget() == self.window.receivePanel:
            self.window.receivePanel.updateProgress(filename, progress)
    
    def device_found(self, device):
        """发现新设备回调"""
        # 更新设备列表
        self.window.sendPanel.add_device_to_list(device)
    
    def run(self):
        """运行应用程序"""
        self.window.show()
        return self.app.exec_()

if __name__ == "__main__":
    app = App()
    sys.exit(app.run()) 