import sys
import random
import hashlib
import os
import math  # 添加math模块导入
import time  # 添加time模块导入用于计算传输速度
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QFileDialog, 
                             QProgressBar, QListWidget, QListWidgetItem, QStackedWidget, 
                             QFrame, QSplitter, QGridLayout, QSpacerItem, QSizePolicy,
                             QButtonGroup, QToolButton, QAction)
from PyQt5.QtCore import Qt, QSize, pyqtSignal, QMimeData, QUrl, QTimer, QRect, QPoint, QPointF, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QIcon, QColor, QPalette, QFont, QDrag, QPainter, QPen, QBrush, QPainterPath, QRadialGradient, QLinearGradient, QTransform

# 更高对比度的赛博朋克风格色调
DARK_BG = "#10111E"        # 更深的导航栏背景色
MAIN_BG = "#151829"        # 更深的主界面背景
PANEL_BG = "#1D203A"       # 更明显的面板背景
INNER_BG = "#262B4A"       # 更亮的内部元素背景
LIST_ITEM_BG = "#30365A"   # 更亮的列表项背景
HIGHLIGHT_COLOR = "#4F6FFF" # 更亮的蓝紫高亮色
ACCENT_COLOR = "#8453DC"   # 更亮的紫色强调色
TEXT_COLOR = "#FFFFFF"     # 纯白文本
SECONDARY_TEXT_COLOR = "#A6A7CA" # 更亮的次级文本
BUTTON_BG = "#2E355F"      # 更亮的按钮背景
BUTTON_HOVER = "#3A4273"   # 更亮的按钮悬停色
BORDER_COLOR = "#36406A"   # 边框颜色，增强边界

# 设备名称生成器
class DeviceNameGenerator:
    """生成独特而有记忆点的设备名称"""
    
    # 形容词列表
    ADJECTIVES = [
        "智能", "快速", "闪耀", "创新", "数字", "量子", "流畅", "精确", "先锋", "超级",
        "动态", "光速", "敏捷", "未来", "高效", "智慧", "卓越", "锐利", "强大", "优雅",
        "无限", "灵动", "极致", "奇妙", "炫酷", "前沿", "尖端", "高能", "星际", "极光"
    ]
    
    # 名词列表
    NOUNS = [
        "蓝莓", "星辰", "云朵", "光子", "电波", "脉冲", "光环", "晶体", "微粒", "夜莺",
        "极光", "雷电", "凤凰", "流星", "宝石", "旋律", "飞鹰", "银河", "钻石", "曜石",
        "赤狐", "翡翠", "海豚", "猎豹", "巨兽", "星尘", "彗星", "风暴", "幻象", "天琴"
    ]
    
    @staticmethod
    def generate_name():
        """生成随机设备名称"""
        adjective = random.choice(DeviceNameGenerator.ADJECTIVES)
        noun = random.choice(DeviceNameGenerator.NOUNS)
        return f"{adjective}{noun}"
    
    @staticmethod
    def generate_id(seed=None):
        """生成唯一ID，格式为两位数字"""
        if seed is None:
            # 使用设备信息和随机数作为种子
            seed = f"{os.getlogin()}_{random.randint(1, 999)}"
        
        # 取哈希值的前两位作为ID
        hash_value = hashlib.md5(seed.encode()).hexdigest()
        return f"#{int(hash_value[:4], 16) % 99 + 1:02d}"
    
    @staticmethod
    def get_persistent_name_and_id():
        """获取持久化的设备名称和ID"""
        # 尝试读取存储的名称和ID
        try:
            config_file = os.path.join(os.path.expanduser("~"), ".sendnow_config")
            if os.path.exists(config_file):
                with open(config_file, "r") as f:
                    content = f.read().strip().split(",")
                    if len(content) == 2:
                        return content[0], content[1]
        except:
            pass
        
        # 生成新的名称和ID
        name = DeviceNameGenerator.generate_name()
        device_id = DeviceNameGenerator.generate_id(name)
        
        # 保存到配置文件
        try:
            config_file = os.path.join(os.path.expanduser("~"), ".sendnow_config")
            with open(config_file, "w") as f:
                f.write(f"{name},{device_id}")
        except:
            pass
        
        return name, device_id

class DynamicLogoWidget(QWidget):
    """简洁几何风格的SendNow动态Logo"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(180, 180)  # 增加最小尺寸
        self.setMaximumSize(300, 300)  # 增加最大尺寸
        
        # 设置大小策略为保持宽高比
        sizePolicy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        sizePolicy.setHeightForWidth(True)
        self.setSizePolicy(sizePolicy)
        
        # 动画计时器
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(40)  # 25fps
        
        # 动画参数
        self.angle = 0
        self.inner_angle = 0
        
        # 颜色
        self.base_color = QColor(HIGHLIGHT_COLOR)
        self.accent_color = QColor(ACCENT_COLOR)
        
        # 控制参数
        self.is_active = True
        self.scale_factor = 1.0
        self.target_scale = 1.0
        self.animation_speed = 0.05  # 收缩/扩张动画的速度
    
    def heightForWidth(self, width):
        """保持宽高比1:1"""
        return width
    
    def hasHeightForWidth(self):
        """告诉布局管理器这个组件要保持宽高比"""
        return True
    
    def paintEvent(self, event):
        """绘制标志"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 获取中心点和半径
        center = QPoint(self.width() // 2, self.height() // 2)
        radius = (min(self.width(), self.height()) // 2 - 10) * self.scale_factor
        
        # 绘制黑色背景圆
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor("#000000")))
        painter.drawEllipse(center, radius, radius)
        
        # 设置白色画笔
        white_color = QColor("#FFFFFF")
        
        # 绘制外部六边形
        hex_radius = radius * 0.85
        hex_points = []
        for i in range(6):
            angle = (i * 60 + self.angle / 6) % 360
            rad_angle = math.radians(angle)
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
            angle = (i * 60 + 30 + self.angle / 8) % 360  # 偏移30度
            rad_angle = math.radians(angle)
            x = center.x() + inner_hex_radius * math.cos(rad_angle)
            y = center.y() + inner_hex_radius * math.sin(rad_angle)
            inner_hex_points.append(QPoint(int(x), int(y)))
        
        painter.drawPolygon(inner_hex_points)
        
        # 绘制主环
        outer_ring_radius = radius * 0.95
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawEllipse(center, outer_ring_radius, outer_ring_radius)
        
        # 绘制简化同心圆环 (只保留两个)
        for r in [0.4, 0.2]:
            ring_radius = radius * r
            painter.drawEllipse(center, ring_radius, ring_radius)
        
        # 绘制简化放射状线条
        num_lines = 12  # 减少线条数量
        line_length = radius * 0.9
        pen.setWidth(1)
        painter.setPen(pen)
        
        for i in range(num_lines):
            angle = (i * (360 / num_lines) + self.angle) % 360
            rad_angle = math.radians(angle)
            
            # 从中心向外绘制线条
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
            angle = (i * 60 + self.angle / 3) % 360
            rad_angle = math.radians(angle)
            x = center.x() + hex_radius * 0.9 * math.cos(rad_angle)
            y = center.y() + hex_radius * 0.9 * math.sin(rad_angle)
            painter.drawEllipse(QPointF(x, y), 3, 3)
        
        # 绘制精简刻度环
        tick_radius = radius * 0.9
        tick_count = 12  # 减少刻度数量
        
        for i in range(tick_count):
            angle = i * (360 / tick_count)
            rad_angle = math.radians(angle)
            
            # 所有刻度长度相同
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
        
        # 更新旋转角度
        if self.is_active:
            self.angle = (self.angle + 0.5) % 360
            self.inner_angle = (self.inner_angle - 0.3) % 360
        
        # 更新缩放因子 - 平滑过渡
        if abs(self.scale_factor - self.target_scale) > 0.01:
            self.scale_factor += (self.target_scale - self.scale_factor) * self.animation_speed
            self.update()  # 触发重绘

    def setActive(self, active):
        """设置是否激活状态"""
        self.is_active = active
        self.target_scale = 1.0 if active else 0.7  # 当不活跃时缩小到70%
        if not active:
            self.update()  # 立即触发一次更新以显示静止状态

