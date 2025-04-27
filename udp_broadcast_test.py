"""
局域网UDP广播测试工具 (UDP Broadcast Test Tool)

该工具用于诊断局域网环境中UDP广播的可用性和网络隔离情况，帮助解决SendNow设备发现功能的问题。
主要功能：
- 发送和接收UDP广播测试消息
- 检测路由器是否开启了AP隔离/客户端隔离功能
- 分析网络环境中的设备可见性和连通性
- 诊断常见的网络配置问题（VLAN隔离、广播限制等）
- 提供解决建议和最佳网络配置参考

当SendNow无法发现局域网内其他设备时，可使用该工具进行网络环境诊断，找出并解决连接问题。
"""

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import socket
import time
import threading
import netifaces
import sys
import argparse
import subprocess
import platform
import re
from typing import List, Dict, Tuple, Optional

# 颜色常量，用于终端输出
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"
BOLD = "\033[1m"

def get_local_ip():
    """获取本机IP地址"""
    for interface in netifaces.interfaces():
        addresses = netifaces.ifaddresses(interface)
        if netifaces.AF_INET in addresses:
            for address in addresses[netifaces.AF_INET]:
                if 'addr' in address and address['addr'] != '127.0.0.1':
                    return address['addr']
    return '127.0.0.1'

def get_default_gateway():
    """获取默认网关IP地址"""
    try:
        if platform.system() == "Darwin" or platform.system() == "Linux":  # macOS或Linux
            output = subprocess.check_output("netstat -rn | grep default", shell=True).decode()
            gateway = output.split()[1]
            return gateway
        elif platform.system() == "Windows":  # Windows
            output = subprocess.check_output("ipconfig", shell=True).decode()
            for line in output.split('\n'):
                if "Default Gateway" in line:
                    match = re.search(r'\d+\.\d+\.\d+\.\d+', line)
                    if match:
                        return match.group(0)
        return None
    except Exception as e:
        print(f"[警告] 无法获取默认网关: {e}")
        return None

def get_network_devices() -> List[Dict]:
    """通过ARP表获取局域网内可见的设备列表"""
    devices = []
    try:
        if platform.system() == "Darwin" or platform.system() == "Linux":  # macOS或Linux
            output = subprocess.check_output("arp -a", shell=True).decode()
            for line in output.split('\n'):
                match = re.search(r'\((\d+\.\d+\.\d+\.\d+)\) at ([0-9a-f:]+)', line)
                if match:
                    ip, mac = match.groups()
                    if mac != "ff:ff:ff:ff:ff:ff" and not ip.startswith("127."):
                        devices.append({"ip": ip, "mac": mac})
        elif platform.system() == "Windows":  # Windows
            output = subprocess.check_output("arp -a", shell=True).decode()
            for line in output.split('\n'):
                parts = line.split()
                if len(parts) >= 3 and re.match(r'\d+\.\d+\.\d+\.\d+', parts[0]):
                    ip, mac = parts[0], parts[1]
                    if mac != "ff-ff-ff-ff-ff-ff" and not ip.startswith("127."):
                        devices.append({"ip": ip, "mac": mac})
        return devices
    except Exception as e:
        print(f"[警告] 无法获取网络设备: {e}")
        return []

def start_receiver(port, timeout=15):
    """启动UDP广播接收器"""
    receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receiver.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    receiver.settimeout(timeout)
    
    try:
        receiver.bind(('', port))
        print(f"[接收] 开始在端口 {port} 监听UDP广播...")
        
        start_time = time.time()
        messages_received = 0
        sources = set()
        
        while time.time() - start_time < timeout:
            try:
                data, addr = receiver.recvfrom(1024)
                message = data.decode('utf-8')
                print(f"{GREEN}[接收] 从 {addr[0]} 收到消息: {message}{RESET}")
                messages_received += 1
                sources.add(addr[0])
            except socket.timeout:
                break
        
        return messages_received, sources
    except Exception as e:
        print(f"{RED}[错误] 接收器出错: {e}{RESET}")
        return 0, set()
    finally:
        receiver.close()

def send_broadcast(port, message, count=5):
    """发送UDP广播消息"""
    time.sleep(1)  # 给接收器一点时间启动
    
    sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sender.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    
    try:
        local_ip = get_local_ip()
        print(f"[发送] 本机IP: {local_ip}")
        print(f"[发送] 开始发送 {count} 个UDP广播消息到端口 {port}...")
        
        for i in range(count):
            broadcast_msg = f"{message} #{i+1}"
            sender.sendto(broadcast_msg.encode('utf-8'), ('<broadcast>', port))
            print(f"[发送] 广播消息: {broadcast_msg}")
            time.sleep(1)
            
        return True
    except Exception as e:
        print(f"{RED}[错误] 发送器出错: {e}{RESET}")
        return False
    finally:
        sender.close()

def test_unicast_connectivity(devices, message="测试单播连接", port=45680):
    """测试与局域网内其他设备的直接连接（检测AP隔离）"""
    if not devices:
        print(f"{YELLOW}[警告] 未发现其他网络设备，无法测试AP隔离{RESET}")
        return None
    
    # 尝试连接到其他设备
    results = []
    local_ip = get_local_ip()
    
    for device in devices:
        if device["ip"] == local_ip:
            continue
            
        try:
            # 尝试建立TCP连接测试直接可达性
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((device["ip"], port))
            sock.close()
            
            # 尝试发送UDP单播数据
            udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            udp_sock.settimeout(1)
            udp_sock.sendto(f"{message} to {device['ip']}".encode('utf-8'), (device["ip"], port))
            udp_sock.close()
            
            status = "可能可达" if result in [0, 111, 10061] else "不可达"
            results.append((device["ip"], status))
            print(f"[单播测试] IP: {device['ip']} - {status}")
            
        except Exception as e:
            print(f"[单播测试] IP: {device['ip']} - 错误: {e}")
            results.append((device["ip"], "错误"))
    
    return results

