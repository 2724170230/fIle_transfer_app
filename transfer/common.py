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