class NavigationButton(QToolButton):
    """自定义导航按钮，支持选中状态高亮"""
    
    def __init__(self, icon_path, text, parent=None):
        super().__init__(parent)
        self.setIcon(QIcon(icon_path))
        self.setText(text)
        self.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.setIconSize(QSize(32, 32))  # 增大图标尺寸
        self.setFixedWidth(120)  # 增加按钮宽度
        self.setCheckable(True)
        self.setStyleSheet(f"""
            QToolButton {{
                color: {SECONDARY_TEXT_COLOR};
                background-color: transparent;
                border: none;
                padding: 15px 5px;
                border-radius: 0px;
                font-size: 14px;
            }}
            QToolButton:checked {{
                color: {TEXT_COLOR};
                background-color: {PANEL_BG};
                border-left: 3px solid {HIGHLIGHT_COLOR};
            }}
            QToolButton:hover:!checked {{
                color: {TEXT_COLOR};
                background-color: rgba(255, 255, 255, 0.1);
            }}
        """)

class DropZoneWidget(QWidget):
    """自定义支持拖放文件的组件"""
    
    filesDropped = pyqtSignal(list)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        
        # 布局
        layout = QVBoxLayout(self)
        self.setLayout(layout)
        
        # 提示标签
        self.label = QLabel("拖拽文件到这里或点击选择文件")
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet(f"color: {SECONDARY_TEXT_COLOR}; font-size: 16px;")
        layout.addItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))
        layout.addWidget(self.label)
        
        # 选择文件按钮
        self.selectButton = QPushButton("选择文件")
        self.selectButton.setStyleSheet(f"""
            QPushButton {{
                background-color: {HIGHLIGHT_COLOR};
                color: {TEXT_COLOR};
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: {HIGHLIGHT_COLOR.replace('#', '#')};
                background-color: {QColor(HIGHLIGHT_COLOR).lighter(120).name()};
            }}
            QPushButton:pressed {{
                background-color: {QColor(HIGHLIGHT_COLOR).darker(110).name()};
            }}
        """)
        self.selectButton.clicked.connect(self.selectFiles)
        
        layout.addWidget(self.selectButton, 0, Qt.AlignCenter)
        layout.addItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))
        
        # 设置样式
        self.setStyleSheet(f"""
            background-color: {PANEL_BG};
            border: 2px dashed {SECONDARY_TEXT_COLOR};
            border-radius: 10px;
        """)
        self.setMinimumHeight(200)
    
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet(f"""
                background-color: {PANEL_BG};
                border: 2px dashed {HIGHLIGHT_COLOR};
                border-radius: 10px;
            """)
    
    def dragLeaveEvent(self, event):
        self.setStyleSheet(f"""
            background-color: {PANEL_BG};
            border: 2px dashed {SECONDARY_TEXT_COLOR};
            border-radius: 10px;
        """)
    
    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            file_paths = [url.toLocalFile() for url in urls]
            self.filesDropped.emit(file_paths)
            self.setStyleSheet(f"""
                background-color: {PANEL_BG};
                border: 2px dashed {SECONDARY_TEXT_COLOR};
                border-radius: 10px;
            """)
    
    def selectFiles(self):
        files, _ = QFileDialog.getOpenFileNames(self, "选择文件")
        if files:
            self.filesDropped.emit(files)