def check_network_isolation():
    """综合分析网络隔离情况"""
    print(f"\n{BOLD}==== 网络环境分析 ===={RESET}")
    
    # 1. 获取局域网内设备信息
    devices = get_network_devices()
    devices_count = len(devices)
    
    if devices_count == 0:
        print(f"{YELLOW}[分析] 未在ARP表中发现其他设备，这可能表明:{RESET}")
        print(f"   - 您的网络中确实没有其他活跃设备")
        print(f"   - 路由器开启了AP隔离/客户端隔离")
        print(f"   - 您处于VLAN隔离环境中")
    else:
        print(f"[分析] 在ARP表中发现 {devices_count} 个网络设备")
        for i, device in enumerate(devices):
            print(f"   {i+1}. IP: {device['ip']}, MAC: {device['mac']}")
    
    # 2. 获取默认网关
    gateway = get_default_gateway()
    if gateway:
        print(f"[分析] 默认网关: {gateway}")
    else:
        print(f"{YELLOW}[分析] 无法确定默认网关{RESET}")
    
    # 3. 分析AP隔离情况
    if devices_count > 0:
        print(f"\n{BOLD}正在测试AP隔离/客户端隔离...{RESET}")
        unicast_results = test_unicast_connectivity(devices)
        
        if unicast_results:
            unreachable_count = sum(1 for _, status in unicast_results if status == "不可达")
            if unreachable_count == len(unicast_results):
                print(f"{RED}[分析] 所有设备均不可直接访问，很可能启用了AP隔离/客户端隔离{RESET}")
            elif unreachable_count > 0:
                print(f"{YELLOW}[分析] 部分设备不可直接访问，网络可能存在复杂隔离策略{RESET}")
            else:
                print(f"{GREEN}[分析] 大多数设备可直接访问，AP隔离/客户端隔离很可能未启用{RESET}")
    
    return devices_count > 0

def main():
    parser = argparse.ArgumentParser(description='测试局域网UDP广播和网络隔离')
    parser.add_argument('--port', type=int, default=45678, help='UDP广播端口 (默认: 45678)')
    parser.add_argument('--count', type=int, default=5, help='发送的消息数量 (默认: 5)')
    parser.add_argument('--timeout', type=int, default=15, help='接收超时时间(秒) (默认: 15)')
    
    args = parser.parse_args()
    
    print(f"{BOLD}==== 局域网网络环境测试 ===={RESET}")
    print(f"[配置] 测试端口: {args.port}")
    
    # 检查网络环境，分析是否存在设备隔离
    devices_found = check_network_isolation()
    
    print(f"\n{BOLD}==== UDP广播测试 ===={RESET}")
    
    # 启动接收线程
    receiver_result = [0, set()]  # [消息数量, 来源IP集合]
    receiver_thread = threading.Thread(
        target=lambda: receiver_result.__setitem__(0, start_receiver(args.port, args.timeout))
    )
    receiver_thread.daemon = True
    receiver_thread.start()
    
    # 启动发送线程
    send_success = [False]
    sender_thread = threading.Thread(
        target=lambda: send_success.__setitem__(0, send_broadcast(args.port, "UDP广播测试消息", args.count))
    )
    sender_thread.daemon = True
    sender_thread.start()
    
    # 等待线程完成
    timeout = args.timeout + 2  # 增加额外时间确保接收完成
    sender_thread.join(timeout)
    receiver_thread.join(timeout)
    
    # 分析测试结果
    messages_received, sources = receiver_result[0]
    
    print(f"\n{BOLD}==== 测试结果分析 ===={RESET}")
    
    if not send_success[0]:
        print(f"{RED}[结论] UDP广播发送失败，可能是网络配置问题{RESET}")
    elif messages_received == 0:
        print(f"{RED}[结论] 未接收到任何UDP广播消息，可能存在以下问题:{RESET}")
        print("   1. 路由器禁止了局域网UDP广播/组播转发")
        print("   2. 启用了AP隔离/客户端隔离")
        print("   3. 存在VLAN隔离")
        print(f"\n{BOLD}解决建议:{RESET}")
        print("   1. 进入路由器管理界面，关闭\"AP隔离\"或\"客户端隔离\"功能")
        print("   2. 检查路由器是否启用了广播风暴控制，并尝试关闭")
        print("   3. 检查是否配置了VLAN，确保设备在同一VLAN中")
    else:
        local_ip = get_local_ip()
        if messages_received > 0 and (len(sources) == 1 and local_ip in sources):
            print(f"{YELLOW}[结论] 仅接收到来自本机的广播消息 ({messages_received}条){RESET}")
            print("   - 这表明广播数据包没有被其他设备接收或回复")
            print("   - 可能原因: 路由器启用了AP隔离/客户端隔离或VLAN隔离")
        else:
            print(f"{GREEN}[结论] 成功接收到 {messages_received} 条UDP广播消息，来自 {len(sources)} 个不同设备{RESET}")
            print("   - 这表明您的局域网支持UDP广播")
            print("   - SendNow的设备发现功能应该能正常工作")
    
    print(f"\n{BOLD}==== 路由器建议配置 ===={RESET}")
    print("1. 关闭\"AP隔离\"或\"客户端隔离\"功能")
    print("2. 确保路由器允许局域网广播/组播转发")
    print("3. 如有多个VLAN，确保需通信的设备在同一VLAN中")
    
if __name__ == "__main__":
    main() 