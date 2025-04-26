import socket
import threading
import json
import time
import hashlib
import random
import os
import ipaddress
import logging
from queue import Queue
from typing import Dict, List, Tuple, Optional, Callable, Any

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("SendNow.Network")

# 网络常量
DISCOVER_PORT = 45678  # 设备发现端口
TRANSFER_PORT = 45679  # 文件传输端口
BUFFER_SIZE = 8192     # 默认缓冲区大小
DISCOVER_INTERVAL = 5  # 设备发现广播间隔(秒)
SOCKET_TIMEOUT = 10    # 套接字超时时间(秒)

# 消息类型
class MessageType:
    DISCOVER = "DISCOVER"               # 设备发现广播
    DISCOVER_RESPONSE = "DISCOVER_RESP" # 设备发现响应
    TRANSFER_REQUEST = "TRANSFER_REQ"   # 传输请求
    TRANSFER_ACCEPT = "TRANSFER_ACCEPT" # 接受传输
    TRANSFER_REJECT = "TRANSFER_REJECT" # 拒绝传输
    FILE_INFO = "FILE_INFO"             # 文件信息
    DATA = "DATA"                       # 数据包
    ACK = "ACK"                         # 确认包
    COMPLETE = "COMPLETE"               # 传输完成
    ERROR = "ERROR"                     # 错误信息
    PAUSE = "PAUSE"                     # 暂停传输
    RESUME = "RESUME"                   # 继续传输
    CANCEL = "CANCEL"                   # 取消传输
    FILE_HEADER_VERIFY = "FILE_HEADER_VERIFY"  # 文件头部验证请求
    FILE_HEADER_RESPONSE = "FILE_HEADER_RESP"  # 文件头部验证响应

class DeviceInfo:
    """设备信息类"""
    
    def __init__(self, device_id: str, device_name: str, ip_address: str, port: int = TRANSFER_PORT):
        self.device_id = device_id
        self.device_name = device_name
        self.ip_address = ip_address
        self.port = port
        self.last_seen = time.time()
    
    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "device_id": self.device_id,
            "device_name": self.device_name,
            "ip_address": self.ip_address,
            "port": self.port
        }
    
    @staticmethod
    def from_dict(data: dict) -> 'DeviceInfo':
        """从字典创建设备信息对象"""
        return DeviceInfo(
            data["device_id"],
            data["device_name"],
            data["ip_address"],
            data.get("port", TRANSFER_PORT)
        )
    
    def __str__(self) -> str:
        return f"{self.device_name} ({self.device_id}) - {self.ip_address}:{self.port}"
    
    def __eq__(self, other):
        if not isinstance(other, DeviceInfo):
            return False
        return self.device_id == other.device_id
    
    def __hash__(self):
        return hash(self.device_id)

class Message:
    """消息基类，定义协议格式"""
    
    def __init__(self, msg_type: str, payload: dict = None, message_id: str = None):
        self.msg_type = msg_type
        self.payload = payload or {}
        # 如果没有提供消息ID，生成一个新的
        self.message_id = message_id or hashlib.md5(f"{time.time()}{random.random()}".encode()).hexdigest()[:8]
        self.timestamp = time.time()
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        message_dict = {
            "type": self.msg_type,
            "id": self.message_id,
            "timestamp": self.timestamp,
            "payload": self.payload
        }
        return json.dumps(message_dict)
    
    def to_bytes(self) -> bytes:
        """转换为字节流"""
        json_str = self.to_json()
        return json_str.encode('utf-8')
    
    @staticmethod
    def from_json(json_str: str) -> 'Message':
        """从JSON字符串创建消息对象"""
        try:
            data = json.loads(json_str)
            return Message(
                data["type"],
                data.get("payload", {}),
                data.get("id", None)
            )
        except Exception as e:
            logger.error(f"解析消息失败: {e}")
            return None
    
    @staticmethod
    def from_bytes(data: bytes) -> 'Message':
        """从字节流创建消息对象"""
        try:
            json_str = data.decode('utf-8')
            return Message.from_json(json_str)
        except Exception as e:
            logger.error(f"从字节流创建消息失败: {e}")
            return None

