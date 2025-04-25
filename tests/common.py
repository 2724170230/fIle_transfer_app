"""测试通用工具模块"""

class DeviceNameGenerator:
    """设备名称生成器模拟类"""
    
    @staticmethod
    def get_persistent_name_and_id():
        """
        获取持久化的设备名称和ID
        
        返回:
            元组: (设备名称, 设备ID)
        """
        return "测试设备", "test123" 