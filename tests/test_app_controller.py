import unittest
import sys
import os
import tempfile
from unittest.mock import MagicMock, patch

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app_controller import AppController
from network import DeviceInfo, NetworkManager
from transfer import FileInfo, TransferManager
from tests.common import DeviceNameGenerator

class TestAppController(unittest.TestCase):
    """测试应用控制器类"""
    
    @patch('app_controller.NetworkManager')
    @patch('app_controller.TransferManager')
    def setUp(self, mock_transfer_manager, mock_network_manager):
        """测试前的设置"""
        # 设置模拟行为
        self.mock_network_manager = mock_network_manager
        self.mock_transfer_manager = mock_transfer_manager
        
        # 创建临时文件用于测试
        self.temp_dir = tempfile.mkdtemp()
        self.test_file_path = os.path.join(self.temp_dir, "test_file.txt")
        with open(self.test_file_path, 'w') as f:
            f.write("测试文件内容")
        
        # 设置mock返回值
        instance = mock_transfer_manager.return_value
        instance.default_save_dir = self.temp_dir
        
        # 修补DeviceNameGenerator
        with patch('app_controller.DeviceNameGenerator', DeviceNameGenerator):
            self.app_controller = AppController()
    
    def tearDown(self):
        """测试后的清理"""
        # 删除临时目录
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_initialization(self):
        """测试初始化"""
        # 验证设备信息
        self.assertEqual(self.app_controller.device_name, "测试设备")
        self.assertEqual(self.app_controller.device_id, "test123")
        
        # 验证回调函数注册
        network_instance = self.mock_network_manager.return_value
        self.assertIsNotNone(network_instance.on_device_found)
        self.assertIsNotNone(network_instance.on_device_lost)
        
        transfer_instance = self.mock_transfer_manager.return_value
        self.assertIsNotNone(transfer_instance.on_transfer_request)
        self.assertIsNotNone(transfer_instance.on_file_progress)
        self.assertIsNotNone(transfer_instance.on_transfer_complete)
        self.assertIsNotNone(transfer_instance.on_transfer_error)
    
    def test_start_and_stop(self):
        """测试启动和停止"""
        # 启动服务
        self.app_controller.start()
        
        # 验证网络和传输管理器是否启动
        network_instance = self.mock_network_manager.return_value
        network_instance.start.assert_called_once()
        
        transfer_instance = self.mock_transfer_manager.return_value
        transfer_instance.start.assert_called_once()
        
        # 停止服务
        self.app_controller.stop()
        
        # 验证网络和传输管理器是否停止
        network_instance.stop.assert_called_once()
        transfer_instance.stop.assert_called_once()
    
    def test_save_directory(self):
        """测试保存目录设置"""
        # 获取保存目录
        save_dir = self.app_controller.get_save_directory()
        self.assertEqual(save_dir, self.temp_dir)
        
        # 设置保存目录
        new_dir = os.path.join(self.temp_dir, "new_dir")
        transfer_instance = self.mock_transfer_manager.return_value
        transfer_instance.set_save_directory.return_value = True
        
        result = self.app_controller.set_save_directory(new_dir)
        self.assertTrue(result)
        transfer_instance.set_save_directory.assert_called_once_with(new_dir)
    
    def test_auto_accept_transfers(self):
        """测试自动接受传输设置"""
        # 默认设置
        self.assertFalse(self.app_controller.auto_accept_transfers)
        
        # 更改设置
        self.app_controller.set_auto_accept_transfers(True)
        self.assertTrue(self.app_controller.auto_accept_transfers)
    
    def test_get_devices(self):
        """测试获取设备列表"""
        # 模拟设备列表
        devices = [
            DeviceInfo("dev1", "设备1", "192.168.1.100"),
            DeviceInfo("dev2", "设备2", "192.168.1.101")
        ]
        
        # 设置mock返回值
        network_instance = self.mock_network_manager.return_value
        network_instance.get_devices.return_value = devices
        
        # 获取设备列表
        result = self.app_controller.get_devices()
        
        # 验证结果
        self.assertEqual(result, devices)
        network_instance.get_devices.assert_called_once()
    
    def test_send_files(self):
        """测试发送文件"""
        # 模拟设备和文件
        device_id = "dev1"
        file_paths = [self.test_file_path]
        
        # 模拟设备列表
        devices = [DeviceInfo(device_id, "设备1", "192.168.1.100")]
        
        # 设置mock返回值
        network_instance = self.mock_network_manager.return_value
        network_instance.get_devices.return_value = devices
        
        transfer_instance = self.mock_transfer_manager.return_value
        transfer_instance.send_files.return_value = ["transfer1"]
        
        # 发送文件
        result = self.app_controller.send_files(device_id, file_paths)
        
        # 验证结果
        self.assertEqual(result, ["transfer1"])
        transfer_instance.send_files.assert_called_once()
    
    def test_transfer_operations(self):
        """测试传输操作"""
        transfer_id = "transfer1"
        
        # 配置mock返回值
        transfer_instance = self.mock_transfer_manager.return_value
        transfer_instance.accept_transfer.return_value = True
        transfer_instance.reject_transfer.return_value = True
        transfer_instance.pause_transfer.return_value = True
        transfer_instance.resume_transfer.return_value = True
        transfer_instance.cancel_transfer.return_value = True
        
        # 测试接受传输
        result = self.app_controller.accept_transfer(transfer_id)
        self.assertTrue(result)
        transfer_instance.accept_transfer.assert_called_once_with(transfer_id)
        
        # 测试拒绝传输
        result = self.app_controller.reject_transfer(transfer_id, "测试拒绝")
        self.assertTrue(result)
        transfer_instance.reject_transfer.assert_called_once_with(transfer_id, "测试拒绝")
        
        # 测试暂停传输
        result = self.app_controller.pause_transfer(transfer_id)
        self.assertTrue(result)
        transfer_instance.pause_transfer.assert_called_once_with(transfer_id)
        
        # 测试恢复传输
        result = self.app_controller.resume_transfer(transfer_id)
        self.assertTrue(result)
        transfer_instance.resume_transfer.assert_called_once_with(transfer_id)
        
        # 测试取消传输
        result = self.app_controller.cancel_transfer(transfer_id)
        self.assertTrue(result)
        transfer_instance.cancel_transfer.assert_called_once_with(transfer_id)
    
    def test_get_tasks(self):
        """测试获取任务列表"""
        # 配置mock返回值
        transfer_instance = self.mock_transfer_manager.return_value
        
        send_tasks = [MagicMock(), MagicMock()]
        receive_tasks = [MagicMock()]
        pending_transfers = [MagicMock(), MagicMock()]
        
        transfer_instance.get_send_tasks.return_value = send_tasks
        transfer_instance.get_receive_tasks.return_value = receive_tasks
        transfer_instance.get_pending_transfers.return_value = pending_transfers
        
        # 测试获取发送任务
        result = self.app_controller.get_send_tasks()
        self.assertEqual(result, send_tasks)
        transfer_instance.get_send_tasks.assert_called_once()
        
        # 测试获取接收任务
        result = self.app_controller.get_receive_tasks()
        self.assertEqual(result, receive_tasks)
        transfer_instance.get_receive_tasks.assert_called_once()
        
        # 测试获取等待处理的传输
        result = self.app_controller.get_pending_transfers()
        self.assertEqual(result, pending_transfers)
        transfer_instance.get_pending_transfers.assert_called_once()
    
    def test_callbacks(self):
        """测试回调函数"""
        # 创建测试对象
        device = DeviceInfo("dev1", "设备1", "192.168.1.100")
        file_info = FileInfo(file_name="test.txt", file_size=1000)
        
        # 测试设备发现回调
        with patch.object(self.app_controller, 'deviceFound') as mock_signal:
            self.app_controller._on_device_found(device)
            mock_signal.emit.assert_called_once_with(device)
            self.assertIn(device.device_id, self.app_controller.devices)
        
        # 测试设备丢失回调
        self.app_controller.devices[device.device_id] = device
        with patch.object(self.app_controller, 'deviceLost') as mock_signal:
            self.app_controller._on_device_lost(device)
            mock_signal.emit.assert_called_once_with(device)
            self.assertNotIn(device.device_id, self.app_controller.devices)
        
        # 测试传输请求回调
        with patch.object(self.app_controller, 'transferRequest') as mock_signal:
            files = [file_info]
            # 默认不自动接受
            result = self.app_controller._on_transfer_request(device, files)
            self.assertFalse(result)
            mock_signal.emit.assert_called_once_with(device, files)
            
            # 设置自动接受
            self.app_controller.auto_accept_transfers = True
            result = self.app_controller._on_transfer_request(device, files)
            self.assertTrue(result)
        
        # 测试文件进度回调
        with patch.object(self.app_controller, 'transferProgress') as mock_signal:
            self.app_controller._on_file_progress(file_info, 50.0, 1024.0)
            mock_signal.emit.assert_called_once_with(file_info, 50.0, 1024.0)
        
        # 测试传输完成回调
        with patch.object(self.app_controller, 'transferComplete') as mock_signal:
            self.app_controller._on_transfer_complete(file_info, True)
            mock_signal.emit.assert_called_once_with(file_info, True)
        
        # 测试传输错误回调
        with patch.object(self.app_controller, 'transferError') as mock_signal:
            self.app_controller._on_transfer_error(file_info, "测试错误")
            mock_signal.emit.assert_called_once_with(file_info, "测试错误")

if __name__ == '__main__':
    unittest.main() 