import socket
import sys
import time

def test_server(port=9999):
    """测试服务器是否能正常监听端口"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('0.0.0.0', port))
        s.listen(5)
        print(f"服务器测试成功，正在监听 {port} 端口")
        s.close()
        return True
    except Exception as e:
        print(f"服务器测试失败: {e}")
        return False

def test_broadcast(port=8888):
    """测试UDP广播功能"""
    try:
        send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        send_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
        recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        recv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        recv_sock.bind(('0.0.0.0', port))
        recv_sock.settimeout(2)
        
        # 发送测试消息
        message = "BROADCAST_TEST".encode()
        send_sock.sendto(message, ('<broadcast>', port))
        print(f"已发送广播测试消息到 {port} 端口")
        
        # 尝试接收
        try:
            data, addr = recv_sock.recvfrom(1024)
            print(f"成功接收到广播消息: {data.decode()} 来自 {addr}")
            result = True
        except socket.timeout:
            print("广播测试超时，未收到消息")
            result = False
            
        send_sock.close()
        recv_sock.close()
        return result
    except Exception as e:
        print(f"广播测试失败: {e}")
        return False

def get_network_info():
    """获取网络信息"""
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        print(f"主机名: {hostname}")
        print(f"本地IP: {ip}")
        
        # 获取本机IP（连接外部地址）
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # 不需要真正连接
            s.connect(('8.8.8.8', 80))
            external_ip = s.getsockname()[0]
            print(f"外部IP: {external_ip}")
        except:
            print("无法获取外部IP")
        finally:
            s.close()
    except Exception as e:
        print(f"获取网络信息失败: {e}")

if __name__ == "__main__":
    print("正在测试网络连接...")
    get_network_info()
    
    print("\n测试TCP服务器端口...")
    test_server()
    
    print("\n测试UDP广播功能...")
    test_broadcast()
    
    print("\n测试完成") 