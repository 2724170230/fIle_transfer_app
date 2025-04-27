"""
以下代码及注释全部由AI Agent生成
"""

"""
文件传输公共模块 (File Transfer Common Module)

该模块包含文件传输应用程序中服务器和客户端共享的常量、配置和工具。
内容：
- 网络传输参数设置（缓冲区大小、块大小、端口号）
- 文件传输状态常量定义
- 日志配置

作为应用程序传输模块的基础组件，确保客户端和服务器使用一致的配置和状态定义。
"""

import logging

# 默认传输参数
BUFFER_SIZE = 8192  # 8KB缓冲区
CHUNK_SIZE = 1024 * 1024  # 1MB块大小
SERVICE_PORT = 45679  # 默认传输服务端口

# 确保日志配置
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("FileTransfer")

class FileTransferStatus:
    """文件传输状态常量"""
    WAITING = "waiting"
    CONNECTING = "connecting"
    TRANSFERRING = "transferring"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled" 