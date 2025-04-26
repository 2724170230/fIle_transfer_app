import sys
import os
import logging
from PyQt5.QtWidgets import (QApplication, QMessageBox, QFileDialog, 
                            QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                            QPushButton, QRadioButton, QButtonGroup)
from PyQt5.QtCore import Qt, QTimer, QSize
from PyQt5.QtGui import QIcon, QFont

from localsend_ui_design import MainWindow, DeviceNameGenerator
from network_discovery import NetworkDiscovery
from file_transfer import FileTransferServer, FileTransferClient

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("SendNowApp")

def create_message_box(parent, icon, title, text):
    """创建高对比度的消息框"""
    msg_box = QMessageBox(parent)
    msg_box.setIcon(icon)
    msg_box.setWindowTitle(title)
    msg_box.setText(text)
    
    # 设置高对比度样式
    msg_box.setStyleSheet("""
        QMessageBox {
            background-color: #151829;
            color: #FFFFFF;
        }
        QLabel {
            color: #FFFFFF;
            font-size: 14px;
        }
        QPushButton {
            background-color: #2E355F;
            color: #FFFFFF;
            border: none;
            padding: 8px 15px;
            border-radius: 4px;
            font-size: 14px;
            min-width: 80px;
        }
        QPushButton:hover {
            background-color: #3A4273;
        }
    """)
    
    return msg_box

class FileReceiveDialog(QDialog):
    """文件接收确认对话框"""
    
    def __init__(self, file_info, parent=None):
        super().__init__(parent)
        self.file_info = file_info
        self.save_dir = None
        
        # 获取默认保存路径
        if parent and hasattr(parent, 'transfer_server'):
            self.default_save_dir = parent.transfer_server.save_dir
        else:
            self.default_save_dir = os.path.expanduser("~/Downloads/SendNow")
        
        self.setup_ui()
    
    def setup_ui(self):
        # 设置对话框属性
        self.setWindowTitle("文件接收请求")
        self.setMinimumWidth(400)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        
        # 设置高对比度样式
        self.setStyleSheet("""
            QDialog {
                background-color: #151829;
                color: #FFFFFF;
            }
            QLabel {
                color: #FFFFFF;
                font-size: 14px;
            }
            QRadioButton {
                color: #FFFFFF;
                font-size: 14px;
            }
            QPushButton {
                background-color: #2E355F;
                color: #FFFFFF;
                border: none;
                padding: 8px 15px;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #3A4273;
            }
            QPushButton#accept_button {
                background-color: #4F6FFF;
                font-weight: bold;
            }
            QPushButton#accept_button:hover {
                background-color: #5D7DFF;
            }
        """)
        
        # 主布局
        layout = QVBoxLayout(self)
        
        # 文件信息
        file_name = self.file_info.get('name', 'unknown_file')
        file_size = self.file_info.get('size', 0)
        sender = self.file_info.get('sender', 'unknown')
        
        # 格式化文件大小
        if file_size < 1024:
            size_str = f"{file_size} B"
        elif file_size < 1024 * 1024:
            size_str = f"{file_size / 1024:.1f} KB"
        else:
            size_str = f"{file_size / (1024 * 1024):.1f} MB"
        
        # 图标和标题
        title_layout = QHBoxLayout()
        
        title_icon = QLabel()
        title_icon.setPixmap(QIcon("icons/receive.svg").pixmap(QSize(32, 32)))
        title_layout.addWidget(title_icon)
        
        title_label = QLabel("收到文件接收请求")
        title_label.setFont(QFont("", 14, QFont.Bold))
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        
        layout.addLayout(title_layout)
        
        # 文件信息
        info_layout = QVBoxLayout()
        
        info_layout.addWidget(QLabel(f"文件名: {file_name}"))
        info_layout.addWidget(QLabel(f"大小: {size_str}"))
        info_layout.addWidget(QLabel(f"发送方: {sender}"))
        
        layout.addLayout(info_layout)
        layout.addSpacing(10)
        
        # 保存选项
        self.default_radio = QRadioButton(f"保存到默认位置: {self.default_save_dir}")
        self.custom_radio = QRadioButton("选择其他位置...")
        
        self.button_group = QButtonGroup(self)
        self.button_group.addButton(self.default_radio)
        self.button_group.addButton(self.custom_radio)
        self.default_radio.setChecked(True)
        
        # 连接自定义位置选择
        self.custom_radio.toggled.connect(self.on_custom_toggled)
        
        layout.addWidget(self.default_radio)
        layout.addWidget(self.custom_radio)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        self.reject_button = QPushButton("拒绝")
        self.reject_button.setAutoDefault(False)
        
        self.accept_button = QPushButton("接收文件")
        self.accept_button.setAutoDefault(True)
        self.accept_button.setDefault(True)
        self.accept_button.setObjectName("accept_button")  # 设置对象名以应用特定样式
        
        button_layout.addWidget(self.reject_button)
        button_layout.addStretch()
        button_layout.addWidget(self.accept_button)
        
        # 连接按钮信号
        self.reject_button.clicked.connect(self.reject)
        self.accept_button.clicked.connect(self.accept)
        
        layout.addSpacing(10)
        layout.addLayout(button_layout)
    
    def on_custom_toggled(self, checked):
        """用户切换到自定义保存位置"""
        if checked:
            dir_path = QFileDialog.getExistingDirectory(
                self, 
                "选择保存位置", 
                os.path.expanduser("~/Downloads")
            )
            
            if dir_path:
                self.save_dir = dir_path
                custom_text = f"选择其他位置... ({os.path.basename(dir_path)})"
                self.custom_radio.setText(custom_text)
            else:
                # 如果用户取消选择，切回默认选项
                self.default_radio.setChecked(True)

