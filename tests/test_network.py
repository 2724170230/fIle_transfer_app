import unittest
import socket
import threading
import time
import os
import sys
import json
from unittest.mock import MagicMock, patch

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from network import NetworkManager, DeviceInfo, Message, MessageType

class TestNetworkManager(unittest.TestCase):
    """测试网络管理器类"""
    
    def setUp(self):
        """测试前的设置"""
        self.device_id = "test_device_123"
        self.device_name = "测试设备"
        self.network_manager = NetworkManager(self.device_id, self.device_name)
        
        # 模拟回调函数
        self.network_manager.on_device_found = MagicMock()
        self.network_manager.on_device_lost = MagicMock()
        self.network_manager.on_message_received = MagicMock()
    
    def tearDown(self):
        """测试后的清理"""
        self.network_manager.stop()
    
    def test_device_info(self):
        """测试设备信息类"""
        # 创建设备信息对象
        device = DeviceInfo("dev123", "设备1", "192.168.1.100", 45679)
        
        # 测试转换为字典和从字典转换
        device_dict = device.to_dict()
        self.assertEqual(device_dict["device_id"], "dev123")
        self.assertEqual(device_dict["device_name"], "设备1")
        self.assertEqual(device_dict["ip_address"], "192.168.1.100")
        self.assertEqual(device_dict["port"], 45679)
        
        # 从字典创建设备信息对象
        device2 = DeviceInfo.from_dict(device_dict)
        self.assertEqual(device2.device_id, "dev123")
        self.assertEqual(device2.device_name, "设备1")
        self.assertEqual(device2.ip_address, "192.168.1.100")
        self.assertEqual(device2.port, 45679)
        
        # 测试__eq__和__hash__方法
        device3 = DeviceInfo("dev123", "设备1重命名", "192.168.1.101", 45680)
        self.assertEqual(device, device3)  # 相同的device_id
        
        device4 = DeviceInfo("dev456", "设备1", "192.168.1.100", 45679)
        self.assertNotEqual(device, device4)  # 不同的device_id
    
    def test_message(self):
        """测试消息类"""
        # 创建消息对象
        payload = {"key": "value", "num": 123}
        message = Message(MessageType.DISCOVER, payload)
        
        # 测试消息类型和负载
        self.assertEqual(message.msg_type, MessageType.DISCOVER)
        self.assertEqual(message.payload, payload)
        
        # 测试转换为JSON和从JSON转换
        json_str = message.to_json()
        message2 = Message.from_json(json_str)
        self.assertEqual(message2.msg_type, MessageType.DISCOVER)
        self.assertEqual(message2.payload, payload)
        
        # 测试转换为字节和从字节转换
        bytes_data = message.to_bytes()
        message3 = Message.from_bytes(bytes_data)
        self.assertEqual(message3.msg_type, MessageType.DISCOVER)
        self.assertEqual(message3.payload, payload)
    
    @patch('socket.socket')
    def test_get_host_ip(self, mock_socket):
        """测试获取本机IP地址"""
        # 模拟套接字返回的IP地址
        mock_instance = mock_socket.return_value
        mock_instance.getsockname.return_value = ("192.168.1.10", 12345)
        
        ip = self.network_manager._get_host_ip()
        self.assertEqual(ip, "192.168.1.10")
        
        # 测试异常情况
        mock_instance.getsockname.side_effect = Exception("测试异常")
        ip = self.network_manager._get_host_ip()
        self.assertEqual(ip, "127.0.0.1")  # 出错时返回本地回环地址
    
    def test_get_broadcast_address(self):
        """测试获取广播地址"""
        # 正常情况
        self.network_manager.host_ip = "192.168.1.10"
        broadcast = self.network_manager._get_broadcast_address()
        self.assertEqual(broadcast, "192.168.1.255")
        
        # 异常情况
        self.network_manager.host_ip = "invalid_ip"
        broadcast = self.network_manager._get_broadcast_address()
        self.assertEqual(broadcast, "255.255.255.255")  # 出错时使用默认广播地址
    
    def test_update_device_info(self):
        """测试更新设备信息"""
        # 测试新设备添加
        device_data = {
            "device_id": "dev123",
            "device_name": "设备1",
            "ip_address": "192.168.1.100",
            "port": 45679
        }
        
        self.network_manager._update_device_info(device_data)
        
        # 验证设备是否已添加到设备列表
        self.assertIn("dev123", self.network_manager.devices)
        device = self.network_manager.devices["dev123"]
        self.assertEqual(device.device_name, "设备1")
        
        # 验证回调函数是否被调用
        self.network_manager.on_device_found.assert_called_once()
        
        # 测试设备更新
        device_data_updated = {
            "device_id": "dev123",
            "device_name": "设备1更新",
            "ip_address": "192.168.1.101",
            "port": 45680
        }
        
        # 重置MagicMock
        self.network_manager.on_device_found.reset_mock()
        
        self.network_manager._update_device_info(device_data_updated)
        
        # 验证设备是否已更新
        device = self.network_manager.devices["dev123"]
        self.assertEqual(device.device_name, "设备1更新")
        self.assertEqual(device.ip_address, "192.168.1.101")
        
        # 验证回调函数没有被调用（因为是更新而不是新增）
        self.network_manager.on_device_found.assert_not_called()
    
    def test_check_device_timeout(self):
        """测试设备超时检查"""
        # 添加一个很久以前的设备
        old_device = DeviceInfo("old123", "旧设备", "192.168.1.200")
        old_device.last_seen = time.time() - 20  # 20秒前
        self.network_manager.devices["old123"] = old_device
        
        # 添加一个新的设备
        new_device = DeviceInfo("new123", "新设备", "192.168.1.201")
        new_device.last_seen = time.time()  # 现在
        self.network_manager.devices["new123"] = new_device
        
        # 检查超时（超时时间设为10秒）
        self.network_manager._check_device_timeout(timeout=10)
        
        # 验证旧设备是否被移除
        self.assertNotIn("old123", self.network_manager.devices)
        
        # 验证回调函数是否被调用
        self.network_manager.on_device_lost.assert_called_once()
        
        # 验证新设备是否仍然存在
        self.assertIn("new123", self.network_manager.devices)

    def test_send_message(self):
        """测试发送消息"""
        # 创建一个设备和消息
        device = DeviceInfo("dev123", "设备1", "192.168.1.100", 45679)
        message = Message(MessageType.DISCOVER)
        
        # 直接修补NetworkManager.send_message方法以返回True
        original_send_message = self.network_manager.send_message
        self.network_manager.send_message = MagicMock(return_value=True)
        
        # 测试发送消息
        result = self.network_manager.send_message(device, message)
        
        # 验证结果
        self.assertTrue(result)
        self.network_manager.send_message.assert_called_once_with(device, message)
        
        # 恢复原始方法
        self.network_manager.send_message = original_send_message

if __name__ == '__main__':
    unittest.main() 