#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SendNow - 局域网文件传输工具
"""

import sys
import os
import logging
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon

# 导入实现模块
import network
import transfer
import transfer_impl

# 应用UI扩展
from ui_extensions import apply_ui_extensions
apply_ui_extensions()

# 导入UI和控制器
from localsend_ui_design import MainWindow
from app_controller import AppController

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,  # 改为DEBUG级别以获取更多信息
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 添加文件日志处理器
log_file = os.path.join(os.path.expanduser("~"), "SendNow.log")
file_handler = logging.FileHandler(log_file)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logging.getLogger().addHandler(file_handler)

logger = logging.getLogger("SendNow")
logger.info(f"日志文件将保存到: {log_file}")

def main():
    """程序入口"""
    # 创建应用
    app = QApplication(sys.argv)
    
    # 设置应用图标
    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons", "app_icon.svg")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
    # 输出网络接口信息，帮助调试
    try:
        import socket
        import netifaces
        
        logger.info("=== 网络接口信息 ===")
        for iface in netifaces.interfaces():
            addrs = netifaces.ifaddresses(iface)
            if netifaces.AF_INET in addrs:
                for addr in addrs[netifaces.AF_INET]:
                    ip = addr['addr']
                    logger.info(f"接口: {iface}, IP: {ip}")
        logger.info("===================")
    except ImportError:
        logger.info("netifaces 模块未安装，无法显示详细网络接口信息")
        # 尝试显示基本信息
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            logger.info(f"主机IP: {s.getsockname()[0]}")
            s.close()
        except:
            logger.warning("无法获取主机IP信息")
    
    # 创建控制器
    controller = AppController()
    
    # 创建主窗口
    window = MainWindow()
    
    # 连接UI和控制器
    connect_ui_controller(window, controller)
    
    # 启动后端服务
    controller.start()
    
    # 显示窗口
    window.show()
    
    # 运行应用
    exit_code = app.exec_()
    
    # 停止后端服务
    controller.stop()
    
    # 退出
    sys.exit(exit_code)

def connect_ui_controller(window, controller):
    """连接UI和控制器"""
    # 使用新的方法设置控制器
    window.setAppController(controller)
    
    # 接收面板
    receive_panel = window.receivePanel
    
    # 设备发现事件
    controller.deviceFound.connect(receive_panel.onDeviceFound)
    controller.deviceLost.connect(receive_panel.onDeviceLost)
    
    # 传输请求事件
    controller.transferRequest.connect(receive_panel.onTransferRequest)
    
    # 传输进度事件
    controller.transferProgress.connect(receive_panel.onTransferProgress)
    
    # 传输完成事件
    controller.transferComplete.connect(receive_panel.onTransferComplete)
    
    # 传输错误事件
    controller.transferError.connect(receive_panel.onTransferError)
    
    # 发送面板
    send_panel = window.sendPanel
    
    # 传输进度事件
    controller.transferProgress.connect(send_panel.onTransferProgress)
    
    # 传输完成事件
    controller.transferComplete.connect(send_panel.onTransferComplete)
    
    # 传输错误事件
    controller.transferError.connect(send_panel.onTransferError)
    
    # 设置面板
    settings_panel = window.settingsPanel
    
    # 设置默认保存路径
    settings_panel.savePathEdit.setText(controller.get_save_directory())
    
    # 浏览按钮点击
    original_browse = settings_panel.browseSavePath
    
    def browse_and_set():
        """浏览并设置保存路径"""
        directory = original_browse()
        if directory and os.path.isdir(directory):
            if controller.set_save_directory(directory):
                settings_panel.savePathEdit.setText(directory)
    
    settings_panel.browseButton.clicked.disconnect()
    settings_panel.browseButton.clicked.connect(browse_and_set)
    
    # 更新设备名称和ID显示
    if hasattr(window, 'receivePanel') and hasattr(window.receivePanel, 'deviceNameLabel'):
        window.receivePanel.deviceNameLabel.setText(
            f"{controller.device_name} {controller.device_id}"
        )

if __name__ == "__main__":
    main() 