"""
属性修补模块，用于确保新旧代码的兼容性
"""

import logging
from transfer import TransferManager

logger = logging.getLogger("SendNow.PatchAttributes")

def patch_transfer_manager():
    """
    修补TransferManager类，添加与旧版本兼容的属性
    """
    # 添加@property装饰器实现的属性，作为sender_tasks和receiver_tasks的别名
    
    # 为TransferManager类添加send_tasks属性
    if not hasattr(TransferManager, 'send_tasks'):
        logger.info("添加 TransferManager.send_tasks 兼容属性")
        TransferManager.send_tasks = property(
            lambda self: self.sender_tasks,
            lambda self, value: setattr(self, 'sender_tasks', value)
        )
    
    # 为TransferManager类添加receive_tasks属性
    if not hasattr(TransferManager, 'receive_tasks'):
        logger.info("添加 TransferManager.receive_tasks 兼容属性")
        TransferManager.receive_tasks = property(
            lambda self: self.receiver_tasks,
            lambda self, value: setattr(self, 'receiver_tasks', value)
        )
        
    logger.info("TransferManager类属性修补完成")
    
    return True 