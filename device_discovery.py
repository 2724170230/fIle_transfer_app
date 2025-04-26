import socket
import json
import threading
import time

class DeviceDiscovery:
    def __init__(self, device_found_callback=None):
        self.broadcast_port = 8888
        self.device_found_callback = device_found_callback
        self.running = False
        self.device_info = {}  # 本设备信息
        self.discovered_devices = {}  # 发现的设备列表
    
    def set_device_info(self, name, device_id):
        """设置本设备信息"""
        self.device_info = {
            "name": name,
            "id": device_id,
            "ip": self._get_local_ip(),
            "port": 9999  # 文件传输端口
        }
        print(f"设置设备信息: {self.device_info}")
    
    def start_discovery(self):
        """开始设备发现"""
        if not self.device_info:
            raise ValueError("需要先设置设备信息")
            
        self.running = True
        
        # 启动广播线程
        threading.Thread(target=self._broadcast_presence, daemon=True).start()
        
        # 启动监听线程
        threading.Thread(target=self._listen_for_devices, daemon=True).start()
        
        print("设备发现服务已启动")
    
    def _broadcast_presence(self):
        """广播本设备存在"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
        while self.running:
            try:
                # 广播设备信息
                device_info_json = json.dumps(self.device_info).encode()
                sock.sendto(device_info_json, ('<broadcast>', self.broadcast_port))
                time.sleep(2)  # 每2秒广播一次
            except Exception as e:
                print(f"广播设备信息出错: {e}")
        
        sock.close()
    
    def _listen_for_devices(self):
        """监听其他设备广播"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('0.0.0.0', self.broadcast_port))
        sock.settimeout(1)  # 设置超时以便检查running标志
        
        while self.running:
            try:
                data, addr = sock.recvfrom(1024)
                if data:
                    device_info = json.loads(data.decode())
                    device_id = device_info.get('id')
                    
                    # 排除自己
                    if device_id and device_id != self.device_info.get('id'):
                        # 更新设备IP为发送方IP
                        device_info['ip'] = addr[0]
                        
                        # 检查是否是新设备
                        is_new = device_id not in self.discovered_devices
                        
                        # 更新发现的设备
                        self.discovered_devices[device_id] = device_info
                        
                        # 通知UI
                        if self.device_found_callback and is_new:
                            print(f"发现新设备: {device_info['name']} ({device_info['ip']})")
                            self.device_found_callback(device_info)
            except socket.timeout:
                continue
            except Exception as e:
                print(f"监听设备广播出错: {e}")
        
        sock.close()
    
    def _get_local_ip(self):
        """获取本机IP地址"""
        try:
            # 连接到公共DNS服务器，获取本地IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            # 回退到localhost
            return '127.0.0.1'
    
    def stop_discovery(self):
        """停止设备发现"""
        self.running = False
        print("设备发现服务已停止")
    
    def get_discovered_devices(self):
        """获取已发现的设备列表"""
        return list(self.discovered_devices.values()) 