class FileItemWidget(QWidget):
    """文件项部件，包含文件名和删除按钮"""
    deleteClicked = pyqtSignal(QListWidgetItem)
    
    def __init__(self, file_name, size_str, full_path=None, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)  # 改为垂直布局
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(0)  # 删除垂直空间，减少行距
        
        # 顶部布局：文件名和删除按钮
        topLayout = QHBoxLayout()
        topLayout.setSpacing(5)  # 保持合适的水平间距
        
        # 文件名和大小标签
        self.fileLabel = QLabel(f"{file_name} ({size_str})")
        self.fileLabel.setStyleSheet(f"color: {TEXT_COLOR}; font-size: 13px; font-weight: bold;")
        
        # 删除按钮 - 确保图标为白色
        self.deleteButton = QPushButton()
        self.deleteButton.setIcon(QIcon("icons/trash.svg"))  # 垃圾箱图标
        self.deleteButton.setIconSize(QSize(16, 16))
        self.deleteButton.setFixedSize(24, 24)
        self.deleteButton.setCursor(Qt.PointingHandCursor)
        self.deleteButton.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                border-radius: 12px;
                padding: 3px;
                color: white;
            }}
            QPushButton:hover {{
                background-color: rgba(255, 255, 255, 0.1);
            }}
            QPushButton:pressed {{
                background-color: rgba(255, 255, 255, 0.05);
            }}
        """)
        
        # 删除按钮点击事件
        self.deleteButton.clicked.connect(self.onDeleteClicked)
        
        # 添加到顶部布局
        topLayout.addWidget(self.fileLabel, 1)  # 1表示伸展因子
        topLayout.addWidget(self.deleteButton, 0, Qt.AlignRight)  # 右对齐
        
        # 文件路径标签
        self.pathLabel = QLabel(full_path if full_path else "")
        self.pathLabel.setStyleSheet(f"color: {SECONDARY_TEXT_COLOR}; font-size: 11px; margin-top: -5px;")  # 添加负的上边距
        self.pathLabel.setWordWrap(True)
        self.pathLabel.setTextInteractionFlags(Qt.TextSelectableByMouse)  # 允许用户选择文本
        
        # 添加到主布局
        layout.addLayout(topLayout)
        layout.addWidget(self.pathLabel)
        
        # 设置整个部件的样式
        self.setStyleSheet(f"""
            background-color: transparent;
        """)
    
    def onDeleteClicked(self):
        """删除按钮被点击"""
        list_item = self.property("list_item")
        if list_item:
            self.deleteClicked.emit(list_item)

class FileListWidget(QListWidget):
    """已选文件列表，支持单项删除"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QListWidget {{
                background-color: {INNER_BG};
                border: none;
                border-radius: 8px;
                padding: 5px;
            }}
            QListWidget::item {{
                background-color: {LIST_ITEM_BG};
                border-radius: 6px;
                margin: 2px 0px;
                padding: 0px;  /* 减少内边距，让自定义部件填满 */
                color: {TEXT_COLOR};
            }}
            QListWidget::item:hover {{
                background-color: {QColor(LIST_ITEM_BG).lighter(115).name()};
            }}
            QListWidget::item:selected {{
                background-color: {QColor(HIGHLIGHT_COLOR).darker(120).name()};
                color: {TEXT_COLOR};
                border: none;
                font-weight: bold;
            }}
        """)
        
        # 创建虚拟垃圾箱图标
        self.createTrashIcon()
        
        # 添加空列表提示
        self.setPlaceholderText("拖动文件至此处")
    
    def setPlaceholderText(self, text):
        """设置空列表时的占位文本"""
        self.placeholder_text = text
        self.update()
    
    def paintEvent(self, event):
        """重写绘制事件，显示占位文本"""
        super().paintEvent(event)
        
        # 当列表为空时显示占位文本
        if self.count() == 0 and hasattr(self, 'placeholder_text'):
            painter = QPainter(self.viewport())
            painter.setRenderHint(QPainter.Antialiasing)
            
            # 设置字体和颜色
            font = painter.font()
            font.setPointSize(15)  # 增大字体大小
            font.setBold(True)     # 设置为粗体
            painter.setFont(font)
            
            # 使用半透明颜色使其显得更加柔和但依然可见
            placeholderColor = QColor(SECONDARY_TEXT_COLOR)
            placeholderColor.setAlpha(180)  # 设置透明度
            painter.setPen(placeholderColor)
            
            # 绘制文本
            painter.drawText(
                self.viewport().rect(),
                Qt.AlignCenter,
                self.placeholder_text
            )
    
    def createTrashIcon(self):
        """创建垃圾箱图标，如果不存在"""
        trash_icon_path = "icons/trash.svg"
        os.makedirs("icons", exist_ok=True)
        
        if not os.path.exists(trash_icon_path):
            # 简单的垃圾桶SVG图标 - 修改为白色
            trash_svg = """<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="3 6 5 6 21 6"></polyline>
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                <line x1="10" y1="11" x2="10" y2="17"></line>
                <line x1="14" y1="11" x2="14" y2="17"></line>
            </svg>"""
            
            with open(trash_icon_path, 'w') as f:
                f.write(trash_svg)

class StatusPanel(QWidget):
    """传输状态面板"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        
        # 状态标签
        self.statusLabel = QLabel("等待中...")
        self.statusLabel.setStyleSheet(f"color: {TEXT_COLOR}; font-size: 18px;")
        self.statusLabel.setAlignment(Qt.AlignCenter)
        
        # 传输速度标签
        self.speedLabel = QLabel("")
        self.speedLabel.setStyleSheet(f"color: {SECONDARY_TEXT_COLOR}; font-size: 14px;")
        self.speedLabel.setAlignment(Qt.AlignCenter)
        self.speedLabel.setVisible(False)  # 初始隐藏
        
        # 进度条
        self.progressBar = QProgressBar()
        self.progressBar.setRange(0, 100)
        self.progressBar.setValue(0)
        self.progressBar.setTextVisible(True)
        self.progressBar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {INNER_BG};
                border: none;
                border-radius: 5px;
                color: {TEXT_COLOR};
                text-align: center;
                height: 25px;
            }}
            QProgressBar::chunk {{
                background-color: {HIGHLIGHT_COLOR};
                border-radius: 5px;
            }}
        """)
        
        # 传输完成操作按钮（初始隐藏）
        self.actionsWidget = QWidget()
        actionsLayout = QHBoxLayout(self.actionsWidget)
        
        self.openFolderButton = QPushButton("打开所在文件夹")
        self.openFileButton = QPushButton("打开文件")
        
        for btn in [self.openFolderButton, self.openFileButton]:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {BUTTON_BG};
                    color: {TEXT_COLOR};
                    border: none;
                    padding: 8px 15px;
                    border-radius: 4px;
                }}
                QPushButton:hover {{
                    background-color: {BUTTON_HOVER};
                }}
                QPushButton:pressed {{
                    background-color: {QColor(BUTTON_BG).darker(110).name()};
                }}
            """)
            actionsLayout.addWidget(btn)
        
        self.actionsWidget.setVisible(False)
        
        # 完成按钮（初始隐藏）
        self.completeButtonWidget = QWidget()
        completeButtonLayout = QHBoxLayout(self.completeButtonWidget)
        completeButtonLayout.setAlignment(Qt.AlignCenter)
        
        self.completeButton = QPushButton("完成")
        self.completeButton.setStyleSheet(f"""
            QPushButton {{
                background-color: {HIGHLIGHT_COLOR};
                color: {TEXT_COLOR};
                border: none;
                padding: 8px 20px;
                border-radius: 4px;
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {QColor(HIGHLIGHT_COLOR).lighter(115).name()};
            }}
            QPushButton:pressed {{
                background-color: {QColor(HIGHLIGHT_COLOR).darker(110).name()};
            }}
        """)
        self.completeButton.clicked.connect(self.fadeOutAndReset)
        completeButtonLayout.addWidget(self.completeButton)
        self.completeButtonWidget.setVisible(False)
        
        # 添加到主布局
        layout.addStretch()
        layout.addWidget(self.statusLabel)
        layout.addWidget(self.speedLabel)  # 添加速度标签
        layout.addWidget(self.progressBar)
        layout.addWidget(self.actionsWidget)
        layout.addWidget(self.completeButtonWidget)
        layout.addStretch()
        
        # 初始隐藏状态文本和进度条
        self.statusLabel.setVisible(False)
        self.progressBar.setVisible(False)
        
        # 为淡出效果准备的属性动画
        self.fadeAnimation = QPropertyAnimation(self, b"windowOpacity")
        self.fadeAnimation.setDuration(500)  # 500毫秒的动画时间
        self.fadeAnimation.setStartValue(1.0)
        self.fadeAnimation.setEndValue(0.0)
        self.fadeAnimation.setEasingCurve(QEasingCurve.OutQuad)
        self.fadeAnimation.finished.connect(self.onFadeOutFinished)
        
        # 传输速度计算相关变量
        self.last_update_time = 0
        self.last_bytes = 0
    
    def showProgress(self, file_name=None, mode="receive"):
        """显示进度条和状态
        
        参数:
            file_name: 文件名
            mode: 模式，可选值为 "receive"(接收) 或 "send"(发送)
        """
        # 重置透明度
        self.setWindowOpacity(1.0)
        
        self.statusLabel.setVisible(True)
        self.speedLabel.setVisible(True)  # 显示速度标签
        self.progressBar.setVisible(True)
        self.actionsWidget.setVisible(False)
        self.completeButtonWidget.setVisible(False)
        self.setVisible(True)
        
        # 重置传输速度计算相关变量
        self.last_update_time = time.time()
        self.last_bytes = 0
        self.speedLabel.setText("计算中...")
        
        if file_name:
            if mode == "send":
                self.statusLabel.setText(f"正在发送文件：{file_name}")
            else:
                self.statusLabel.setText(f"正在接收文件：{file_name}")
    
    def updateTransferSpeed(self, current_bytes, total_bytes):
        """更新传输速度显示
        
        参数:
            current_bytes: 当前已传输的字节数
            total_bytes: 总字节数
        """
        current_time = time.time()
        time_diff = current_time - self.last_update_time
        
        # 至少等待0.5秒更新一次速度，避免频繁更新
        if time_diff > 0.5 and self.last_update_time > 0:
            bytes_diff = current_bytes - self.last_bytes
            speed = bytes_diff / time_diff  # 字节/秒
            
            # 格式化速度显示
            if speed < 1024:
                speed_str = f"{speed:.1f} B/s"
            elif speed < 1024 * 1024:
                speed_str = f"{speed/1024:.1f} KB/s"
            else:
                speed_str = f"{speed/(1024*1024):.1f} MB/s"
            
            # 计算剩余时间
            remaining_bytes = total_bytes - current_bytes
            if speed > 0:
                remaining_seconds = remaining_bytes / speed
                
                # 格式化剩余时间
                if remaining_seconds < 60:
                    time_str = f"{int(remaining_seconds)}秒"
                elif remaining_seconds < 3600:
                    time_str = f"{int(remaining_seconds/60)}分{int(remaining_seconds%60)}秒"
                else:
                    time_str = f"{int(remaining_seconds/3600)}时{int((remaining_seconds%3600)/60)}分"
                
                self.speedLabel.setText(f"速度: {speed_str} | 剩余时间: {time_str}")
            else:
                self.speedLabel.setText(f"速度: {speed_str}")
            
            # 更新计算基准值
            self.last_update_time = current_time
            self.last_bytes = current_bytes
    
    def showCompleted(self, file_name, mode="receive"):
        """显示传输完成状态"""
        if mode == "send":
            self.statusLabel.setText(f"已发送：{file_name}")
        else:
            self.statusLabel.setText(f"已接收：{file_name}")
        self.progressBar.setValue(100)
        self.speedLabel.setText("传输完成")  # 更新速度标签
        self.actionsWidget.setVisible(mode == "receive")  # 只在接收模式下显示操作按钮
        
        # 在接收模式下显示完成按钮
        if mode == "receive":
            self.completeButtonWidget.setVisible(True)
    
    def fadeOutAndReset(self):
        """开始淡出动画效果"""
        self.fadeAnimation.start()
    
    def onFadeOutFinished(self):
        """淡出动画完成后重置状态"""
        self.reset()
        # 恢复透明度，以备下次显示
        self.setWindowOpacity(1.0)
    
    def reset(self):
        """重置状态面板"""
        self.statusLabel.setVisible(False)
        self.speedLabel.setVisible(False)  # 隐藏速度标签
        self.progressBar.setVisible(False)
        self.actionsWidget.setVisible(False)
        self.completeButtonWidget.setVisible(False)
        self.progressBar.setValue(0)
        self.setVisible(False)
        
        # 重置传输速度计算相关变量
        self.last_update_time = 0
        self.last_bytes = 0

