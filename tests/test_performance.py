import unittest
import os
import sys
import time
import threading
import tempfile
import shutil
import random
import logging

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from network import NetworkManager, DeviceInfo
from transfer import TransferManager, FileInfo, TransferTask

# 禁用测试期间的日志输出
logging.disable(logging.CRITICAL)

class TestTransferPerformance(unittest.TestCase):
    """传输性能测试"""
    
    def setUp(self):
        """测试前的设置"""
        # 创建临时目录用于测试
        self.temp_dir = tempfile.mkdtemp()
        self.send_dir = os.path.join(self.temp_dir, "send")
        self.receive_dir = os.path.join(self.temp_dir, "receive")
        
        os.makedirs(self.send_dir, exist_ok=True)
        os.makedirs(self.receive_dir, exist_ok=True)
        
        # 创建测试文件
        self.create_test_files()
        
        # 创建网络管理器实例（使用真实网络但本地地址）
        self.sender_network = NetworkManager("sender_device", "发送设备")
        
        # 创建传输管理器实例
        self.sender_transfer = TransferManager(self.sender_network, self.send_dir)
        
        # 在网络管理器中添加本地设备模拟接收方
        self.receiver_device = DeviceInfo("receiver_device", "接收设备", "127.0.0.1")
        self.sender_network.devices[self.receiver_device.device_id] = self.receiver_device
    
    def tearDown(self):
        """测试后的清理"""
        # 停止网络服务
        self.sender_network.stop()
        
        # 停止传输服务
        self.sender_transfer.stop()
        
        # 删除临时目录
        shutil.rmtree(self.temp_dir)
    
    def create_test_files(self):
        """创建不同大小的测试文件"""
        # 小文件 (10KB)
        self.small_file = os.path.join(self.send_dir, "small_file.dat")
        self.create_random_file(self.small_file, 10 * 1024)
        
        # 中等文件 (1MB)
        self.medium_file = os.path.join(self.send_dir, "medium_file.dat")
        self.create_random_file(self.medium_file, 1 * 1024 * 1024)
        
        # 大文件 (10MB) - 通常情况下应足够测试传输性能
        self.large_file = os.path.join(self.send_dir, "large_file.dat")
        self.create_random_file(self.large_file, 10 * 1024 * 1024)
    
    def create_random_file(self, path, size):
        """创建指定大小的随机内容文件"""
        with open(path, 'wb') as f:
            # 每次写入1MB以避免内存问题
            chunk_size = 1024 * 1024
            while size > 0:
                write_size = min(chunk_size, size)
                f.write(os.urandom(write_size))
                size -= write_size
    
    def test_file_info_performance(self):
        """测试FileInfo性能"""
        # 测试大文件的哈希计算性能
        start_time = time.time()
        file_info = FileInfo(file_path=self.large_file)
        file_info.calculate_hash()
        hash_time = time.time() - start_time
        
        print(f"\n大文件哈希计算时间: {hash_time:.2f}秒")
        
        # 对于10MB的文件，哈希计算应该在合理的时间内完成（取决于硬件）
        # 通常应该在1秒内完成
        self.assertLess(hash_time, 2.0, "大文件哈希计算时间过长")
    
    def test_transfer_task_chunk_calculation(self):
        """测试传输任务块计算性能"""
        # 测试不同块大小对大文件的影响
        chunk_sizes = [
            1024,       # 1KB - 非常小
            64 * 1024,  # 64KB - 默认
            256 * 1024, # 256KB - 较大
            1024 * 1024 # 1MB - 很大
        ]
        
        file_info = FileInfo(file_path=self.large_file)
        file_size = file_info.file_size
        
        print(f"\n文件大小: {file_size / (1024 * 1024):.2f} MB")
        
        for chunk_size in chunk_sizes:
            # 设置块大小
            file_info.chunk_size = chunk_size
            
            # 创建传输任务
            task = TransferTask(file_info, self.receiver_device, is_sender=True)
            
            # 计算总块数
            total_chunks = task._calculate_total_chunks()
            
            print(f"块大小: {chunk_size / 1024:.1f} KB, 总块数: {total_chunks}")
            
            # 验证块数计算正确
            expected_chunks = (file_size + chunk_size - 1) // chunk_size
            self.assertEqual(total_chunks, expected_chunks)
    
    def test_multi_file_prep_performance(self):
        """测试多文件准备性能"""
        # 创建多个小文件用于测试
        num_files = 100
        files = []
        
        for i in range(num_files):
            path = os.path.join(self.send_dir, f"multi_file_{i}.dat")
            self.create_random_file(path, 10 * 1024)  # 10KB的文件
            files.append(path)
        
        # 测试批量创建FileInfo对象的性能
        start_time = time.time()
        file_infos = []
        
        for file_path in files:
            file_info = FileInfo(file_path=file_path)
            file_infos.append(file_info)
        
        prep_time = time.time() - start_time
        
        print(f"\n准备{num_files}个文件的时间: {prep_time:.2f}秒")
        
        # 准备100个小文件应该在合理的时间内完成
        # 通常应该在1秒内完成
        self.assertLess(prep_time, 1.0, "多文件准备时间过长")
    
    def test_multi_threading_performance(self):
        """测试多线程性能"""
        # 模拟同时处理多个传输任务
        num_tasks = 10
        all_tasks = []
        results = [False] * num_tasks
        
        def process_task(task_index):
            """处理单个任务的线程函数"""
            # 模拟处理时间
            time.sleep(0.1)
            
            # 设置结果
            results[task_index] = True
        
        # 创建并启动多个线程
        start_time = time.time()
        threads = []
        
        for i in range(num_tasks):
            thread = threading.Thread(target=process_task, args=(i,))
            threads.append(thread)
            thread.start()
        
        # 等待所有线程完成
        for thread in threads:
            thread.join()
        
        multi_thread_time = time.time() - start_time
        
        print(f"\n多线程处理{num_tasks}个任务的时间: {multi_thread_time:.2f}秒")
        
        # 验证所有任务都已处理
        self.assertTrue(all(results))
        
        # 如果是真正的并行处理，时间应该接近于单个任务的处理时间
        # 允许一些额外开销
        self.assertLess(multi_thread_time, 0.3, "多线程处理效率不佳")
    
    def test_buffer_performance(self):
        """测试不同缓冲区大小的性能"""
        # 创建一个测试文件
        test_file = os.path.join(self.send_dir, "buffer_test.dat")
        file_size = 5 * 1024 * 1024  # 5MB
        self.create_random_file(test_file, file_size)
        
        # 测试不同缓冲区大小的读写性能
        buffer_sizes = [
            4 * 1024,     # 4KB
            16 * 1024,    # 16KB
            64 * 1024,    # 64KB
            256 * 1024,   # 256KB
            1024 * 1024   # 1MB
        ]
        
        print("\n不同缓冲区大小的读取性能:")
        
        for buffer_size in buffer_sizes:
            # 测试读取性能
            start_time = time.time()
            bytes_read = 0
            
            with open(test_file, 'rb') as f:
                while True:
                    data = f.read(buffer_size)
                    if not data:
                        break
                    bytes_read += len(data)
            
            read_time = time.time() - start_time
            
            # 验证读取了全部数据
            self.assertEqual(bytes_read, file_size)
            
            print(f"缓冲区大小: {buffer_size / 1024:.1f} KB, 读取时间: {read_time:.4f}秒, " 
                  f"速度: {file_size / read_time / (1024 * 1024):.2f} MB/s")
        
        # 测试写入性能
        print("\n不同缓冲区大小的写入性能:")
        
        for buffer_size in buffer_sizes:
            output_file = os.path.join(self.receive_dir, f"buffer_out_{buffer_size}.dat")
            
            # 测试写入性能
            start_time = time.time()
            bytes_written = 0
            
            with open(test_file, 'rb') as f_in, open(output_file, 'wb') as f_out:
                while bytes_written < file_size:
                    read_size = min(buffer_size, file_size - bytes_written)
                    data = f_in.read(read_size)
                    if not data:
                        break
                    f_out.write(data)
                    bytes_written += len(data)
            
            write_time = time.time() - start_time
            
            # 验证写入了全部数据
            self.assertEqual(bytes_written, file_size)
            
            print(f"缓冲区大小: {buffer_size / 1024:.1f} KB, 写入时间: {write_time:.4f}秒, "
                  f"速度: {file_size / write_time / (1024 * 1024):.2f} MB/s")

if __name__ == '__main__':
    unittest.main() 