class NetworkManager:
    """网络管理器，处理设备发现和基础网络通信"""
    
    def __init__(self, device_id: str, device_name: str):
        self.device_id = device_id
        self.device_name = device_name
        self.devices: Dict[str, DeviceInfo] = {}  # 已发现的设备
        
        # 线程和控制标志
        self.discover_thread = None
        self.listen_thread = None
        self.running = False
        
        # 回调函数
        self.on_device_found: Optional[Callable[[DeviceInfo], None]] = None
        self.on_device_lost: Optional[Callable[[DeviceInfo], None]] = None
        self.on_message_received: Optional[Callable[[Message, Tuple[str, int]], None]] = None
        
        # 获取主机信息
        self.host_ip = self._get_host_ip()
        
        logger.info(f"初始化网络管理器: 设备ID={device_id}, 设备名称={device_name}, IP={self.host_ip}")
    
    def _get_host_ip(self) -> str:
        """获取本机在局域网中的IP地址"""
        try:
            # 创建一个UDP套接字
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # 连接到一个外部地址，实际上不会发送数据
            s.connect(("8.8.8.8", 80))
            # 获取分配的IP地址
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception as e:
            logger.error(f"获取本机IP地址失败: {e}")
            # 如果出错，返回本地回环地址
            return "127.0.0.1"
    
    def _get_broadcast_address(self) -> str:
        """获取广播地址"""
        try:
            # 尝试获取子网掩码以计算广播地址
            ip = ipaddress.IPv4Address(self.host_ip)
            # 默认使用 /24 子网，即 255.255.255.0 的掩码
            network = ipaddress.IPv4Network(f"{ip}/24", strict=False)
            broadcast = str(network.broadcast_address)
            logger.info(f"计算得到的广播地址: {broadcast}")
            return broadcast
        except Exception as e:
            logger.warning(f"获取广播地址失败: {e}, 使用默认广播地址")
            # 如果无法获取，使用255.255.255.255
            return "255.255.255.255"
    
    def start(self):
        """启动网络服务"""
        if self.running:
            logger.warning("网络服务已经在运行")
            return
        
        self.running = True
        
        # 启动设备发现线程
        self.discover_thread = threading.Thread(target=self._discover_loop)
        self.discover_thread.daemon = True
        self.discover_thread.start()
        
        # 启动消息监听线程
        self.listen_thread = threading.Thread(target=self._listen_loop)
        self.listen_thread.daemon = True
        self.listen_thread.start()
        
        logger.info("网络服务已启动")
    
    def stop(self):
        """停止网络服务"""
        if not self.running:
            return
        
        self.running = False
        
        # 等待线程结束
        if self.discover_thread:
            self.discover_thread.join(1.0)
        
        if self.listen_thread:
            self.listen_thread.join(1.0)
        
        logger.info("网络服务已停止")
    
    def _discover_loop(self):
        """设备发现循环，发送广播寻找设备"""
        # 使用多个套接字来提高广播成功率
        broadcast_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        broadcast_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        broadcast_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # 设置TTL
        broadcast_sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 32)
        broadcast_sock.settimeout(SOCKET_TIMEOUT)
        
        # 用于发送直接消息的套接字
        direct_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        direct_sock.settimeout(SOCKET_TIMEOUT)
        
        while self.running:
            try:
                # 创建发现消息
                device_info = {
                    "device_id": self.device_id,
                    "device_name": self.device_name,
                    "ip_address": self.host_ip,
                    "port": TRANSFER_PORT
                }
                
                message = Message(MessageType.DISCOVER, device_info)
                message_bytes = message.to_bytes()
                
                # 发送广播到255.255.255.255
                try:
                    broadcast_sock.sendto(message_bytes, ("255.255.255.255", DISCOVER_PORT))
                    logger.debug("发送设备发现广播到 255.255.255.255:%d", DISCOVER_PORT)
                except Exception as e:
                    logger.warning(f"发送全局广播失败: {e}")
                
                # 发送到计算出的广播地址
                broadcast_addr = self._get_broadcast_address()
                if broadcast_addr != "255.255.255.255":
                    try:
                        broadcast_sock.sendto(message_bytes, (broadcast_addr, DISCOVER_PORT))
                        logger.debug(f"发送设备发现广播到 {broadcast_addr}:{DISCOVER_PORT}")
                    except Exception as e:
                        logger.warning(f"发送本地广播失败: {e}")
                
                # 直接发送给已知设备（确保通信稳定性）
                for device_id, device in self.devices.items():
                    try:
                        direct_sock.sendto(message_bytes, (device.ip_address, DISCOVER_PORT))
                        logger.debug(f"直接发送设备发现消息到 {device.ip_address}:{DISCOVER_PORT}")
                    except Exception as e:
                        logger.warning(f"直接发送给设备 {device.device_name} 失败: {e}")
                
                # 检查设备超时
                self._check_device_timeout()
                
                # 等待一段时间再发送下一次广播
                time.sleep(DISCOVER_INTERVAL)
                
            except Exception as e:
                logger.error(f"设备发现过程中出错: {e}")
                time.sleep(1)  # 出错后等待一会儿再重试
        
        broadcast_sock.close()
        direct_sock.close()
    
    def _listen_loop(self):
        """消息监听循环，接收广播和其他消息"""
        # 创建UDP套接字用于接收广播
        discover_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        discover_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # 允许接收广播消息
        discover_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        discover_sock.settimeout(1.0)  # 短超时以便能响应running状态变化
        
        try:
            # 注意：这里绑定空字符串表示监听所有网络接口
            discover_sock.bind(("0.0.0.0", DISCOVER_PORT))
            logger.info(f"开始监听设备发现消息端口 {DISCOVER_PORT}，监听所有网络接口")
            
            while self.running:
                try:
                    data, addr = discover_sock.recvfrom(BUFFER_SIZE)
                    logger.info(f"接收到来自 {addr[0]}:{addr[1]} 的消息")
                    self._handle_discover_message(data, addr)
                except socket.timeout:
                    continue
                except Exception as e:
                    logger.error(f"接收广播消息出错: {e}")
        
        except Exception as e:
            logger.error(f"创建广播监听套接字失败: {e}")
        
        finally:
            discover_sock.close()
    
    def _handle_discover_message(self, data: bytes, addr: Tuple[str, int]):
        """处理设备发现消息"""
        message = Message.from_bytes(data)
        if not message:
            logger.warning(f"无法解析来自 {addr[0]}:{addr[1]} 的消息")
            return
        
        source_ip = addr[0]
        logger.debug(f"处理来自 {source_ip}:{addr[1]} 的 {message.msg_type} 消息")
        
        if message.msg_type == MessageType.DISCOVER:
            # 收到发现请求，回复设备信息
            if message.payload.get("device_id") != self.device_id:  # 忽略自己的广播
                logger.info(f"收到来自 {source_ip} 的设备发现请求: {message.payload.get('device_name', '未知设备')}")
                self._update_device_info(message.payload)
                
                # 更新payload中的host_ip为真实有效的IP
                # 如果payload中的IP与发送消息的源IP不同，可能表明发送方使用了与实际通信路径不同的IP
                sender_info = message.payload.copy()
                if sender_info.get("ip_address") != source_ip:
                    logger.info(f"发送方声明IP ({sender_info.get('ip_address')}) 与实际源IP ({source_ip}) 不同，使用源IP")
                    sender_info["ip_address"] = source_ip
                
                # 发送响应 - 使用对方的实际IP地址
                response_info = {
                    "device_id": self.device_id,
                    "device_name": self.device_name,
                    "ip_address": self.host_ip,
                    "port": TRANSFER_PORT
                }
                
                response = Message(MessageType.DISCOVER_RESPONSE, response_info)
                
                try:
                    response_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    response_sock.settimeout(SOCKET_TIMEOUT)
                    # 直接发送到对方的源IP和端口
                    response_sock.sendto(response.to_bytes(), (source_ip, DISCOVER_PORT))
                    logger.info(f"已向 {source_ip} 发送设备发现响应")
                    response_sock.close()
                except Exception as e:
                    logger.error(f"发送设备发现响应失败: {e}")
        
        elif message.msg_type == MessageType.DISCOVER_RESPONSE:
            # 收到发现响应，更新设备信息
            if message.payload.get("device_id") != self.device_id:  # 忽略自己的响应
                logger.info(f"收到来自 {source_ip} 的设备发现响应: {message.payload.get('device_name', '未知设备')}")
                
                # 更新payload中的IP为实际源IP
                sender_info = message.payload.copy()
                if sender_info.get("ip_address") != source_ip:
                    logger.info(f"响应方声明IP ({sender_info.get('ip_address')}) 与实际源IP ({source_ip}) 不同，使用源IP")
                    sender_info["ip_address"] = source_ip
                
                self._update_device_info(sender_info)
        
        # 其他类型的消息传递给回调处理
        if self.on_message_received:
            self.on_message_received(message, addr)
    
    def _update_device_info(self, device_data: dict):
        """更新设备信息"""
        device_id = device_data.get("device_id")
        if not device_id or device_id == self.device_id:
            return  # 忽略不完整数据或自己的数据
        
        device_info = DeviceInfo.from_dict(device_data)
        is_new_device = device_id not in self.devices
        
        # 更新或添加设备信息
        self.devices[device_id] = device_info
        
        # 触发设备发现回调
        if is_new_device and self.on_device_found:
            self.on_device_found(device_info)
    
    def _check_device_timeout(self, timeout: int = DISCOVER_INTERVAL * 3):
        """检查设备是否超时（长时间未响应）"""
        current_time = time.time()
        expired_devices = []
        
        for device_id, device in list(self.devices.items()):
            if current_time - device.last_seen > timeout:
                expired_devices.append(device)
                del self.devices[device_id]
        
        # 触发设备丢失回调
        if self.on_device_lost:
            for device in expired_devices:
                self.on_device_lost(device)
    
    def get_devices(self) -> List[DeviceInfo]:
        """获取当前已发现的设备列表"""
        return list(self.devices.values())
    
    def send_message(self, device: DeviceInfo, message: Message) -> bool:
        """向指定设备发送消息
        
        Args:
            device: 目标设备信息
            message: 要发送的消息对象
            
        Returns:
            bool: 发送是否成功
        """
        if not device or not message:
            logger.error("无法发送消息：设备或消息为空")
            return False
            
        client_socket = None
        try:
            # 创建TCP套接字
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.settimeout(SOCKET_TIMEOUT)
            
            # 连接到目标设备
            logger.debug(f"尝试连接到 {device.ip_address}:{device.port}")
            client_socket.connect((device.ip_address, device.port))
            
            # 发送消息
            message_bytes = message.to_bytes()
            bytes_sent = 0
            total_bytes = len(message_bytes)
            
            # 确保所有数据都被发送
            while bytes_sent < total_bytes:
                sent = client_socket.send(message_bytes[bytes_sent:])
                if sent == 0:
                    raise RuntimeError("套接字连接已断开")
                bytes_sent += sent
                
            logger.debug(f"成功发送消息: {message.msg_type} 到 {device.device_name}")
            return True
            
        except ConnectionRefusedError:
            logger.warning(f"连接被拒绝: {device.ip_address}:{device.port}")
            return False
        except socket.timeout:
            logger.warning(f"连接超时: {device.ip_address}:{device.port}")
            return False
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            return False
        finally:
            # 确保套接字被关闭
            if client_socket:
                try:
                    client_socket.close()
                except:
                    pass
    
    def create_server_socket(self) -> socket.socket:
        """创建服务器套接字用于文件传输"""
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind((self.host_ip, TRANSFER_PORT))
        server_sock.listen(10)  # 允许最多10个等待连接
        server_sock.settimeout(1.0)  # 设置超时以便能响应关闭请求
        return server_sock 