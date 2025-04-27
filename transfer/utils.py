"""
以下代码及注释全部由AI Agent生成
"""

"""
文件传输工具函数模块 (File Transfer Utilities Module)

该模块提供文件传输过程中需要的各种辅助函数和工具。
主要功能：
- 文件哈希计算（MD5）用于文件完整性校验
- 文件大小格式化显示（B/KB/MB）
- 目录操作辅助（创建目录、检查可写性）

作为应用程序传输模块的辅助组件，提供各种常用功能，避免代码重复，提高可维护性。
"""

import os
import hashlib

def compute_file_hash(file_path):
    """计算文件的MD5哈希值"""
    hash_obj = hashlib.md5()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            hash_obj.update(chunk)
    return hash_obj.hexdigest()

def format_file_size(size_bytes):
    """格式化文件大小显示"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"

def ensure_directory_exists(directory):
    """确保目录存在，如果不存在则创建"""
    os.makedirs(directory, exist_ok=True)
    
def is_directory_writable(directory):
    """测试目录是否可写"""
    try:
        test_file = os.path.join(directory, ".test_write")
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)
        return True
    except Exception:
        return False 