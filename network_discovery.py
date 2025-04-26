import socket
import json
import threading
import time
import uuid
import ipaddress
import netifaces
import logging
from PyQt5.QtCore import QObject, pyqtSignal

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("NetworkDiscovery")

# 默认通信端口
DISCOVERY_PORT = 45678
SERVICE_PORT = 45679

class DeviceInfo:
    """设备信息类"""
    
    def __init__(self, name, device_id, ip, port=SERVICE_PORT):
        self.name = name
        self.device_id = device_id
        self.ip = ip
        self.port = port
        self.last_seen = time.time()
    
    def to_dict(self):
        """转换为字典"""
        return {
            "name": self.name,
            "id": self.device_id,
            "ip": self.ip,
            "port": self.port
        }
    
    def is_expired(self, timeout=60):
        """检查设备是否超时（60秒未收到广播）"""
        return (time.time() - self.last_seen) > timeout
    
    def __eq__(self, other):
        """比较两个设备是否相同"""
        if not isinstance(other, DeviceInfo):
            return False
        return self.device_id == other.device_id
    
    def __hash__(self):
        """哈希函数支持设备对象用作字典键"""
        return hash(self.device_id)

class NetworkDiscovery(QObject):
    """局域网设备发现模块"""
    
    # 信号定义
    deviceDiscovered = pyqtSignal(object)  # 发现新设备
    deviceLost = pyqtSignal(object)        # 设备离线
    statusChanged = pyqtSignal(str)        # 状态改变
    
    def __init__(self, device_name, device_id, service_port=SERVICE_PORT):
        super().__init__()
        self.device_name = device_name
        self.device_id = device_id
        self.service_port = service_port
        self.discovery_port = DISCOVERY_PORT
        self.is_running = False
        self.devices = {}  # 已发现的设备字典
        
        # 网络参数
        self.broadcast_interval = 5.0  # 广播间隔(秒)
        self.socket_timeout = 0.5      # 套接字接收超时
        self.device_timeout = 30.0     # 设备超时时间(秒)
        
        # 线程
        self.discovery_thread = None
        self.broadcast_thread = None
        self.cleanup_thread = None
    
    def start(self):
        """启动设备发现服务"""
        if self.is_running:
            return
        
        self.is_running = True
        self.statusChanged.emit("正在启动设备发现服务...")
        
        # 启动发现线程
        self.discovery_thread = threading.Thread(target=self._discovery_loop, daemon=True)
        self.discovery_thread.start()
        
        # 启动广播线程
        self.broadcast_thread = threading.Thread(target=self._broadcast_loop, daemon=True)
        self.broadcast_thread.start()
        
        # 启动清理线程
        self.cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self.cleanup_thread.start()
        
        self.statusChanged.emit("设备发现服务已启动")
        logger.info("设备发现服务已启动")
    
    def stop(self):
        """停止设备发现服务"""
        if not self.is_running:
            return
        
        self.is_running = False
        self.statusChanged.emit("正在停止设备发现服务...")
        
        # 等待线程结束
        if self.discovery_thread and self.discovery_thread.is_alive():
            self.discovery_thread.join(timeout=1.0)
        
        if self.broadcast_thread and self.broadcast_thread.is_alive():
            self.broadcast_thread.join(timeout=1.0)
        
        if self.cleanup_thread and self.cleanup_thread.is_alive():
            self.cleanup_thread.join(timeout=1.0)
        
        # 清除设备列表
        self.devices.clear()
        self.statusChanged.emit("设备发现服务已停止")
        logger.info("设备发现服务已停止")
    
    def _discovery_loop(self):
        """设备发现循环"""
        try:
            # 创建UDP套接字
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(('', self.discovery_port))
            sock.settimeout(self.socket_timeout)
            
            logger.info(f"监听设备广播在端口 {self.discovery_port}")
            
            while self.is_running:
                try:
                    data, addr = sock.recvfrom(1024)
                    self._handle_discovery_message(data, addr)
                except socket.timeout:
                    continue
                except Exception as e:
                    logger.error(f"接收设备广播时出错: {str(e)}")
                    time.sleep(1)  # 发生错误时暂停一下
        
        except Exception as e:
            logger.error(f"设备发现线程错误: {str(e)}")
        finally:
            try:
                sock.close()
            except:
                pass
            logger.info("设备发现线程已结束")
    
    def _broadcast_loop(self):
        """设备广播循环"""
        try:
            # 创建UDP广播套接字
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.settimeout(self.socket_timeout)
            
            logger.info(f"开始广播设备信息，间隔 {self.broadcast_interval} 秒")
            
            while self.is_running:
                try:
                    # 获取所有网络接口的广播地址
                    broadcast_addresses = self._get_broadcast_addresses()
                    
                    # 广播设备信息
                    for broadcast_address in broadcast_addresses:
                        self._send_broadcast(sock, broadcast_address)
                    
                    # 等待下一个广播周期
                    time.sleep(self.broadcast_interval)
                
                except Exception as e:
                    logger.error(f"广播设备信息时出错: {str(e)}")
                    time.sleep(1)
        
        except Exception as e:
            logger.error(f"设备广播线程错误: {str(e)}")
        finally:
            try:
                sock.close()
            except:
                pass
            logger.info("设备广播线程已结束")
    
    def _cleanup_loop(self):
        """清理过期设备循环"""
        try:
            logger.info("启动设备超时清理线程")
            
            while self.is_running:
                try:
                    # 检查过期设备
                    expired_devices = []
                    for device_id, device in list(self.devices.items()):
                        if device.is_expired(timeout=self.device_timeout) and device_id != self.device_id:
                            expired_devices.append(device)
                            del self.devices[device_id]
                    
                    # 触发设备离线信号
                    for device in expired_devices:
                        logger.info(f"设备已超时: {device.name} ({device.device_id}) - {device.ip}")
                        self.deviceLost.emit(device)
                    
                    # 休眠
                    time.sleep(5)
                
                except Exception as e:
                    logger.error(f"清理过期设备时出错: {str(e)}")
                    time.sleep(1)
        
        except Exception as e:
            logger.error(f"设备清理线程错误: {str(e)}")
        finally:
            logger.info("设备清理线程已结束")
    
    def _handle_discovery_message(self, data, addr):
        """处理接收到的设备发现消息"""
        try:
            # 解析收到的JSON数据
            message = json.loads(data.decode('utf-8'))
            
            # 提取设备信息
            device_name = message.get('name', 'Unknown Device')
            device_id = message.get('id', '')
            device_ip = addr[0]
            device_port = message.get('port', self.service_port)
            
            # 忽略自己的广播
            if device_id == self.device_id:
                return
            
            # 创建或更新设备信息
            device = DeviceInfo(device_name, device_id, device_ip, device_port)
            is_new_device = device_id not in self.devices
            
            # 更新设备列表
            self.devices[device_id] = device
            
            # 仅对新设备触发发现信号
            if is_new_device:
                logger.info(f"发现新设备: {device_name} ({device_id}) - {device_ip}")
                self.deviceDiscovered.emit(device)
        
        except json.JSONDecodeError:
            logger.warning(f"收到无效的设备广播数据: {data}")
        except Exception as e:
            logger.error(f"处理设备广播时出错: {str(e)}")
    
    def _send_broadcast(self, sock, broadcast_address):
        """发送设备广播"""
        try:
            # 准备广播消息
            message = {
                "name": self.device_name,
                "id": self.device_id,
                "port": self.service_port
            }
            
            # 转换为JSON并发送
            data = json.dumps(message).encode('utf-8')
            sock.sendto(data, (broadcast_address, self.discovery_port))
            
        except Exception as e:
            logger.error(f"发送广播到 {broadcast_address} 时出错: {str(e)}")
    
    def _get_broadcast_addresses(self):
        """获取所有活动网络接口的广播地址"""
        broadcast_addresses = set()
        
        try:
            # 获取所有网络接口
            interfaces = netifaces.interfaces()
            
            for interface in interfaces:
                # 跳过回环接口
                if interface.startswith('lo'):
                    continue
                
                # 获取接口地址信息
                addrs = netifaces.ifaddresses(interface)
                
                # 获取IPv4地址
                if netifaces.AF_INET in addrs:
                    for addr in addrs[netifaces.AF_INET]:
                        # 检查是否有广播地址
                        if 'broadcast' in addr:
                            broadcast_addresses.add(addr['broadcast'])
                        # 如果没有广播地址，但有IP和子网掩码，计算广播地址
                        elif 'addr' in addr and 'netmask' in addr:
                            try:
                                ip = ipaddress.IPv4Address(addr['addr'])
                                netmask = ipaddress.IPv4Address(addr['netmask'])
                                network = ipaddress.IPv4Network(f"{ip}/{netmask}", strict=False)
                                broadcast_addresses.add(str(network.broadcast_address))
                            except:
                                pass
        except Exception as e:
            logger.error(f"获取广播地址时出错: {str(e)}")
            # 如果出错，至少尝试使用通用广播地址
            broadcast_addresses.add('255.255.255.255')
        
        # 如果没有找到任何广播地址，使用通用广播地址
        if not broadcast_addresses:
            broadcast_addresses.add('255.255.255.255')
        
        return broadcast_addresses
    
    def get_discovered_devices(self):
        """获取已发现的设备列表"""
        return list(self.devices.values())


# 如果作为独立脚本运行，执行测试代码
if __name__ == "__main__":
    # 测试设备发现功能
    device_name = "测试设备"
    device_id = f"#{uuid.uuid4().hex[:8]}"
    
    # 创建设备发现实例
    discovery = NetworkDiscovery(device_name, device_id)
    
    # 注册回调函数
    def on_device_discovered(device):
        print(f"发现设备: {device.name} ({device.device_id}) - {device.ip}")
    
    def on_device_lost(device):
        print(f"设备离线: {device.name} ({device.device_id}) - {device.ip}")
    
    def on_status_changed(status):
        print(f"状态变化: {status}")
    
    discovery.deviceDiscovered.connect(on_device_discovered)
    discovery.deviceLost.connect(on_device_lost)
    discovery.statusChanged.connect(on_status_changed)
    
    # 启动服务
    discovery.start()
    
    try:
        # 运行60秒后退出
        print("测试运行中，按Ctrl+C退出...")
        time.sleep(60)
    except KeyboardInterrupt:
        print("用户中断，正在停止...")
    finally:
        # 停止服务
        discovery.stop() 