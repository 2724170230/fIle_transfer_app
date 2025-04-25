"""
属性修补模块，用于确保新旧代码的兼容性
"""

import logging
import inspect
import uuid
from transfer import TransferManager
from message import MessageType, Message

logger = logging.getLogger("SendNow.PatchAttributes")

def patch_transfer_manager(tm):
    """
    给TransferManager打补丁，以便兼容新旧版本之间的差异
    
    Args:
        tm: TransferManager实例
        
    Returns:
        TransferManager: 打过补丁的TransferManager实例
    """
    logger.info("开始给TransferManager打补丁...")
    
    # 为兼容性设置一些属性
    if not hasattr(tm, "send_tasks"):
        tm.send_tasks = {}
        logger.info("添加send_tasks属性")
        
    if not hasattr(tm, "receive_tasks"):
        tm.receive_tasks = {}
        logger.info("添加receive_tasks属性")
    
    # 保存原始方法
    original_handle_message = tm._handle_network_message
    original_handle_transfer_request = tm._handle_transfer_request
    
    # 添加包装方法以确保兼容性
    def wrapped_handle_message(message, addr):
        """包装_handle_network_message方法以确保payload中包含兼容性字段"""
        if message and hasattr(message, 'payload') and message.payload:
            # 确保文件信息同时存在于file_infos和files字段中
            if message.msg_type == MessageType.TRANSFER_REQUEST:
                payload = message.payload
                if "file_infos" in payload and "files" not in payload:
                    payload["files"] = payload["file_infos"]
                    logger.info("从file_infos复制到files字段以保持兼容性")
                elif "files" in payload and "file_infos" not in payload:
                    payload["file_infos"] = payload["files"]
                    logger.info("从files复制到file_infos字段以保持兼容性")
        
        # 调用原始方法
        return original_handle_message(message, addr)
    
    def wrapped_handle_transfer_request(payload, addr):
        """包装_handle_transfer_request方法以确保payload中包含兼容性字段"""
        if payload:
            # 确保同时存在file_infos和files字段
            if "file_infos" in payload and "files" not in payload:
                payload["files"] = payload["file_infos"]
                logger.info("从file_infos复制到files字段以保持兼容性")
            elif "files" in payload and "file_infos" not in payload:
                payload["file_infos"] = payload["files"]
                logger.info("从files复制到file_infos字段以保持兼容性")
            
            # 确保存在transfer_id字段
            if "transfer_id" not in payload:
                payload["transfer_id"] = str(uuid.uuid4())
                logger.info("添加缺失的transfer_id字段")
        
        # 调用原始方法
        return original_handle_transfer_request(payload, addr)
    
    # 替换方法
    tm._handle_network_message = wrapped_handle_message
    tm._handle_transfer_request = wrapped_handle_transfer_request
    
    logger.info("TransferManager补丁应用完成")
    
    return tm 