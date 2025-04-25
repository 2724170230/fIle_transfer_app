#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SendNow - UI扩展
为现有UI类添加处理后端事件的方法
"""

import os
import time
from PyQt5.QtCore import pyqtSlot, QTimer, Qt
from PyQt5.QtWidgets import QMessageBox, QListWidgetItem, QFileDialog

from network import DeviceInfo
from transfer import FileInfo, TransferTask

# ReceivePanel 扩展方法
def receive_onDeviceFound(self, device):
    """设备发现回调"""
    # 显示设备发现状态
    if hasattr(self, 'statusPanel'):
        self.statusPanel.setStatus(f"发现新设备: {device.device_name}")
    
    # 更新设备列表
    self.updateDeviceList()

def receive_onDeviceLost(self, device):
    """设备丢失回调"""
    self.updateDeviceList()

def receive_onTransferRequest(self, device, files):
    """传输请求回调"""
    if not files:
        return
    
    # 显示传输请求对话框
    message = f"{device.device_name} 想要发送 {len(files)} 个文件给你:\n\n"
    for file in files:
        message += f"- {file.file_name} ({file.get_formatted_size()})\n"
    message += "\n你要接受这些文件吗？"
    
    reply = QMessageBox.question(
        self,
        "传输请求",
        message,
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.No
    )
    
    if reply == QMessageBox.Yes:
        for file in files:
            # 接受传输
            self.controller.accept_transfer(file.transfer_id)
            
            # 更新状态面板
            self.statusPanel.showProgress(file.file_name)
            self.statusPanel.setStatus(f"正在接收: {file.file_name}")
    else:
        for file in files:
            # 拒绝传输
            self.controller.reject_transfer(file.transfer_id, "用户拒绝")

def receive_onTransferProgress(self, file_info, progress, speed):
    """传输进度回调"""
    # 只处理接收文件
    if file_info.transfer_id not in self.controller.get_receive_tasks():
        return
    
    # 确保 statusPanel 存在
    if not hasattr(self, 'statusPanel'):
        return
        
    # 更新进度条
    self.statusPanel.progressBar.setValue(int(progress))
    
    # 计算并显示传输速度
    speed_text = ""
    for unit in ['B/s', 'KB/s', 'MB/s', 'GB/s']:
        if speed < 1024.0:
            speed_text = f"{speed:.1f} {unit}"
            break
        speed /= 1024.0
    
    # 更新状态文本
    status_text = f"正在接收: {file_info.file_name} ({int(progress)}%, {speed_text})"
    self.statusPanel.setStatus(status_text)

def receive_onTransferComplete(self, file_info, is_sender):
    """传输完成回调"""
    # 只处理接收文件
    if is_sender:
        return
    
    # 完成接收
    self.statusPanel.progressBar.setValue(100)
    self.statusPanel.showCompleted(file_info.file_name)
    self.statusPanel.setStatus(f"接收完成: {file_info.file_name}")
    
    # 显示完成消息
    QMessageBox.information(
        self,
        "接收完成",
        f"文件 {file_info.file_name} 已接收完成\n保存在: {file_info.save_path}"
    )
    
    # 一段时间后重置状态面板
    QTimer.singleShot(3000, self.statusPanel.reset)

def receive_onTransferError(self, file_info, error_message):
    """传输错误回调"""
    # 只处理接收文件
    if file_info.transfer_id not in self.controller.get_receive_tasks():
        return
    
    # 显示错误消息
    self.statusPanel.setStatus(f"接收失败: {error_message}")
    
    # 显示错误对话框
    QMessageBox.warning(
        self,
        "接收错误",
        f"接收文件 {file_info.file_name} 失败\n错误: {error_message}"
    )
    
    # 一段时间后重置状态面板
    QTimer.singleShot(3000, self.statusPanel.reset)

def receive_updateDeviceList(self):
    """更新设备列表"""
    devices = self.controller.get_devices()
    device_count = len(devices)
    
    # 更新状态面板显示
    if hasattr(self, 'statusPanel'):
        if device_count == 0:
            self.statusPanel.setStatus("正在搜索设备...")
        else:
            self.statusPanel.setStatus(f"发现 {device_count} 台设备")
            
    # 注意：ReceivePanel 实际上没有设备列表组件
    # 未来如果添加了设备列表组件，可以在这里添加代码更新列表

# SendPanel 扩展方法
def send_onDeviceFound(self, device):
    """设备发现回调"""
    # 添加设备到列表
    if hasattr(self, 'deviceList') and self.deviceList is not None:
        # 检查是否已存在
        found = False
        for i in range(self.deviceList.count()):
            item = self.deviceList.item(i)
            if item.data(100) == device.device_id:  # 使用设备ID作为自定义数据
                found = True
                break
        
        if not found:
            # 添加新设备，确保显示格式与 DeviceInfo.__str__ 一致
            item = QListWidgetItem(f"{device.device_name} ({device.device_id}) - {device.ip_address}:{device.port}")
            item.setData(100, device.device_id)  # 存储设备ID
            self.deviceList.addItem(item)
            print(f"添加设备: {device.device_name} ({device.device_id}) @ {device.ip_address}")
    
    # 更新UI状态
    self.updateDeviceSearchStatus()

def send_onDeviceLost(self, device):
    """设备丢失回调"""
    # 从列表中移除设备
    if hasattr(self, 'deviceList') and self.deviceList is not None:
        for i in range(self.deviceList.count()):
            item = self.deviceList.item(i)
            if item.data(100) == device.device_id:
                self.deviceList.takeItem(i)
                break
    
    # 更新UI状态
    self.updateDeviceSearchStatus()

def send_onTransferProgress(self, file_info, progress, speed):
    """传输进度回调"""
    # 只处理发送文件
    tasks = self.controller.get_send_tasks()
    is_sending = False
    for task in tasks:
        if task.file_info.transfer_id == file_info.transfer_id:
            is_sending = True
            break
    
    if not is_sending:
        return
    
    # 更新进度条
    if hasattr(self, 'transferProgress'):
        self.transferProgress.setValue(int(progress))
    
    # 计算并显示传输速度
    speed_text = ""
    for unit in ['B/s', 'KB/s', 'MB/s', 'GB/s']:
        if speed < 1024.0:
            speed_text = f"{speed:.1f} {unit}"
            break
        speed /= 1024.0
    
    # 更新状态文本
    if hasattr(self, 'statusLabel'):
        self.statusLabel.setText(f"正在发送: {file_info.file_name} ({int(progress)}%, {speed_text})")

def send_onTransferComplete(self, file_info, is_sender):
    """传输完成回调"""
    # 只处理发送文件
    if not is_sender:
        return
    
    # 完成发送
    if hasattr(self, 'transferProgress'):
        self.transferProgress.setValue(100)
    
    if hasattr(self, 'statusLabel'):
        self.statusLabel.setText(f"发送完成: {file_info.file_name}")
    
    # 显示完成消息
    QMessageBox.information(
        self,
        "发送完成",
        f"文件 {file_info.file_name} 已发送完成"
    )
    
    # 一段时间后重置状态
    QTimer.singleShot(3000, self.resetTransferStatus)

def send_onTransferError(self, file_info, error_message):
    """传输错误回调"""
    # 只处理发送文件
    tasks = self.controller.get_send_tasks()
    is_sending = False
    for task in tasks:
        if task.file_info.transfer_id == file_info.transfer_id:
            is_sending = True
            break
    
    if not is_sending:
        return
    
    # 显示错误消息
    if hasattr(self, 'statusLabel'):
        self.statusLabel.setText(f"发送失败: {error_message}")
    
    # 显示错误对话框
    QMessageBox.warning(
        self,
        "发送错误",
        f"发送文件 {file_info.file_name} 失败\n错误: {error_message}"
    )
    
    # 一段时间后重置状态
    QTimer.singleShot(3000, self.resetTransferStatus)

def send_updateDeviceSearchStatus(self):
    """更新设备搜索状态"""
    if hasattr(self, 'deviceList') and self.deviceList is not None:
        device_count = self.deviceList.count()
        
        if device_count == 0:
            # 没有设备，显示搜索动画
            if hasattr(self, 'deviceSearchAnimation'):
                self.deviceSearchAnimation.setVisible(True)
            
            if hasattr(self, 'deviceStatusLabel'):
                self.deviceStatusLabel.setText("正在搜索设备...")
        else:
            # 有设备，隐藏搜索动画
            if hasattr(self, 'deviceSearchAnimation'):
                self.deviceSearchAnimation.setVisible(False)
            
            if hasattr(self, 'deviceStatusLabel'):
                self.deviceStatusLabel.setText(f"发现 {device_count} 台设备")

def send_resetTransferStatus(self):
    """重置传输状态"""
    if hasattr(self, 'transferProgress'):
        self.transferProgress.setValue(0)
    
    if hasattr(self, 'statusLabel'):
        self.statusLabel.setText("准备就绪")

def send_sendFilesToDevice(self):
    """发送文件到选中的设备"""
    # 检查是否选择了设备
    if not hasattr(self, 'deviceList') or self.deviceList is None or not self.deviceList.currentItem():
        QMessageBox.warning(self, "发送错误", "请先选择一个接收设备")
        return
    
    # 获取选中的设备ID - 修正为与 send_onDeviceFound 一致的数据键
    selected_item = self.deviceList.currentItem()
    device_id = selected_item.data(100)
    display_text = selected_item.text()
    
    # 添加调试信息
    print(f"选择的设备: {display_text}")
    print(f"选择的设备ID: {device_id}")
    
    # 获取设备列表以进行对比
    if hasattr(self, 'controller'):
        print("实际设备列表:")
        for dev in self.controller.get_devices():
            print(f"  - {dev.device_name} ({dev.device_id}) @ {dev.ip_address}")
    
    # 检查是否有文件要发送
    if not hasattr(self, 'fileList') or self.fileList is None or self.fileList.count() == 0:
        QMessageBox.warning(self, "发送错误", "请先添加要发送的文件")
        return
    
    # 获取文件列表
    file_paths = []
    for i in range(self.fileList.count()):
        item = self.fileList.item(i)
        if item.data(Qt.UserRole):
            path = item.data(Qt.UserRole)
            file_paths.append(path)
            print(f"添加文件: {path}")
    
    if not file_paths:
        QMessageBox.warning(self, "发送错误", "没有有效的文件可发送")
        return
    
    # 发送文件
    transfer_ids = self.controller.send_files(device_id, file_paths)
    
    if transfer_ids:
        print(f"成功创建传输任务: {transfer_ids}")
        if hasattr(self, 'statusLabel'):
            self.statusLabel.setText(f"正在发送 {len(transfer_ids)} 个文件...")
        
        if hasattr(self, 'transferProgress'):
            self.transferProgress.setValue(0)
    else:
        print("传输任务创建失败")
        QMessageBox.warning(self, "发送错误", "发送失败，请检查网络连接")

# 应用扩展方法到原始类
def apply_ui_extensions():
    """应用UI扩展方法到原始类"""
    from localsend_ui_design import ReceivePanel, SendPanel
    
    # 扩展接收面板
    ReceivePanel.onDeviceFound = receive_onDeviceFound
    ReceivePanel.onDeviceLost = receive_onDeviceLost
    ReceivePanel.onTransferRequest = receive_onTransferRequest
    ReceivePanel.onTransferProgress = receive_onTransferProgress
    ReceivePanel.onTransferComplete = receive_onTransferComplete
    ReceivePanel.onTransferError = receive_onTransferError
    ReceivePanel.updateDeviceList = receive_updateDeviceList
    
    # 扩展发送面板
    SendPanel.onDeviceFound = send_onDeviceFound
    SendPanel.onDeviceLost = send_onDeviceLost
    SendPanel.onTransferProgress = send_onTransferProgress
    SendPanel.onTransferComplete = send_onTransferComplete
    SendPanel.onTransferError = send_onTransferError
    SendPanel.updateDeviceSearchStatus = send_updateDeviceSearchStatus
    SendPanel.resetTransferStatus = send_resetTransferStatus
    SendPanel.sendFilesToDevice = send_sendFilesToDevice
    
    # 重新连接发送面板的发送按钮
    original_init = SendPanel.__init__
    
    def send_panel_init_wrapper(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        
        # 断开原来的模拟连接
        if hasattr(self, 'sendButton'):
            try:
                self.sendButton.clicked.disconnect()
            except:
                pass
            
            # 连接到实际的发送函数
            self.sendButton.clicked.connect(self.sendFilesToDevice)
    
    SendPanel.__init__ = send_panel_init_wrapper 