class SendNowApp(MainWindow):
    """SendNow应用主类，集成UI、网络发现和文件传输功能"""
    
    def __init__(self):
        super().__init__()
        
        # 设置窗口固定比例和初始大小
        self.resize(self.DEFAULT_WIDTH, self.DEFAULT_HEIGHT)
        
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
        self.transfer_server.pendingTransferRequest.connect(self.on_pending_transfer_request)
        
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
        # 发送离线通知，确保其他设备及时知道本设备已关闭
        if hasattr(self, 'network_discovery') and self.network_discovery:
            self.network_discovery.broadcast_offline()
            
        # 停止所有服务
        self.stop_services()
        event.accept()
    
    # ===== 网络发现事件处理 =====
    
    def on_device_discovered(self, device):
        """处理发现新设备事件"""
        logger.info(f"发现设备: {device.name} {device.device_id} ({device.ip})")
        
        # 添加到发送面板的设备列表，不显示IP地址
        item_text = f"{device.name} {device.device_id}"
        
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
            # 确保读取的设备数量是准确的
            device_count = self.sendPanel.deviceList.count()
            self.sendPanel.searchStatusLabel.setText(f"找到 {device_count} 个设备")
            logger.debug(f"UI更新设备数量: {device_count}")
    
    # ===== 接收服务器事件处理 =====
    
    def on_server_status_changed(self, status):
        """处理服务器状态变化事件"""
        logger.info(f"服务器状态: {status}")
        
        # 可以在这里更新UI状态
        pass
    
    def on_pending_transfer_request(self, file_info, client_socket):
        """处理等待确认的文件传输请求"""
        logger.info(f"收到待确认的文件传输请求: {file_info['name']} ({file_info['size']} 字节) 来自 {file_info['sender']}")
        
        # 跳转到接收面板
        self.receiveButton.setChecked(True)
        self.stack.setCurrentWidget(self.receivePanel)
        
        # 确保开启接收模式
        if self.receivePanel.offButton.isChecked():
            self.receivePanel.onButton.setChecked(True)
            self.on_receive_switch_toggled(True)
        
        # 显示文件接收确认对话框
        dialog = FileReceiveDialog(file_info, self)
        result = dialog.exec_()
        
        if result == QDialog.Accepted:
            # 用户接受文件传输
            save_dir = dialog.save_dir if dialog.save_dir else self.transfer_server.save_dir
            client_address = (file_info['sender'], 0)  # 端口为0，因为这里不重要
            
            # 获取客户端传过来的文件信息
            self.transfer_server.accept_transfer(client_socket, client_address, file_info, save_dir)
        else:
            # 用户拒绝文件传输
            self.transfer_server.reject_transfer(client_socket)
    
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
        
        # 安全断开可能存在的旧连接
        try:
            self.receivePanel.statusPanel.openFileButton.clicked.disconnect()
        except TypeError:
            # 如果没有连接，忽略错误
            pass
        
        try:
            self.receivePanel.statusPanel.openFolderButton.clicked.disconnect()
        except TypeError:
            # 如果没有连接，忽略错误
            pass
        
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
        msg_box = create_message_box(self, QMessageBox.Warning, "接收失败", f"文件 {filename} 接收失败:\n{error}")
        msg_box.exec_()
    
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
        
        # 显示发送进度条
        if not self.sendPanel.statusPanel.isVisible():
            self.sendPanel.statusPanel.showProgress(filename, mode="send")
        
        # 更新发送进度条
        self.sendPanel.statusPanel.progressBar.setValue(percent)
    
    def on_client_transfer_complete(self, filename, response):
        """处理客户端传输完成事件"""
        logger.info(f"文件发送完成: {filename} - {response}")
        
        # 更新发送面板状态
        self.sendPanel.statusPanel.showCompleted(filename, mode="send")
        
        # 创建一个计时器，在显示完成状态一段时间后自动隐藏
        QTimer.singleShot(3000, self.sendPanel.statusPanel.reset)
        
        # 重置发送按钮
        self.sendPanel.sendButton.setEnabled(True)
        self.sendPanel.sendButton.setText("发送文件")
        
        # 显示成功消息
        msg_box = create_message_box(self, QMessageBox.Information, "发送成功", f"文件 {filename} 已成功发送!")
        msg_box.exec_()
    
    def on_client_transfer_failed(self, filename, error):
        """处理客户端传输失败事件"""
        logger.error(f"文件发送失败: {filename} - {error}")
        
        # 更新发送面板状态
        if self.sendPanel.statusPanel.isVisible():
            self.sendPanel.statusPanel.statusLabel.setText(f"发送失败: {error}")
            self.sendPanel.statusPanel.actionsWidget.setVisible(False)
            
            # 创建一个计时器，在显示失败状态一段时间后自动隐藏
            QTimer.singleShot(3000, self.sendPanel.statusPanel.reset)
        
        # 重置发送按钮
        self.sendPanel.sendButton.setEnabled(True)
        self.sendPanel.sendButton.setText("发送文件")
        
        # 显示错误提示
        msg_box = create_message_box(self, QMessageBox.Warning, "发送失败", f"文件 {filename} 发送失败:\n{error}")
        msg_box.exec_()
    
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
            # 先发送离线通知，让其他设备立即知道本设备已关闭
            # 广播离线消息可以确保其他设备在3秒内看不到该设备
            if hasattr(self, 'network_discovery') and self.network_discovery:
                self.network_discovery.broadcast_offline()
            
            # 停止服务
            self.transfer_server.stop()
            # 完全停止网络发现服务（此处将会再次发送离线广播）
            self.network_discovery.stop()
            # 停止Logo动画
            self.receivePanel.logoWidget.setActive(False)
            # 重置状态面板（带淡出效果）
            self.receivePanel.resetStatusPanel()
    
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
            msg_box = create_message_box(self, QMessageBox.Warning, "发送失败", "请选择要发送的文件和目标设备")
            msg_box.exec_()
            return
        
        # 获取第一个选中的文件和设备
        file_item = selected_files[0]
        device_item = selected_devices[0]
        
        # 获取文件路径和设备信息
        file_path = file_item.data(Qt.UserRole)
        device_data = device_item.data(Qt.UserRole)
        
        if not file_path or not device_data or not os.path.exists(file_path):
            msg_box = create_message_box(self, QMessageBox.Warning, "发送失败", "文件不存在或设备信息无效")
            msg_box.exec_()
            return
        
        # 获取设备IP
        device_ip = device_data.get('ip')
        device_port = device_data.get('port', 45679)  # 默认端口
        
        if not device_ip:
            msg_box = create_message_box(self, QMessageBox.Warning, "发送失败", "设备IP地址无效")
            msg_box.exec_()
            return
        
        # 重置发送状态面板
        self.sendPanel.statusPanel.reset()
        
        # 开始发送文件
        logger.info(f"开始发送文件: {file_path} 到 {device_ip}:{device_port}")
        success = self.transfer_client.send_file(file_path, device_ip, device_port)
        
        if not success:
            msg_box = create_message_box(self, QMessageBox.Warning, "发送失败", "无法启动文件传输，请稍后再试")
            msg_box.exec_()
    
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
                # 更新设置面板中的显示
                self.settingsPanel.savePathEdit.setText(directory)
                logger.info(f"已更新默认保存路径: {directory}")
            else:
                # 显示错误信息
                msg_box = create_message_box(self, QMessageBox.Warning, "设置失败", f"无法设置保存目录: {directory}\n请确保该目录可写入。")
                msg_box.exec_()

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