class DeviceSearchWidget(QWidget):
    """搜索附近设备的组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 创建布局
        layout = QVBoxLayout(self)
        
        # 搜索状态标签
        self.searchLabel = QLabel("正在搜索附近设备...")
        self.searchLabel.setAlignment(Qt.AlignCenter)
        self.searchLabel.setStyleSheet(f"color: {TEXT_COLOR}; font-size: 16px;")
        
        # 创建动画指示器
        self.animationWidget = QWidget()
        self.animationWidget.setFixedSize(40, 40)
        self.animationWidget.setStyleSheet("background-color: transparent;")
        
        # 添加到布局
        layout.addWidget(self.animationWidget, 0, Qt.AlignCenter)
        layout.addWidget(self.searchLabel)
        
        # 设置计时器更新动画
        self.angle = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.updateAnimation)
        self.timer.start(50)  # 每50毫秒更新一次
        
        # 设置样式
        self.setMinimumHeight(80)
        self.setStyleSheet("background-color: #35353A; border-radius: 8px;")
    
    def paintEvent(self, event):
        """绘制背景"""
        super().paintEvent(event)
        
        # 绘制背景
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 创建渐变
        gradient = QLinearGradient(0, 0, self.width(), 0)
        gradient.setColorAt(0, QColor("#35353A"))
        gradient.setColorAt(1, QColor("#3A3A40"))
        
        # 填充背景
        painter.fillRect(self.rect(), QBrush(gradient))
    
    def updateAnimation(self):
        """更新动画状态"""
        self.angle = (self.angle + 10) % 360
        self.animationWidget.update()
    
    def paintEvent(self, event):
        """绘制组件"""
        super().paintEvent(event)
    
    def resizeEvent(self, event):
        """调整大小时居中动画组件"""
        super().resizeEvent(event)
        
        # 居中动画组件
        self.animationWidget.move(
            (self.width() - self.animationWidget.width()) // 2,
            10
        )

class AnimationWidget(QWidget):
    """旋转动画组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(40, 40)
        
        # 动画参数
        self.angle = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(50)  # 20fps
    
    def paintEvent(self, event):
        """绘制动画"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 绘制旋转的圆弧
        pen = QPen(QColor(HIGHLIGHT_COLOR))
        pen.setWidth(3)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        
        rect = QRect(3, 3, self.width() - 6, self.height() - 6)
        
        # 绘制3个弧，每个占据一部分圆
        spans = [120, 90, 60]  # 弧的跨度
        gaps = [15, 25, 40]    # 间隙角度
        
        for i, (span, gap) in enumerate(zip(spans, gaps)):
            # 为每个弧使用不同颜色
            if i == 0:
                pen.setColor(QColor(HIGHLIGHT_COLOR))
            elif i == 1:
                pen.setColor(QColor(ACCENT_COLOR))
            else:
                pen.setColor(QColor(HIGHLIGHT_COLOR).lighter(130))
            painter.setPen(pen)
            
            start_angle = (self.angle + i * gap) % 360
            painter.drawArc(rect, start_angle * 16, span * 16)
        
        # 更新角度
        self.angle = (self.angle + 5) % 360

class ReceivePanel(QWidget):
    """接收文件界面"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)  # 边距
        
        # 设置尺寸策略
        sizePolicy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        sizePolicy.setVerticalStretch(1)
        self.setSizePolicy(sizePolicy)
        
        # 创建一个内容容器
        contentWidget = QWidget()
        contentLayout = QVBoxLayout(contentWidget)
        contentLayout.setContentsMargins(25, 30, 25, 30)  # 内边距提高内容集中度
        contentLayout.setSpacing(1)  # 减小整体间距
        
        # 获取设备名称和ID
        self.device_name, self.device_id = DeviceNameGenerator.get_persistent_name_and_id()
        
        # 添加动态标志
        logoContainer = QWidget()
        logoLayout = QVBoxLayout(logoContainer)
        logoLayout.setContentsMargins(0, 0, 0, 0)
        logoLayout.setSpacing(0)  # 减小logo内部间距
        
        self.logoWidget = DynamicLogoWidget()
        logoLayout.addWidget(self.logoWidget, 0, Qt.AlignCenter)
        
        # 设备名称和ID标签
        titleLabel = QLabel(self.device_name)
        titleLabel.setAlignment(Qt.AlignCenter)
        titleLabel.setStyleSheet(f"color: {TEXT_COLOR}; font-size: 36px; font-weight: bold;")
        
        deviceIdLabel = QLabel(self.device_id)
        deviceIdLabel.setAlignment(Qt.AlignCenter)
        deviceIdLabel.setStyleSheet(f"color: {SECONDARY_TEXT_COLOR}; font-size: 24px;")
        
        # 开关按钮
        self.switchWidget = QWidget()
        switchLayout = QHBoxLayout(self.switchWidget)
        switchLayout.setSpacing(0)
        switchLayout.setContentsMargins(0, 5, 0, 5)  # 减小垂直方向上的内边距
        
        self.onButton = QPushButton("开")
        self.offButton = QPushButton("关")
        
        self.onButton.setCheckable(True)
        self.offButton.setCheckable(True)
        
        # 应用样式 - 修复格式化语法
        on_button_style = f"""
            QPushButton {{
                background-color: {BUTTON_BG};
                color: {SECONDARY_TEXT_COLOR};
                border: none;
                padding: 6px 20px;  /* 减小内边距 */
                border-top-left-radius: 15px;
                border-bottom-left-radius: 15px;
            }}
            QPushButton:checked {{
                background-color: {HIGHLIGHT_COLOR};
                color: {TEXT_COLOR};
            }}
        """
        
        off_button_style = f"""
            QPushButton {{
                background-color: {BUTTON_BG};
                color: {SECONDARY_TEXT_COLOR};
                border: none;
                padding: 6px 20px;  /* 减小内边距 */
                border-top-right-radius: 15px;
                border-bottom-right-radius: 15px;
            }}
            QPushButton:checked {{
                background-color: {QColor(HIGHLIGHT_COLOR).darker(130).name()};
                color: {TEXT_COLOR};
            }}
        """
        
        self.onButton.setStyleSheet(on_button_style)
        self.offButton.setStyleSheet(off_button_style)
        
        # 创建按钮组，确保只有一个按钮被选中
        buttonGroup = QButtonGroup(self)
        buttonGroup.addButton(self.onButton)
        buttonGroup.addButton(self.offButton)
        buttonGroup.setExclusive(True)  # 确保互斥
        
        # 将按钮添加到开关布局
        switchLayout.addWidget(self.onButton)
        switchLayout.addWidget(self.offButton)
        
        # 默认选择"开"按钮
        self.onButton.setChecked(True)
        
        # 添加开关及状态文字
        switchAreaWidget = QWidget()
        switchAreaLayout = QVBoxLayout(switchAreaWidget)
        switchAreaLayout.setContentsMargins(0, 0, 0, 0)
        switchAreaLayout.setSpacing(2)  # 减小开关区域内部间距
        
        # 状态文字
        statusLayout = QHBoxLayout()
        statusLayout.setContentsMargins(0, 2, 0, 0)  # 减小状态文字的上边距
        
        self.statusLabel = QLabel("设备已可被发现")
        self.statusLabel.setStyleSheet(f"color: {TEXT_COLOR}; font-size: 15px;")
        self.statusLabel.setAlignment(Qt.AlignCenter)
        
        statusLayout.addStretch()
        statusLayout.addWidget(self.statusLabel)
        statusLayout.addStretch()
        
        # 添加到开关区域布局
        switchAreaLayout.addWidget(self.switchWidget, 0, Qt.AlignCenter)
        switchAreaLayout.addLayout(statusLayout)
        
        # 状态面板（初始隐藏）
        self.statusPanel = StatusPanel()
        self.statusPanel.setVisible(False)
        
        # 设置主布局
        contentLayout.addWidget(logoContainer, 0, Qt.AlignCenter)  # 居中显示标志
        contentLayout.addSpacing(5)  # 减小logo与标题之间的间距
        contentLayout.addWidget(titleLabel)
        contentLayout.addWidget(deviceIdLabel)
        contentLayout.addSpacing(10)  # 在标题和开关之间添加间距
        contentLayout.addWidget(switchAreaWidget)
        contentLayout.addStretch(1)  # 添加弹性空间
        
        # 设置内容容器样式
        contentWidget.setStyleSheet(f"""
            background-color: {PANEL_BG};
            border-radius: 12px;
            margin: 5px;
        """)
        
        # 添加到主布局
        layout.addWidget(contentWidget)
        layout.addWidget(self.statusPanel)  # 状态面板添加到主窗口
        
        # 设置整体样式
        self.setStyleSheet(f"background-color: {MAIN_BG};")
        
        # 连接开关信号
        self.onButton.toggled.connect(self.onSwitchToggled)
        self.offButton.toggled.connect(self.onSwitchToggled)
        
        # 测试状态面板显示 - 开发时使用
        # QTimer.singleShot(1000, self.simulateReceive)
    
    def simulateReceive(self):
        """模拟接收文件，用于开发测试"""
        self.statusPanel.showProgress("测试文件.pdf")
        
        progress = 0
        
        # 模拟进度更新
        def updateProgress():
            nonlocal progress
            progress += 5
            self.statusPanel.progressBar.setValue(progress)
            if progress >= 100:
                self.statusPanel.showCompleted("测试文件.pdf")
                return
            QTimer.singleShot(100, updateProgress)
        
        QTimer.singleShot(200, updateProgress)
    
    def onSwitchToggled(self, checked):
        """开关状态切换"""
        sender = self.sender()
        
        if sender == self.onButton and checked:
            self.statusLabel.setText("设备已可被发现")
            self.logoWidget.setActive(True)
        else:
            self.statusLabel.setText("传输功能已关闭")
            self.logoWidget.setActive(False)
            # 重置状态面板
            self.resetStatusPanel()
    
    def resetStatusPanel(self):
        """重置状态面板，在切换到关闭状态或完成传输后调用"""
        # 使用淡出动画重置状态面板
        if self.statusPanel.isVisible():
            self.statusPanel.fadeOutAndReset()

