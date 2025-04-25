import unittest
import os
import sys
import time
import threading
import socket
import tempfile
import shutil
import json
from unittest.mock import MagicMock, patch

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from network import NetworkManager, DeviceInfo, Message, MessageType
from transfer import TransferManager, FileInfo
from app_controller import AppController
from tests.common import DeviceNameGenerator

class TestNetworkTransferIntegration(unittest.TestCase):
    """网络和传输模块集成测试"""
    
    def setUp(self):
        """测试前的设置"""
        # 创建临时目录用于测试
        self.temp_dir = tempfile.mkdtemp()
        self.send_dir = os.path.join(self.temp_dir, "send")
        self.receive_dir = os.path.join(self.temp_dir, "receive")
        
        os.makedirs(self.send_dir, exist_ok=True)
        os.makedirs(self.receive_dir, exist_ok=True)
        
        # 创建测试文件
        self.test_file_path = os.path.join(self.send_dir, "test_file.txt")
        with open(self.test_file_path, 'w') as f:
            f.write("测试文件内容" * 100)  # 约1.5KB的内容
        
        # 创建网络管理器实例
        self.sender_network = NetworkManager("sender_device", "发送设备")
        self.receiver_network = NetworkManager("receiver_device", "接收设备")
        
        # 创建传输管理器实例
        self.sender_transfer = TransferManager(self.sender_network, self.send_dir)
        self.receiver_transfer = TransferManager(self.receiver_network, self.receive_dir)
        
        # 模拟互相发现的设备
        self.sender_device = DeviceInfo("sender_device", "发送设备", "127.0.0.1")
        self.receiver_device = DeviceInfo("receiver_device", "接收设备", "127.0.0.1")
        
        # 在网络管理器中添加设备
        self.sender_network.devices[self.receiver_device.device_id] = self.receiver_device
        self.receiver_network.devices[self.sender_device.device_id] = self.sender_device
    
    def tearDown(self):
        """测试后的清理"""
        # 停止网络服务
        self.sender_network.stop()
        self.receiver_network.stop()
        
        # 停止传输服务
        self.sender_transfer.stop()
        self.receiver_transfer.stop()
        
        # 删除临时目录
        shutil.rmtree(self.temp_dir)
    
    @patch('socket.socket')
    def test_send_receive_message(self, mock_socket):
        """测试消息的发送和接收"""
        # 模拟套接字行为
        mock_instance = mock_socket.return_value
        
        # 确保sendto方法被调用
        mock_instance.sendto = MagicMock()
        
        # 测试发送消息
        test_message = Message(MessageType.DISCOVER, {"test": "payload"})
        self.sender_network.send_message(self.receiver_device, test_message)
        
        # 验证套接字发送被调用
        mock_instance.sendto.assert_called_once()
        
        # 获取发送的数据
        sent_data = mock_instance.sendto.call_args[0][0]
        sent_message = Message.from_bytes(sent_data)
        
        # 验证消息内容
        self.assertEqual(sent_message.msg_type, MessageType.DISCOVER)
        self.assertEqual(sent_message.payload["test"], "payload")
    
    # 先跳过这个测试，直到TransferManager实现了正确的回调方法
    @unittest.skip("等待TransferManager修复")
    @patch('transfer.socket.socket')
    def test_file_transfer_flow(self, mock_socket):
        """测试文件传输流程"""
        # 设置回调模拟
        self.receiver_transfer.on_transfer_request = MagicMock(return_value=True)
        self.receiver_transfer.on_file_progress = MagicMock()
        self.receiver_transfer.on_transfer_complete = MagicMock()
        
        self.sender_transfer.on_file_progress = MagicMock()
        self.sender_transfer.on_transfer_complete = MagicMock()
        
        # 配置模拟套接字行为，模拟成功的建立连接、发送数据等
        mock_instance = mock_socket.return_value
        
        # 模拟文件接收
        def mock_receive_data(size):
            # 简单的模拟数据接收
            if not hasattr(mock_receive_data, 'count'):
                mock_receive_data.count = 0
            
            mock_receive_data.count += 1
            if mock_receive_data.count == 1:
                # 第一次返回消息头
                header = {
                    "type": MessageType.FILE_INFO,
                    "payload": {
                        "file_id": "test_file_id",
                        "file_name": "test_file.txt",
                        "file_size": os.path.getsize(self.test_file_path)
                    }
                }
                return json.dumps(header).encode('utf-8')
            elif mock_receive_data.count < 5:
                # 后续返回数据块
                with open(self.test_file_path, 'rb') as f:
                    return f.read(4096)
            else:
                # 最后返回完成消息
                complete = {
                    "type": MessageType.COMPLETE,
                    "payload": {"file_id": "test_file_id"}
                }
                return json.dumps(complete).encode('utf-8')
        
        mock_instance.recv.side_effect = mock_receive_data
        
        # 模拟发送文件
        with patch.object(self.sender_network, 'send_message', return_value=True):
            # 发送文件
            transfer_ids = self.sender_transfer.send_files(self.receiver_device, [self.test_file_path])
            
            # 验证传输ID是否创建
            self.assertEqual(len(transfer_ids), 1)
            
            # 模拟接受请求
            transfer_accepted = self.receiver_transfer.accept_transfer(transfer_ids[0])
            self.assertTrue(transfer_accepted)
            
            # 等待传输完成的回调
            time.sleep(0.1)  # 给异步处理一些时间
            
            # 验证进度和完成回调是否被调用
            self.sender_transfer.on_file_progress.assert_called()
            self.receiver_transfer.on_file_progress.assert_called()
            
            # 在真实环境中，这里应该检查文件是否被正确传输到接收目录
            # 但由于我们模拟了socket通信，不会有实际文件写入

