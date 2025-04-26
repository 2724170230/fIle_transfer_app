import sys
import os
import logging
from PyQt5.QtWidgets import QApplication, QMessageBox, QFileDialog
from PyQt5.QtCore import Qt, QTimer

from localsend_ui_design import MainWindow, DeviceNameGenerator
from network_discovery import NetworkDiscovery
from file_transfer import FileTransferServer, FileTransferClient

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("SendNowApp")

class SendNowApp(MainWindow):
    """SendNow应用主类，集成UI、网络发现和文件传输功能"""
    
    def __init__(self):
        super().__init__()
        
        # 获取或生成设备名称和ID
        self.device_name, self.device_id = DeviceNameGenerator.get_persistent_name_and_id()
        logger.info(f"设备信息: {self.device_name} {self.device_id}")
        
        # 初始化网络发现模块
        self.network_discovery = NetworkDiscovery(self.device_name, self.device_id)
        
        # 初始化文件传输服务器
        self.transfer_server = FileTransferServer()
        
        # 初始化文件传输客户端
        self.transfer_client = FileTransferClient()
        
        # 连接信号与槽
        self.connect_signals()
        
        # 设置设置面板中的保存路径
        self.settingsPanel.savePathEdit.setText(self.transfer_server.save_dir)
        
        # 启动服务
        self.start_services()
    
    def connect_signals(self):
        """连接所有的信号和槽"""
        # 连接网络发现信号
        self.network_discovery.deviceDiscovered.connect(self.on_device_discovered)
        self.network_discovery.deviceLost.connect(self.on_device_lost)
        self.network_discovery.statusChanged.connect(self.on_discovery_status_changed)
        
        # 连接文件传输服务器信号
        self.transfer_server.statusChanged.connect(self.on_server_status_changed)
        self.transfer_server.transferRequest.connect(self.on_transfer_request)
        self.transfer_server.transferProgress.connect(self.on_server_progress)
        self.transfer_server.transferComplete.connect(self.on_server_transfer_complete)
        self.transfer_server.transferFailed.connect(self.on_server_transfer_failed)
        
        # 连接文件传输客户端信号
        self.transfer_client.statusChanged.connect(self.on_client_status_changed)
        self.transfer_client.transferProgress.connect(self.on_client_progress)
        self.transfer_client.transferComplete.connect(self.on_client_transfer_complete)
        self.transfer_client.transferFailed.connect(self.on_client_transfer_failed)
        
        # 连接UI事件
        self.receivePanel.onButton.toggled.connect(self.on_receive_switch_toggled)
        self.receivePanel.offButton.toggled.connect(self.on_receive_switch_toggled)
        
        self.sendPanel.deviceList.itemClicked.connect(self.on_device_selected)
        self.sendPanel.sendButton.clicked.connect(self.on_send_button_clicked)
        self.sendPanel.fileList.itemSelectionChanged.connect(self.on_file_selection_changed)
        
        self.settingsPanel.browseButton.clicked.connect(self.on_browse_save_dir)
    
    def start_services(self):
        """启动服务"""
        # 启动网络发现服务
        self.network_discovery.start()
        
        # 启动文件传输服务器
        self.transfer_server.start()
        
        # 更新接收面板显示
        self.receivePanel.device_name = self.device_name
        self.receivePanel.device_id = self.device_id
    
    def stop_services(self):
        """停止服务"""
        # 停止网络发现服务
        self.network_discovery.stop()
        
        # 停止文件传输服务器
        self.transfer_server.stop()
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        # 停止所有服务
        self.stop_services()
        event.accept()
    
    # ===== 网络发现事件处理 =====
    
    def on_device_discovered(self, device):
        """处理发现新设备事件"""
        logger.info(f"发现设备: {device.name} {device.device_id} ({device.ip})")
        
        # 添加到发送面板的设备列表
        item_text = f"{device.name} {device.device_id} ({device.ip})"
        
        # 检查设备是否已在列表中
        found = False
        for i in range(self.sendPanel.deviceList.count()):
            item = self.sendPanel.deviceList.item(i)
            device_data = item.data(Qt.UserRole)
            if device_data and device_data.get('id') == device.device_id:
                # 更新现有设备信息
                device_data = device.to_dict()
                item.setData(Qt.UserRole, device_data)
                item.setText(item_text)
                found = True
                break
        
        # 如果是新设备，添加到列表
        if not found:
            from PyQt5.QtWidgets import QListWidgetItem
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, device.to_dict())
            self.sendPanel.deviceList.addItem(item)
        
        # 更新设备数量状态
        device_count = self.sendPanel.deviceList.count()
        self.sendPanel.searchStatusLabel.setText(f"找到 {device_count} 个设备")
    
    def on_device_lost(self, device):
        """处理设备离线事件"""
        logger.info(f"设备离线: {device.name} {device.device_id}")
        
        # 从发送面板的设备列表中移除
        for i in range(self.sendPanel.deviceList.count()):
            item = self.sendPanel.deviceList.item(i)
            device_data = item.data(Qt.UserRole)
            if device_data and device_data.get('id') == device.device_id:
                self.sendPanel.deviceList.takeItem(i)
                break
        
        # 更新设备数量状态
        device_count = self.sendPanel.deviceList.count()
        self.sendPanel.searchStatusLabel.setText(f"找到 {device_count} 个设备")
    
    def on_discovery_status_changed(self, status):
        """处理网络发现状态变化事件"""
        logger.info(f"网络发现状态: {status}")
        
        # 更新发送面板的搜索状态
        if "正在搜索" in status:
            self.sendPanel.searchStatusLabel.setText("正在搜索附近设备...")
        else:
            device_count = self.sendPanel.deviceList.count()
            self.sendPanel.searchStatusLabel.setText(f"找到 {device_count} 个设备")
    
    # ===== 接收服务器事件处理 =====
    
    def on_server_status_changed(self, status):
        """处理服务器状态变化事件"""
        logger.info(f"服务器状态: {status}")
        
        # 可以在这里更新UI状态
        pass
    
    def on_transfer_request(self, info):
        """处理传输请求事件"""
        logger.info(f"收到文件传输请求: {info['name']} ({info['size']} 字节) 来自 {info['sender']}")
        
        # 更新接收面板状态
        self.receivePanel.statusPanel.showProgress(info['name'])
    
    def on_server_progress(self, filename, current, total):
        """处理服务器传输进度事件"""
        # 计算百分比
        percent = (current * 100) // total if total > 0 else 0
        logger.debug(f"接收进度: {filename} - {current}/{total} 字节 ({percent}%)")
        
        # 更新接收面板进度条
        self.receivePanel.statusPanel.progressBar.setValue(percent)
    
    def on_server_transfer_complete(self, filename, path):
        """处理服务器传输完成事件"""
        logger.info(f"文件接收完成: {filename} -> {path}")
        
        # 更新接收面板状态
        self.receivePanel.statusPanel.showCompleted(filename)
        
        # 设置打开文件和文件夹按钮动作
        self.receivePanel.statusPanel.openFileButton.clicked.disconnect()
        self.receivePanel.statusPanel.openFolderButton.clicked.disconnect()
        
        # 连接新的动作
        self.receivePanel.statusPanel.openFileButton.clicked.connect(
            lambda: os.startfile(path) if os.name == 'nt' else os.system(f"open '{path}'")
        )
        
        folder_path = os.path.dirname(path)
        self.receivePanel.statusPanel.openFolderButton.clicked.connect(
            lambda: os.startfile(folder_path) if os.name == 'nt' else os.system(f"open '{folder_path}'")
        )
    
    def on_server_transfer_failed(self, filename, error):
        """处理服务器传输失败事件"""
        logger.error(f"文件接收失败: {filename} - {error}")
        
        # 更新接收面板状态
        self.receivePanel.statusPanel.statusLabel.setText(f"接收失败: {error}")
        self.receivePanel.statusPanel.actionsWidget.setVisible(False)
        
        # 显示错误提示
        QMessageBox.warning(self, "接收失败", f"文件 {filename} 接收失败:\n{error}")
    
    # ===== 发送客户端事件处理 =====
    
    def on_client_status_changed(self, status):
        """处理客户端状态变化事件"""
        logger.info(f"客户端状态: {status}")
        
        # 更新发送按钮状态
        if "正在连接" in status or "正在发送" in status:
            self.sendPanel.sendButton.setEnabled(False)
            self.sendPanel.sendButton.setText("发送中...")
        elif "传输已完成" in status:
            self.sendPanel.sendButton.setEnabled(True)
            self.sendPanel.sendButton.setText("发送文件")
    
    def on_client_progress(self, filename, current, total):
        """处理客户端传输进度事件"""
        # 计算百分比
        percent = (current * 100) // total if total > 0 else 0
        logger.debug(f"发送进度: {filename} - {current}/{total} 字节 ({percent}%)")
        
        # 这里可以添加发送进度UI更新
        # 当前UI没有发送进度条，可以考虑在发送按钮上显示进度文本
        self.sendPanel.sendButton.setText(f"发送中... {percent}%")
    
    def on_client_transfer_complete(self, filename, response):
        """处理客户端传输完成事件"""
        logger.info(f"文件发送完成: {filename} - {response}")
        
        # 重置发送按钮
        self.sendPanel.sendButton.setEnabled(True)
        self.sendPanel.sendButton.setText("发送文件")
        
        # 显示成功消息
        QMessageBox.information(self, "发送成功", f"文件 {filename} 已成功发送!")
    
    def on_client_transfer_failed(self, filename, error):
        """处理客户端传输失败事件"""
        logger.error(f"文件发送失败: {filename} - {error}")
        
        # 重置发送按钮
        self.sendPanel.sendButton.setEnabled(True)
        self.sendPanel.sendButton.setText("发送文件")
        
        # 显示错误提示
        QMessageBox.warning(self, "发送失败", f"文件 {filename} 发送失败:\n{error}")
    
    # ===== UI事件处理 =====
    
    def on_receive_switch_toggled(self, checked):
        """处理接收开关切换事件"""
        sender = self.sender()
        
        if checked and sender == self.receivePanel.onButton:
            logger.info("接收模式: 开启")
            # 重启服务
            self.transfer_server.start()
            self.network_discovery.start()
            # 启动Logo动画
            self.receivePanel.logoWidget.setActive(True)
        
        elif checked and sender == self.receivePanel.offButton:
            logger.info("接收模式: 关闭")
            # 停止服务
            self.transfer_server.stop()
            # 停止Logo动画
            self.receivePanel.logoWidget.setActive(False)
    
    def on_device_selected(self, item):
        """处理设备列表项选择事件"""
        # 获取设备信息
        device_data = item.data(Qt.UserRole)
        if device_data:
            logger.info(f"选择设备: {device_data.get('name')} {device_data.get('id')}")
            
            # 更新发送按钮状态
            has_files = self.sendPanel.fileList.count() > 0
            has_selected_files = len(self.sendPanel.fileList.selectedItems()) > 0
            self.sendPanel.sendButton.setEnabled(has_files and has_selected_files)
    
    def on_file_selection_changed(self):
        """处理文件选择变化事件"""
        # 检查是否有文件和设备被选中
        has_selected_files = len(self.sendPanel.fileList.selectedItems()) > 0
        has_selected_device = len(self.sendPanel.deviceList.selectedItems()) > 0
        
        # 更新发送按钮状态
        self.sendPanel.sendButton.setEnabled(has_selected_files and has_selected_device)
    
    def on_send_button_clicked(self):
        """处理发送按钮点击事件"""
        # 获取选中的文件和设备
        selected_files = self.sendPanel.fileList.selectedItems()
        selected_devices = self.sendPanel.deviceList.selectedItems()
        
        if not selected_files or not selected_devices:
            QMessageBox.warning(self, "发送失败", "请选择要发送的文件和目标设备")
            return
        
        # 获取第一个选中的文件和设备
        file_item = selected_files[0]
        device_item = selected_devices[0]
        
        # 获取文件路径和设备信息
        file_path = file_item.data(Qt.UserRole)
        device_data = device_item.data(Qt.UserRole)
        
        if not file_path or not device_data or not os.path.exists(file_path):
            QMessageBox.warning(self, "发送失败", "文件不存在或设备信息无效")
            return
        
        # 获取设备IP
        device_ip = device_data.get('ip')
        device_port = device_data.get('port', 45679)  # 默认端口
        
        if not device_ip:
            QMessageBox.warning(self, "发送失败", "设备IP地址无效")
            return
        
        # 开始发送文件
        logger.info(f"开始发送文件: {file_path} 到 {device_ip}:{device_port}")
        success = self.transfer_client.send_file(file_path, device_ip, device_port)
        
        if not success:
            QMessageBox.warning(self, "发送失败", "无法启动文件传输，请稍后再试")
    
    def on_browse_save_dir(self):
        """处理浏览保存目录按钮点击事件"""
        # 打开文件夹选择对话框
        directory = QFileDialog.getExistingDirectory(
            self,
            "选择文件保存目录",
            self.transfer_server.save_dir
        )
        
        if directory:
            # 设置新的保存目录
            success = self.transfer_server.set_save_directory(directory)
            
            if success:
                # 更新设置面板显示
                self.settingsPanel.savePathEdit.setText(directory)
                logger.info(f"文件保存目录已更改为: {directory}")
            else:
                QMessageBox.warning(self, "设置失败", "无法设置保存目录，请确保目录存在且可写")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 检查必要的库是否安装
    try:
        import netifaces
    except ImportError:
        QMessageBox.critical(None, "缺少依赖", "缺少必要的库: netifaces\n请使用pip安装: pip install netifaces")
        sys.exit(1)
    
    # 创建并显示应用窗口
    window = SendNowApp()
    window.show()
    
    sys.exit(app.exec_()) 