class SendPanel(QWidget):
    """发送文件界面"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)  # 边距
        
        # 设置尺寸策略
        sizePolicy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        sizePolicy.setVerticalStretch(1)
        self.setSizePolicy(sizePolicy)
        
        # ===== 顶部区域：附件列表 =====
        topAreaWidget = QWidget()
        topAreaWidget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        topAreaLayout = QVBoxLayout(topAreaWidget)
        topAreaLayout.setContentsMargins(15, 15, 15, 15)  # 内部边距
        
        # 标题：附件列表
        titleLabel = QLabel("附件列表")
        titleLabel.setStyleSheet(f"""
            color: {TEXT_COLOR}; 
            font-size: 20px; 
            font-weight: bold;
            padding: 5px 0;
            margin-bottom: 5px;
        """)
        titleLabel.setAlignment(Qt.AlignLeft)
        
        # 标题栏布局，包含标题和"全部删除"按钮
        titleBarLayout = QHBoxLayout()
        titleBarLayout.setContentsMargins(0, 0, 0, 0)
        titleBarLayout.addWidget(titleLabel)
        
        # 全部删除按钮
        self.clearAllButton = QPushButton("全部删除")
        self.clearAllButton.setCursor(Qt.PointingHandCursor)
        self.clearAllButton.setStyleSheet(f"""
            QPushButton {{
                background-color: {BUTTON_BG};
                color: {TEXT_COLOR};
                border: none;
                border-radius: 4px;
                padding: 5px 10px;
                font-size: 13px;
                min-width: 0;
                max-width: 80px;
            }}
            QPushButton:hover {{
                background-color: #E55050;
                color: white;
            }}
            QPushButton:pressed {{
                background-color: #D44040;
            }}
            QPushButton:disabled {{
                background-color: {BUTTON_BG};
                color: {SECONDARY_TEXT_COLOR};
                opacity: 0.6;
            }}
        """)
        self.clearAllButton.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.clearAllButton.clicked.connect(self.clearAllFiles)
        self.clearAllButton.setEnabled(False)  # 初始状态禁用
        
        titleBarLayout.addWidget(self.clearAllButton)
        
        # 文件列表区域
        self.fileListWidget = QWidget()
        self.fileListWidget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        fileListLayout = QVBoxLayout(self.fileListWidget)
        fileListLayout.setContentsMargins(0, 0, 0, 0)  # 减少内部边距
        
        # 文件列表
        self.fileList = FileListWidget()
        self.fileList.setMinimumHeight(120)
        self.fileList.setSelectionMode(QListWidget.SingleSelection)  # 仅允许单选
        self.fileList.itemSelectionChanged.connect(self.onFileSelectionChanged)  # 添加选择变化事件处理
        
        # 添加到文件列表布局
        fileListLayout.addWidget(self.fileList)
        
        # 文件操作按钮区域
        buttonAreaWidget = QWidget()
        buttonAreaLayout = QHBoxLayout(buttonAreaWidget)
        buttonAreaLayout.setContentsMargins(0, 5, 0, 5)  # 减少内部边距
        
        # 添加文件按钮
        self.addFileButton = QPushButton("添加文件")
        self.addFileButton.setStyleSheet(f"""
            QPushButton {{
                background-color: {HIGHLIGHT_COLOR};
                color: {TEXT_COLOR};
                border: none;
                padding: 8px 15px;
                border-radius: 5px;
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {QColor(HIGHLIGHT_COLOR).lighter(115).name()};
            }}
            QPushButton:pressed {{
                background-color: {QColor(HIGHLIGHT_COLOR).darker(110).name()};
            }}
        """)
        self.addFileButton.clicked.connect(self.addFiles)
        
        # 单文件发送标签
        self.singleSendLabel = QLabel("仅支持单文件发送")
        self.singleSendLabel.setStyleSheet(f"color: {SECONDARY_TEXT_COLOR}; font-size: 14px;")
        self.singleSendLabel.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        
        # 添加到按钮布局
        buttonAreaLayout.addWidget(self.addFileButton)
        buttonAreaLayout.addWidget(self.singleSendLabel)
        buttonAreaLayout.addStretch()
        
        # 添加到顶部区域布局
        topAreaLayout.addLayout(titleBarLayout)
        topAreaLayout.addWidget(self.fileListWidget, 1)  # 使用比例因子1
        topAreaLayout.addWidget(buttonAreaWidget)
        
        # 设置顶部区域样式
        topAreaWidget.setStyleSheet(f"""
            background-color: {PANEL_BG};
            border-radius: 8px;
            border: none;
        """)
        
        # ===== 发送状态面板 =====
        self.statusPanel = StatusPanel()
        self.statusPanel.setVisible(False)  # 初始隐藏状态面板
        
        # ===== 底部区域：附近设备 =====
        
        # 搜索设备组件
        self.deviceSearchWidget = QWidget()
        self.deviceSearchWidget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        searchLayout = QVBoxLayout(self.deviceSearchWidget)
        searchLayout.setContentsMargins(15, 15, 15, 15)  # 内部边距
        
        # 搜索状态标题和动画指示器水平布局
        searchTitleLayout = QHBoxLayout()
        searchTitleLayout.setContentsMargins(0, 0, 0, 0)
        
        # 搜索状态标题
        searchTitle = QLabel("附近设备")
        searchTitle.setStyleSheet(f"""
            color: {TEXT_COLOR}; 
            font-size: 20px; 
            font-weight: bold;
            padding: 5px 0;
            margin-bottom: 5px;
        """)
        searchTitle.setAlignment(Qt.AlignLeft)
        
        # 旋转动画指示器和状态标签水平布局
        statusLayout = QHBoxLayout()
        statusLayout.setContentsMargins(0, 0, 0, 0)
        self.searchAnimation = AnimationWidget()
        self.searchStatusLabel = QLabel("正在搜索附近设备...")
        self.searchStatusLabel.setStyleSheet(f"color: {SECONDARY_TEXT_COLOR}; font-size: 14px;")
        
        statusLayout.addWidget(self.searchAnimation)
        statusLayout.addWidget(self.searchStatusLabel)
        
        # 将标题和状态指示器添加到同一行布局
        searchTitleLayout.addWidget(searchTitle)
        searchTitleLayout.addSpacing(5)  # 添加很小的间距
        searchTitleLayout.addLayout(statusLayout)
        searchTitleLayout.addStretch()  # 将剩余空间推到右侧
        
        # 创建一个容器Widget来承载标题布局
        searchTitleWidget = QWidget()
        searchTitleWidget.setLayout(searchTitleLayout)
        
        # 添加到搜索布局
        searchLayout.addWidget(searchTitleWidget)
        
        # 设备列表
        self.deviceList = QListWidget()
        self.deviceList.setStyleSheet(f"""
            QListWidget {{
                background-color: {INNER_BG};
                border-radius: 6px;
                border: none;
                padding: 5px;
                color: {TEXT_COLOR};
            }}
            QListWidget::item {{
                background-color: {LIST_ITEM_BG};
                border-radius: 4px;
                margin: 3px 0px;
                padding: 10px;
            }}
            QListWidget::item:hover {{
                background-color: {QColor(LIST_ITEM_BG).lighter(115).name()};
            }}
            QListWidget::item:selected {{
                background-color: {QColor(HIGHLIGHT_COLOR).darker(120).name()};
                color: {TEXT_COLOR};
                border: none;
                border-left: 3px solid {QColor(HIGHLIGHT_COLOR).lighter(130).name()};
                font-weight: bold;
            }}
        """)
        self.deviceList.setMinimumHeight(100)
        self.deviceList.setMaximumHeight(200)
        
        # 添加到搜索布局
        searchLayout.addWidget(self.deviceList)
        
        # 发送按钮
        self.sendButton = QPushButton("发送文件")
        self.sendButton.setStyleSheet(f"""
            QPushButton {{
                background-color: {HIGHLIGHT_COLOR};
                color: {TEXT_COLOR};
                border: none;
                padding: 12px 30px;
                border-radius: 5px;
                font-size: 16px;
                font-weight: bold;
                margin-top: 10px;
            }}
            QPushButton:hover {{
                background-color: {QColor(HIGHLIGHT_COLOR).lighter(115).name()};
            }}
            QPushButton:pressed {{
                background-color: {QColor(HIGHLIGHT_COLOR).darker(110).name()};
            }}
            QPushButton:disabled {{
                background-color: {BUTTON_BG};
                color: {SECONDARY_TEXT_COLOR};
            }}
        """)
        self.sendButton.setEnabled(False)  # 初始没有文件时禁用
        
        # 设置底部区域样式
        self.deviceSearchWidget.setStyleSheet(f"""
            background-color: {PANEL_BG};
            border-radius: 8px;
            border: none;
        """)
        
        # 添加到主布局
        layout.addWidget(topAreaWidget, 3)  # 给顶部区域分配3份比例
        layout.addSpacing(10)
        layout.addWidget(self.statusPanel)  # 添加状态面板
        layout.addSpacing(10)
        layout.addWidget(self.deviceSearchWidget, 2)  # 给设备列表分配2份比例
        layout.addSpacing(10)
        layout.addWidget(self.sendButton, 0, Qt.AlignCenter)
        
        # 配置拖放功能
        self.setAcceptDrops(True)
        
        # 模拟搜索设备
        QTimer.singleShot(2000, self.simulateDeviceFound)
    
    def addFiles(self):
        """添加文件按钮点击事件"""
        files, _ = QFileDialog.getOpenFileNames(self, "选择文件")
        if files:
            self.addFilesToList(files)
    
    def addFilesToList(self, file_paths):
        """添加文件到列表"""
        for path in file_paths:
            # 提取文件名，不包含路径
            file_name = os.path.basename(path)
            
            # 创建包含文件名和大小的条目
            try:
                size = os.path.getsize(path)
                if size < 1024:
                    size_str = f"{size} B"
                elif size < 1024 * 1024:
                    size_str = f"{size/1024:.1f} KB"
                else:
                    size_str = f"{size/(1024*1024):.1f} MB"
            except:
                size_str = "未知大小"
            
            # 创建自定义列表项
            item = QListWidgetItem(self.fileList)
            item.setData(Qt.UserRole, path)  # 存储完整路径
            
            # 创建自定义部件
            file_widget = FileItemWidget(file_name, size_str, path)
            file_widget.setProperty("list_item", item)  # 存储列表项引用
            file_widget.deleteClicked.connect(self.removeFileItem)
            
            # 设置列表项尺寸
            item.setSizeHint(file_widget.sizeHint())
            
            # 将自定义部件添加到列表项
            self.fileList.addItem(item)
            self.fileList.setItemWidget(item, file_widget)
        
        # 启用清除按钮（只要有文件就启用）
        has_files = self.fileList.count() > 0
        self.clearAllButton.setEnabled(has_files)
        
        # 发送按钮状态由文件选择状态控制
        selected_items = self.fileList.selectedItems()
        self.sendButton.setEnabled(len(selected_items) > 0)
    
    def removeFileItem(self, item):
        """从列表中移除文件项"""
        row = self.fileList.row(item)
        if row >= 0:
            self.fileList.takeItem(row)
            
        # 更新按钮状态
        has_files = self.fileList.count() > 0
        self.sendButton.setEnabled(has_files)
        self.clearAllButton.setEnabled(has_files)
    
    def clearAllFiles(self):
        """清除所有文件"""
        # 弹出确认对话框
        confirm = True  # 在实际应用中可能需要弹窗确认
        
        if confirm:
            self.fileList.clear()
            self.sendButton.setEnabled(False)
            self.clearAllButton.setEnabled(False)
    
    def dragEnterEvent(self, event):
        """拖动进入事件"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            # 拖动时可以更改列表的边框样式而不是原来的提示标签
            self.fileList.setStyleSheet(f"""
                QListWidget {{
                    background-color: {INNER_BG};
                    border: 2px dashed {HIGHLIGHT_COLOR};
                    border-radius: 8px;
                    padding: 5px;
                }}
                QListWidget::item {{
                    background-color: {LIST_ITEM_BG};
                    border-radius: 6px;
                    margin: 2px 0px;
                    padding: 0px;
                    color: {TEXT_COLOR};
                }}
                QListWidget::item:hover {{
                    background-color: {QColor(LIST_ITEM_BG).lighter(115).name()};
                }}
                QListWidget::item:selected {{
                    background-color: {QColor(HIGHLIGHT_COLOR).darker(120).name()};
                    color: {TEXT_COLOR};
                    border: none;
                    font-weight: bold;
                }}
            """)
    
    def dragLeaveEvent(self, event):
        """拖动离开事件"""
        # 恢复列表的原始样式
        self.fileList.setStyleSheet(f"""
            QListWidget {{
                background-color: {INNER_BG};
                border: none;
                border-radius: 8px;
                padding: 5px;
            }}
            QListWidget::item {{
                background-color: {LIST_ITEM_BG};
                border-radius: 6px;
                margin: 2px 0px;
                padding: 0px;
                color: {TEXT_COLOR};
            }}
            QListWidget::item:hover {{
                background-color: {QColor(LIST_ITEM_BG).lighter(115).name()};
            }}
            QListWidget::item:selected {{
                background-color: {QColor(HIGHLIGHT_COLOR).darker(120).name()};
                color: {TEXT_COLOR};
                border: none;
                font-weight: bold;
            }}
        """)
    
    def dropEvent(self, event):
        """放置事件"""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            file_paths = [url.toLocalFile() for url in urls]
            self.addFilesToList(file_paths)
            # 恢复列表的原始样式
            self.fileList.setStyleSheet(f"""
                QListWidget {{
                    background-color: {INNER_BG};
                    border: none;
                    border-radius: 8px;
                    padding: 5px;
                }}
                QListWidget::item {{
                    background-color: {LIST_ITEM_BG};
                    border-radius: 6px;
                    margin: 2px 0px;
                    padding: 0px;
                    color: {TEXT_COLOR};
                }}
                QListWidget::item:hover {{
                    background-color: {QColor(LIST_ITEM_BG).lighter(115).name()};
                }}
                QListWidget::item:selected {{
                    background-color: {QColor(HIGHLIGHT_COLOR).darker(120).name()};
                    color: {TEXT_COLOR};
                    border: none;
                    font-weight: bold;
                }}
            """)
            
    def simulateDeviceFound(self):
        """模拟发现设备"""
        # 不再添加模拟设备
        devices = []
        
        # 更新搜索状态
        self.searchStatusLabel.setText(f"找到 {len(devices)} 个设备")

    def onFileSelectionChanged(self):
        """处理文件选择变化事件"""
        # 只有在有文件被选中时才启用发送按钮
        selected_items = self.fileList.selectedItems()
        self.sendButton.setEnabled(len(selected_items) > 0)