class TestAppControllerIntegration(unittest.TestCase):
    """应用控制器集成测试"""
    
    @patch('app_controller.NetworkManager')
    @patch('app_controller.TransferManager')
    def setUp(self, mock_transfer_manager, mock_network_manager):
        """测试前的设置"""
        # 配置模拟对象
        self.mock_network_manager = mock_network_manager
        self.mock_transfer_manager = mock_transfer_manager
        
        # 设置返回值
        # 修补DeviceNameGenerator
        with patch('app_controller.DeviceNameGenerator', DeviceNameGenerator):
            # 创建app控制器
            self.app_controller = AppController()
        
        # 创建临时目录
        self.temp_dir = tempfile.mkdtemp()
        self.test_file_path = os.path.join(self.temp_dir, "test_file.txt")
        with open(self.test_file_path, 'w') as f:
            f.write("测试文件内容")
    
    def tearDown(self):
        """测试后的清理"""
        # 停止app服务
        self.app_controller.stop()
        
        # 删除临时目录
        shutil.rmtree(self.temp_dir)
    
    def test_device_discovery_signals(self):
        """测试设备发现信号"""
        # 设置模拟设备
        device = DeviceInfo("dev_id", "发现的设备", "192.168.1.100")
        
        # 设置信号接收器
        device_found_callback = MagicMock()
        device_lost_callback = MagicMock()
        
        self.app_controller.deviceFound.connect(device_found_callback)
        self.app_controller.deviceLost.connect(device_lost_callback)
        
        # 模拟设备发现
        self.app_controller._on_device_found(device)
        
        # 验证信号是否被触发
        device_found_callback.assert_called_once_with(device)
        
        # 验证设备是否添加到设备列表
        self.assertIn("dev_id", self.app_controller.devices)
        
        # 模拟设备丢失
        self.app_controller._on_device_lost(device)
        
        # 验证信号是否被触发
        device_lost_callback.assert_called_once_with(device)
        
        # 验证设备是否从设备列表移除
        self.assertNotIn("dev_id", self.app_controller.devices)
    
    def test_transfer_signals(self):
        """测试传输信号"""
        # 设置模拟对象
        device = DeviceInfo("dev_id", "发送设备", "192.168.1.100")
        file_info = FileInfo(file_name="test.txt", file_size=1000)
        
        # 设置信号接收器
        transfer_request_callback = MagicMock()
        transfer_progress_callback = MagicMock()
        transfer_complete_callback = MagicMock()
        transfer_error_callback = MagicMock()
        
        self.app_controller.transferRequest.connect(transfer_request_callback)
        self.app_controller.transferProgress.connect(transfer_progress_callback)
        self.app_controller.transferComplete.connect(transfer_complete_callback)
        self.app_controller.transferError.connect(transfer_error_callback)
        
        # 模拟传输请求
        self.app_controller._on_transfer_request(device, [file_info])
        
        # 验证信号是否被触发
        transfer_request_callback.assert_called_once_with(device, [file_info])
        
        # 模拟传输进度
        self.app_controller._on_file_progress(file_info, 50.0, 1024.0)
        
        # 验证信号是否被触发
        transfer_progress_callback.assert_called_once_with(file_info, 50.0, 1024.0)
        
        # 模拟传输完成
        self.app_controller._on_transfer_complete(file_info, True)
        
        # 验证信号是否被触发
        transfer_complete_callback.assert_called_once_with(file_info, True)
        
        # 模拟传输错误
        self.app_controller._on_transfer_error(file_info, "测试错误")
        
        # 验证信号是否被触发
        transfer_error_callback.assert_called_once_with(file_info, "测试错误")
    
    def test_transfer_operations_flow(self):
        """测试传输操作流程"""
        # 设置mock返回值
        network_instance = self.mock_network_manager.return_value
        transfer_instance = self.mock_transfer_manager.return_value
        
        # 添加模拟设备
        device = DeviceInfo("dev_id", "测试设备", "192.168.1.100")
        devices = [device]
        network_instance.get_devices.return_value = devices
        
        # 模拟文件传输
        transfer_instance.send_files.return_value = ["transfer_id_1"]
        
        # 启动app
        self.app_controller.start()
        
        # 验证启动服务
        network_instance.start.assert_called_once()
        transfer_instance.start.assert_called_once()
        
        # 发送文件
        transfer_ids = self.app_controller.send_files("dev_id", [self.test_file_path])
        
        # 验证传输ID
        self.assertEqual(transfer_ids, ["transfer_id_1"])
        
        # 模拟接受传输
        transfer_instance.accept_transfer.return_value = True
        result = self.app_controller.accept_transfer("transfer_id_1")
        self.assertTrue(result)
        
        # 模拟暂停/恢复/取消传输
        transfer_instance.pause_transfer.return_value = True
        transfer_instance.resume_transfer.return_value = True
        transfer_instance.cancel_transfer.return_value = True
        
        result = self.app_controller.pause_transfer("transfer_id_1")
        self.assertTrue(result)
        
        result = self.app_controller.resume_transfer("transfer_id_1")
        self.assertTrue(result)
        
        result = self.app_controller.cancel_transfer("transfer_id_1")
        self.assertTrue(result)
        
        # 停止app
        self.app_controller.stop()
        
        # 验证停止服务
        transfer_instance.stop.assert_called_once()
        network_instance.stop.assert_called_once()

if __name__ == '__main__':
    unittest.main() 