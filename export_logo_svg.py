import os
import math
from PyQt5.QtSvg import QSvgGenerator
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush
from PyQt5.QtCore import Qt, QPoint, QPointF, QSize, QRect

# 定义颜色
HIGHLIGHT_COLOR = "#4F6FFF"  # 蓝紫高亮色
ACCENT_COLOR = "#8453DC"     # 紫色强调色

def create_svg_logo(output_path):
    """创建SVG格式的SendNow标志"""
    
    # 确保输出目录存在
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # 创建SVG生成器
    generator = QSvgGenerator()
    generator.setFileName(output_path)
    generator.setSize(QSize(300, 300))
    generator.setViewBox(QRect(0, 0, 300, 300))
    generator.setTitle("SendNow Logo")
    generator.setDescription("SendNow应用程序的标志")
    
    # 创建画家
    painter = QPainter()
    painter.begin(generator)
    painter.setRenderHint(QPainter.Antialiasing)
    
    # 定义中心点和半径
    center = QPoint(150, 150)
    radius = 120
    
    # 绘制黑色背景圆
    painter.setPen(Qt.NoPen)
    painter.setBrush(QBrush(QColor("#000000")))
    painter.drawEllipse(center, radius, radius)
    
    # 设置白色画笔
    white_color = QColor("#FFFFFF")
    
    # 绘制外部六边形
    hex_radius = radius * 0.85
    hex_points = []
    angle = 0  # 固定角度
    for i in range(6):
        rad_angle = math.radians(i * 60 + angle)
        x = center.x() + hex_radius * math.cos(rad_angle)
        y = center.y() + hex_radius * math.sin(rad_angle)
        hex_points.append(QPoint(int(x), int(y)))
    
    # 绘制外六边形
    pen = QPen(white_color)
    pen.setWidth(2)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    painter.drawPolygon(hex_points)
    
    # 绘制内部六边形
    inner_hex_radius = radius * 0.6
    inner_hex_points = []
    for i in range(6):
        rad_angle = math.radians(i * 60 + 30 + angle)  # 偏移30度
        x = center.x() + inner_hex_radius * math.cos(rad_angle)
        y = center.y() + inner_hex_radius * math.sin(rad_angle)
        inner_hex_points.append(QPoint(int(x), int(y)))
    
    painter.drawPolygon(inner_hex_points)
    
    # 绘制主环
    outer_ring_radius = radius * 0.95
    pen.setWidth(1)
    painter.setPen(pen)
    painter.drawEllipse(center, outer_ring_radius, outer_ring_radius)
    
    # 绘制简化同心圆环
    for r in [0.4, 0.2]:
        ring_radius = radius * r
        painter.drawEllipse(center, ring_radius, ring_radius)
    
    # 绘制简化放射状线条
    num_lines = 12
    line_length = radius * 0.9
    pen.setWidth(1)
    painter.setPen(pen)
    
    for i in range(num_lines):
        rad_angle = math.radians(i * (360 / num_lines))
        
        if i % 2 == 0:  # 每隔一条线从中心点开始
            x1 = center.x()
            y1 = center.y()
            pen.setWidth(2)
        else:
            inner_radius = radius * 0.2
            x1 = center.x() + inner_radius * math.cos(rad_angle)
            y1 = center.y() + inner_radius * math.sin(rad_angle)
            pen.setWidth(1)
        
        painter.setPen(pen)
        x2 = center.x() + line_length * math.cos(rad_angle)
        y2 = center.y() + line_length * math.sin(rad_angle)
        
        painter.drawLine(QPoint(int(x1), int(y1)), QPoint(int(x2), int(y2)))
    
    # 绘制六个关键点
    painter.setPen(Qt.NoPen)
    painter.setBrush(QBrush(white_color))
    
    for i in range(6):
        rad_angle = math.radians(i * 60)
        x = center.x() + hex_radius * 0.9 * math.cos(rad_angle)
        y = center.y() + hex_radius * 0.9 * math.sin(rad_angle)
        painter.drawEllipse(QPointF(x, y), 3, 3)
    
    # 绘制精简刻度环
    tick_radius = radius * 0.9
    tick_count = 12
    
    for i in range(tick_count):
        rad_angle = math.radians(i * (360 / tick_count))
        
        outer_radius = tick_radius
        inner_radius = tick_radius * 0.95
        
        pen.setWidth(2)
        painter.setPen(pen)
        
        x1 = center.x() + outer_radius * math.cos(rad_angle)
        y1 = center.y() + outer_radius * math.sin(rad_angle)
        x2 = center.x() + inner_radius * math.cos(rad_angle)
        y2 = center.y() + inner_radius * math.sin(rad_angle)
        
        painter.drawLine(QPoint(int(x1), int(y1)), QPoint(int(x2), int(y2)))
    
    # 绘制中心点
    painter.setPen(Qt.NoPen)
    painter.setBrush(QBrush(white_color))
    painter.drawEllipse(center, radius * 0.05, radius * 0.05)
    
    # 结束绘画
    painter.end()
    print(f"SVG标志已成功导出到: {output_path}")

if __name__ == "__main__":
    app = QApplication([])  # 需要QApplication实例才能使用QPainter
    
    # 确保icons文件夹存在
    if not os.path.exists("icons"):
        os.makedirs("icons")
    
    # 导出SVG
    create_svg_logo("icons/sendnow_logo.svg") 