class SettingsPanel(QWidget):
    """设置界面"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)  # 增加边距
        
        # 创建内容容器
        contentWidget = QWidget()
        contentLayout = QVBoxLayout(contentWidget)
        contentLayout.setContentsMargins(20, 20, 20, 20)
        
        # 标题
        titleLabel = QLabel("设置")
        titleLabel.setStyleSheet(f"color: {TEXT_COLOR}; font-size: 24px; font-weight: bold;")
        
        # 保存路径设置
        savePathLayout = QGridLayout()
        savePathLayout.setContentsMargins(0, 15, 0, 0)
        
        savePathLabel = QLabel("默认保存路径:")
        savePathLabel.setStyleSheet(f"color: {TEXT_COLOR}; font-size: 14px;")
        
        self.savePathEdit = QLabel("/Users/Documents/LocalSend")
        self.savePathEdit.setStyleSheet(f"""
            background-color: {INNER_BG};
            color: {TEXT_COLOR};
            padding: 8px;
            border-radius: 4px;
            border: none;
        """)
        
        self.browseButton = QPushButton("浏览...")
        self.browseButton.setStyleSheet(f"""
            QPushButton {{
                background-color: {BUTTON_BG};
                color: {TEXT_COLOR};
                border: none;
                padding: 8px 15px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {BUTTON_HOVER};
            }}
            QPushButton:pressed {{
                background-color: {QColor(BUTTON_BG).darker(110).name()};
            }}
        """)
        self.browseButton.clicked.connect(self.browseSavePath)
        
        savePathLayout.addWidget(savePathLabel, 0, 0)
        savePathLayout.addWidget(self.savePathEdit, 0, 1)
        savePathLayout.addWidget(self.browseButton, 0, 2)
        
        # 添加到内容布局
        contentLayout.addWidget(titleLabel)
        contentLayout.addLayout(savePathLayout)
        contentLayout.addStretch()
        
        # 设置内容容器样式
        contentWidget.setStyleSheet(f"""
            background-color: {PANEL_BG};
            border-radius: 12px;
            border: none;
        """)
        
        # 添加到主布局
        layout.addWidget(contentWidget)
    
    def browseSavePath(self):
        """选择保存路径"""
        # 此方法仅为了保持接口一致性而存在
        # 实际实现在 SendNowApp.on_browse_save_dir 中，避免重复打开文件对话框
        pass

class MainWindow(QMainWindow):
    """主窗口"""
    
    # 设置默认窗口尺寸和比例常量
    DEFAULT_WIDTH = 1000
    DEFAULT_HEIGHT = 700
    ASPECT_RATIO = DEFAULT_WIDTH / DEFAULT_HEIGHT  # 宽高比例常量
    
    def __init__(self):
        super().__init__()
        self.initUI()
    
    def initUI(self):
        self.setWindowTitle("SendNow")  # 修改窗口标题
        self.setMinimumSize(900, 600)  # 最小窗口尺寸
        self.resize(self.DEFAULT_WIDTH, self.DEFAULT_HEIGHT)  # 设置默认大小
        
        # 设置应用程序图标
        app_icon = QIcon("icons/sendnow_logo.svg")
        self.setWindowIcon(app_icon)
        
        # 设置应用风格
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{
                background-color: {MAIN_BG};
                border: none;
            }}
            QScrollBar:vertical {{
                background: {MAIN_BG};
                width: 10px;
                margin: 0px;
                border: none;
            }}
            QScrollBar::handle:vertical {{
                background: {INNER_BG};
                min-height: 20px;
                border-radius: 5px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar:horizontal {{
                background: {MAIN_BG};
                height: 10px;
                margin: 0px;
                border: none;
            }}
            QScrollBar::handle:horizontal {{
                background: {INNER_BG};
                min-width: 20px;
                border-radius: 5px;
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
            }}
        """)
        
        # 创建主布局
        mainLayout = QHBoxLayout()
        mainLayout.setContentsMargins(0, 0, 0, 0)  # 去除所有边距
        mainLayout.setSpacing(0)  #, 去除间距
        centralWidget = QWidget()
        centralWidget.setLayout(mainLayout)
        self.setCentralWidget(centralWidget)
        
        # 创建左侧导航栏
        navBar = QFrame()
        navBar.setStyleSheet("background-color: #000000;")  # 黑色背景
        navBar.setFixedWidth(120)  # 增加导航栏宽度
        navLayout = QVBoxLayout(navBar)
        navLayout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        navLayout.setSpacing(10)  # 减少间距
        navLayout.setContentsMargins(0, 0, 0, 0)  # 去除边距
        
        # 应用标题
        appTitle = QLabel("SendNow")  # 修改应用名称
        appTitle.setStyleSheet(f"""
            color: {TEXT_COLOR}; 
            font-size: 22px; 
            font-weight: bold;
            padding: 15px 0;
            background-color: #000000;
            border-radius: 0px;
            text-align: center;
        """)
        appTitle.setAlignment(Qt.AlignCenter)
        navLayout.addWidget(appTitle)
        navLayout.addSpacing(5)  # 减少间距
        
        # 导航按钮
        # 实际使用时需要替换为真实的图标路径
        self.receiveButton = NavigationButton("icons/receive.svg", "接收")
        self.sendButton = NavigationButton("icons/send.svg", "发送")
        self.settingsButton = NavigationButton("icons/settings.svg", "设置")
        
        self.buttonGroup = QButtonGroup(self)
        self.buttonGroup.addButton(self.receiveButton)
        self.buttonGroup.addButton(self.sendButton)
        self.buttonGroup.addButton(self.settingsButton)
        self.buttonGroup.buttonClicked.connect(self.onNavButtonClicked)
        
        for button in [self.receiveButton, self.sendButton, self.settingsButton]:
            navLayout.addWidget(button)
        
        navLayout.addStretch()
        
        # 创建堆叠窗口（用于切换界面）
        self.stack = QStackedWidget()
        
        # 创建三个面板
        self.receivePanel = ReceivePanel()
        self.sendPanel = SendPanel()
        self.settingsPanel = SettingsPanel()
        
        # 添加到堆叠窗口
        self.stack.addWidget(self.receivePanel)
        self.stack.addWidget(self.sendPanel)
        self.stack.addWidget(self.settingsPanel)
        
        # 添加到主布局
        mainLayout.addWidget(navBar)
        mainLayout.addWidget(self.stack)
        
        # 默认选中"接收"页面
        self.receiveButton.setChecked(True)
        self.stack.setCurrentWidget(self.receivePanel)
    
    def onNavButtonClicked(self, button):
        """处理导航按钮点击事件"""
        if button == self.receiveButton:
            self.stack.setCurrentWidget(self.receivePanel)
        elif button == self.sendButton:
            self.stack.setCurrentWidget(self.sendPanel)
        elif button == self.settingsButton:
            self.stack.setCurrentWidget(self.settingsPanel)
            
    def resizeEvent(self, event):
        """重写调整大小事件，保持宽高比"""
        super().resizeEvent(event)
        
        # 获取当前尺寸
        width = event.size().width()
        height = event.size().height()
        current_ratio = width / height
        
        # 如果当前比例与目标比例相差太大，调整窗口大小
        if abs(current_ratio - self.ASPECT_RATIO) > 0.05:  # 允许5%的误差
            if current_ratio > self.ASPECT_RATIO:
                # 当前窗口太宽，根据高度调整宽度
                new_width = int(height * self.ASPECT_RATIO)
                self.resize(new_width, height)
            else:
                # 当前窗口太高，根据宽度调整高度
                new_height = int(width / self.ASPECT_RATIO)
                self.resize(width, new_height)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 设置应用程序图标
    app_icon = QIcon("icons/sendnow_logo.svg")
    app.setWindowIcon(app_icon)
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec_()) 