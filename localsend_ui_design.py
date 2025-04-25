import sys
import random
import hashlib
import os
import math  # 添加math模块导入
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QFileDialog, 
                             QProgressBar, QListWidget, QListWidgetItem, QStackedWidget, 
                             QFrame, QSplitter, QGridLayout, QSpacerItem, QSizePolicy,
                             QButtonGroup, QToolButton, QAction)
from PyQt5.QtCore import Qt, QSize, pyqtSignal, QMimeData, QUrl, QTimer, QRect, QPoint, QPointF
from PyQt5.QtGui import QIcon, QColor, QPalette, QFont, QDrag, QPainter, QPen, QBrush, QPainterPath, QRadialGradient, QLinearGradient, QTransform

# 更高对比度的赛博朋克风格色调
DARK_BG = "#0A0B15"        # 更暗的导航栏背景色，增强对比度
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
        self.setMinimumSize(160, 160)
        self.setMaximumSize(240, 240)
        
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
        
    def paintEvent(self, event):
        """绘制标志"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 获取中心点和半径
        center = QPoint(self.width() // 2, self.height() // 2)
        radius = min(self.width(), self.height()) // 2 - 10
        
        # 绘制主圆
        painter.setPen(Qt.NoPen)
        main_gradient = QRadialGradient(center, radius)
        main_gradient.setColorAt(0, QColor(PANEL_BG).lighter(130))
        main_gradient.setColorAt(1, QColor(PANEL_BG))
        painter.setBrush(QBrush(main_gradient))
        painter.drawEllipse(center, radius, radius)
        
        # 绘制旋转的圆环
        pen_width = radius * 0.06
        ring_radius = radius * 0.8
        pen = QPen(self.base_color)
        pen.setWidth(pen_width)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        
        # 绘制分段圆环 (6个弧形)
        segments = 6
        arc_length = 360 / segments
        gap_angle = arc_length * 0.3  # 30% 的间隙
        segment_angle = arc_length - gap_angle
        
        for i in range(segments):
            start_angle = (i * arc_length + self.angle) % 360
            painter.drawArc(
                center.x() - ring_radius,
                center.y() - ring_radius,
                ring_radius * 2,
                ring_radius * 2,
                start_angle * 16,
                segment_angle * 16
            )
        
        # 绘制内部放射状线条
        inner_radius = radius * 0.4
        painter.setPen(QPen(self.accent_color, pen_width * 0.6))
        
        inner_lines = 8
        for i in range(inner_lines):
            angle = (i * (360 / inner_lines) + self.inner_angle) % 360
            rad_angle = math.radians(angle)
            x1 = center.x() + inner_radius * 0.3 * math.cos(rad_angle)
            y1 = center.y() + inner_radius * 0.3 * math.sin(rad_angle)
            x2 = center.x() + inner_radius * math.cos(rad_angle)
            y2 = center.y() + inner_radius * math.sin(rad_angle)
            
            painter.drawLine(QPoint(int(x1), int(y1)), QPoint(int(x2), int(y2)))
        
        # 绘制中心圆和字母 S
        center_radius = radius * 0.25
        painter.setPen(Qt.NoPen)
        center_gradient = QRadialGradient(center, center_radius)
        center_gradient.setColorAt(0, self.base_color.lighter(130))
        center_gradient.setColorAt(1, self.base_color)
        painter.setBrush(QBrush(center_gradient))
        painter.drawEllipse(center, center_radius, center_radius)
        
        # 绘制字母 "S"
        s_size = center_radius * 1.2
        font = QFont("Arial", s_size)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QPen(QColor(TEXT_COLOR)))
        
        text_rect = QRect(
            center.x() - s_size/2, 
            center.y() - s_size/2,
            s_size, 
            s_size
        )
        painter.drawText(text_rect, Qt.AlignCenter, "S")
        
        # 更新角度
        self.angle = (self.angle + 0.5) % 360
        self.inner_angle = (self.inner_angle - 1) % 360

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
                border-left: 4px solid {HIGHLIGHT_COLOR};
            }}
            QToolButton:hover:!checked {{
                color: {TEXT_COLOR};
                background-color: rgba(255, 255, 255, 0.15);
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
    
    def __init__(self, file_name, size_str, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # 文件名和大小标签
        self.fileLabel = QLabel(f"{file_name} ({size_str})")
        self.fileLabel.setStyleSheet(f"color: {TEXT_COLOR}; font-size: 13px;")
        
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
        
        # 添加到布局
        layout.addWidget(self.fileLabel, 1)  # 1表示伸展因子
        layout.addWidget(self.deleteButton, 0, Qt.AlignRight)  # 右对齐
        
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
        
        # 添加到主布局
        layout.addStretch()
        layout.addWidget(self.statusLabel)
        layout.addWidget(self.progressBar)
        layout.addWidget(self.actionsWidget)
        layout.addStretch()
        
        # 初始隐藏状态文本和进度条
        self.statusLabel.setVisible(False)
        self.progressBar.setVisible(False)
    
    def showProgress(self, file_name=None):
        """显示进度条和状态"""
        self.statusLabel.setVisible(True)
        self.progressBar.setVisible(True)
        self.actionsWidget.setVisible(False)
        
        if file_name:
            self.statusLabel.setText(f"正在接收文件：{file_name}")
    
    def showCompleted(self, file_name):
        """显示传输完成状态"""
        self.statusLabel.setText(f"已接收：{file_name}")
        self.progressBar.setValue(100)
        self.actionsWidget.setVisible(True)
    
    def reset(self):
        """重置状态面板"""
        self.statusLabel.setVisible(False)
        self.progressBar.setVisible(False)
        self.actionsWidget.setVisible(False)
        self.progressBar.setValue(0)

    def setStatus(self, status_text):
        """设置状态文本并确保其可见"""
        self.statusLabel.setText(status_text)
        self.statusLabel.setVisible(True)

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
        layout.setContentsMargins(20, 20, 20, 20)  # 增加边距
        
        # 创建一个内容容器
        contentWidget = QWidget()
        contentLayout = QVBoxLayout(contentWidget)
        contentLayout.setContentsMargins(25, 30, 25, 30)  # 增加内边距提高内容集中度
        contentLayout.setSpacing(20)
        
        # 获取设备名称和ID
        self.device_name, self.device_id = DeviceNameGenerator.get_persistent_name_and_id()
        
        # 添加动态标志
        self.logoWidget = DynamicLogoWidget()
        
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
        switchLayout.setContentsMargins(0, 10, 0, 10)
        
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
                padding: 8px 25px;
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
                padding: 8px 25px;
                border-top-right-radius: 15px;
                border-bottom-right-radius: 15px;
            }}
            QPushButton:checked {{
                background-color: {HIGHLIGHT_COLOR};
                color: {TEXT_COLOR};
            }}
        """
        
        self.onButton.setStyleSheet(on_button_style)
        self.offButton.setStyleSheet(off_button_style)
        
        # 创建按钮组使它们互斥
        self.buttonGroup = QButtonGroup(self)
        self.buttonGroup.addButton(self.onButton)
        self.buttonGroup.addButton(self.offButton)
        self.buttonGroup.setExclusive(True)
        
        # 添加到布局
        switchLayout.addWidget(self.onButton)
        switchLayout.addWidget(self.offButton)
        
        # 默认选中开启
        self.onButton.setChecked(True)
        
        # 状态面板
        self.statusPanel = StatusPanel()
        
        # 添加到内容布局
        contentLayout.addWidget(self.logoWidget, 0, Qt.AlignCenter)
        contentLayout.addWidget(titleLabel)
        contentLayout.addWidget(deviceIdLabel)
        contentLayout.addWidget(self.switchWidget, 0, Qt.AlignCenter)
        contentLayout.addWidget(self.statusPanel)
        
        # 设置内容容器样式
        contentWidget.setStyleSheet(f"""
            background-color: {PANEL_BG};
            border-radius: 12px;
            border: none;
            box-shadow: 0px 3px 10px rgba(0, 0, 0, 0.2);
        """)
        
        # 添加到主布局
        layout.addWidget(contentWidget)
        
        # 模拟接收测试按钮 (仅开发调试用)
        self.testButton = QPushButton("模拟接收文件 (测试)")
        self.testButton.setStyleSheet(f"""
            QPushButton {{
                background-color: #555555;
                color: white;
                border: none;
                padding: 5px 10px;
                border-radius: 3px;
                font-size: 12px;
            }}
        """)
        self.testButton.clicked.connect(self.simulateReceive)
        layout.addWidget(self.testButton, 0, Qt.AlignRight)
        
        # 保存对AppController的引用
        self.controller = None
    
    def onDeviceFound(self, device):
        """设备发现回调"""
        # 在接收页面，我们通常只显示设备总数，不显示具体设备列表
        pass
    
    def onDeviceLost(self, device):
        """设备丢失回调"""
        # 在接收页面，我们通常只显示设备总数，不显示具体设备列表
        pass
    
    def onTransferRequest(self, device, files):
        """传输请求回调"""
        # 显示传输请求提示
        file_names = [f.file_name for f in files]
        file_str = "、".join(file_names[:3])
        if len(file_names) > 3:
            file_str += f"等 {len(file_names)} 个文件"
        
        self.statusPanel.setStatus(f"接收来自 {device.device_name} 的文件: {file_str}")
        self.statusPanel.showProgress()
    
    def onTransferProgress(self, file_info, progress, speed):
        """传输进度回调"""
        # 更新进度条
        self.statusPanel.progressBar.setValue(int(progress * 100))
        
        # 显示传输速度
        speed_str = "KB/s"
        speed_val = speed / 1024
        if speed_val > 1024:
            speed_str = "MB/s"
            speed_val /= 1024
        
        self.statusPanel.setStatus(
            f"正在接收: {file_info.file_name} - {speed_val:.1f} {speed_str}"
        )
    
    def onTransferComplete(self, file_info, is_sender):
        """传输完成回调"""
        if not is_sender:  # 只处理接收完成
            self.statusPanel.showCompleted(file_info.file_name)
    
    def onTransferError(self, file_info, error_message):
        """传输错误回调"""
        self.statusPanel.setStatus(f"传输错误: {error_message}")
    
    def simulateReceive(self):
        """模拟接收文件过程"""
        self.statusPanel.showProgress("document.pdf")
        
        # 创建一个模拟进度计时器
        self.progress_timer = QTimer(self)
        self.progress_value = 0
        
        def updateProgress():
            self.progress_value += 5
            self.statusPanel.progressBar.setValue(self.progress_value)
            
            if self.progress_value >= 100:
                self.progress_timer.stop()
                self.statusPanel.showCompleted("document.pdf")
        
        self.progress_timer.timeout.connect(updateProgress)
        self.progress_timer.start(200)  # 模拟网络延迟

class SendPanel(QWidget):
    """发送文件界面"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)  # 增加边距
        
        # ===== 顶部区域：附件列表 =====
        topAreaWidget = QWidget()
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
        fileListLayout = QVBoxLayout(self.fileListWidget)
        fileListLayout.setContentsMargins(0, 0, 0, 0)  # 减少内部边距
        
        # 文件列表
        self.fileList = FileListWidget()
        self.fileList.setMinimumHeight(120)
        self.fileList.setSelectionMode(QListWidget.ExtendedSelection)  # 允许多选
        
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
        
        # 多文件发送标签
        self.multiSendLabel = QLabel("可多文件发送")
        self.multiSendLabel.setStyleSheet(f"color: {SECONDARY_TEXT_COLOR}; font-size: 14px;")
        self.multiSendLabel.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        
        # 添加到按钮布局
        buttonAreaLayout.addWidget(self.addFileButton)
        buttonAreaLayout.addWidget(self.multiSendLabel)
        buttonAreaLayout.addStretch()
        
        # 添加到顶部区域布局
        topAreaLayout.addLayout(titleBarLayout)
        topAreaLayout.addWidget(self.fileListWidget)
        topAreaLayout.addWidget(buttonAreaWidget)
        
        # 设置顶部区域样式
        topAreaWidget.setStyleSheet(f"""
            background-color: {PANEL_BG};
            border-radius: 8px;
            border: none;
            box-shadow: 0px 2px 8px rgba(0, 0, 0, 0.15);
        """)
        
        # 保存对AppController的引用
        self.app_controller = None
        
        # ===== 底部区域：附近设备 =====
        
        # 搜索设备组件
        self.deviceSearchWidget = QWidget()
        searchLayout = QVBoxLayout(self.deviceSearchWidget)
        searchLayout.setContentsMargins(15, 15, 15, 15)  # 内部边距
        
        # 搜索状态标题和刷新按钮水平布局
        titleLayout = QHBoxLayout()
        titleLayout.setContentsMargins(0, 0, 0, 0)
        
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
        
        # 创建动画指示器
        self.searchAnimation = AnimationWidget()
        
        # 状态标签
        self.searchStatusLabel = QLabel("正在搜索附近设备...")
        self.searchStatusLabel.setStyleSheet(f"color: {SECONDARY_TEXT_COLOR}; font-size: 14px;")
        
        # 刷新按钮
        self.refreshButton = QPushButton("刷新")
        self.refreshButton.setCursor(Qt.PointingHandCursor)
        self.refreshButton.setStyleSheet(f"""
            QPushButton {{
                background-color: {BUTTON_BG};
                color: {TEXT_COLOR};
                border: none;
                border-radius: 4px;
                padding: 5px 15px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {QColor(BUTTON_BG).lighter(115).name()};
            }}
            QPushButton:pressed {{
                background-color: {QColor(BUTTON_BG).darker(110).name()};
            }}
        """)
        self.refreshButton.clicked.connect(self.refreshDevices)
        
        # 添加到标题布局
        titleLayout.addWidget(searchTitle)
        titleLayout.addWidget(self.searchAnimation)
        titleLayout.addWidget(self.searchStatusLabel)
        titleLayout.addStretch()
        titleLayout.addWidget(self.refreshButton)
        
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
        searchLayout.addLayout(titleLayout)
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
        
        # 状态标签 - 用于显示选择的设备和传输状态
        self.statusLabel = QLabel("请选择设备和文件")
        self.statusLabel.setStyleSheet(f"color: {TEXT_COLOR}; font-size: 14px;")
        self.statusLabel.setAlignment(Qt.AlignCenter)
        
        # 设置底部区域样式
        self.deviceSearchWidget.setStyleSheet(f"""
            background-color: {PANEL_BG};
            border-radius: 8px;
            border: none;
            box-shadow: 0px 2px 8px rgba(0, 0, 0, 0.15);
        """)
        
        # 添加到主布局
        layout.addWidget(topAreaWidget)
        layout.addSpacing(15)
        layout.addWidget(self.deviceSearchWidget)
        layout.addSpacing(10)
        layout.addWidget(self.statusLabel, 0, Qt.AlignCenter)  # 先添加状态标签
        layout.addWidget(self.sendButton, 0, Qt.AlignCenter)
        
        # 配置拖放功能
        self.setAcceptDrops(True)
        
        # 连接设备列表选择变化的信号
        self.deviceList.itemSelectionChanged.connect(self.updateSelectedDeviceInfo)
        
        # 创建设备扫描定时器，每10秒扫描一次
        self.scanTimer = QTimer(self)
        self.scanTimer.timeout.connect(self.refreshDevices)
        self.scanTimer.start(10000)  # 10秒
    
    def addFiles(self):
        """添加文件按钮点击事件"""
        files, _ = QFileDialog.getOpenFileNames(self, "选择文件")
        if files:
            self.addFilesToList(files)
    
    def addFilesToList(self, file_paths):
        """添加文件到列表"""
        for path in file_paths:
            # 检查是否已存在相同文件
            exists = False
            for i in range(self.fileList.count()):
                if self.fileList.item(i).data(Qt.UserRole) == path:
                    exists = True
                    break
            
            if not exists:
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
                file_widget = FileItemWidget(file_name, size_str)
                file_widget.setProperty("list_item", item)  # 存储列表项引用
                file_widget.deleteClicked.connect(self.removeFileItem)
                
                # 设置列表项尺寸
                item.setSizeHint(file_widget.sizeHint())
                
                # 将自定义部件添加到列表项
                self.fileList.addItem(item)
                self.fileList.setItemWidget(item, file_widget)
        
        # 启用发送按钮和清除按钮
        has_files = self.fileList.count() > 0
        self.sendButton.setEnabled(has_files)
        self.clearAllButton.setEnabled(has_files)
    
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
            
    def updateSelectedDeviceInfo(self, selectedItem=None):
        """更新所选设备信息"""
        if selectedItem is None:
            selectedItem = self.deviceList.currentItem()
        
        if selectedItem:
            device_id = selectedItem.data(100)
            # 不再使用selectedDeviceLabel，而是直接更新发送按钮状态
            if hasattr(self, 'sendButton'):
                self.sendButton.setEnabled(True)
            
            # 显示在状态标签中（如果有）
            if hasattr(self, 'statusLabel'):
                self.statusLabel.setText(f"已选择: {selectedItem.text()}")
        else:
            # 禁用发送按钮
            if hasattr(self, 'sendButton'):
                self.sendButton.setEnabled(False)
            
            # 显示在状态标签中（如果有）
            if hasattr(self, 'statusLabel'):
                self.statusLabel.setText("已选择: 无")

    def onTransferProgress(self, file_info, progress, speed):
        """传输进度回调"""
        # 在发送面板可以显示传输进度状态
        # 这里可以添加一个状态标签
        speed_str = "KB/s"
        speed_val = speed / 1024
        if speed_val > 1024:
            speed_str = "MB/s"
            speed_val /= 1024
        
        # 更新状态标签（如果有）
        if hasattr(self, 'statusLabel'):
            self.statusLabel.setText(
                f"正在发送: {file_info.file_name} - {progress*100:.1f}% ({speed_val:.1f} {speed_str})"
            )
    
    def onTransferComplete(self, file_info, is_sender):
        """传输完成回调"""
        if is_sender:  # 只处理发送完成
            # 更新状态标签（如果有）
            if hasattr(self, 'statusLabel'):
                self.statusLabel.setText(f"发送完成: {file_info.file_name}")
    
    def onTransferError(self, file_info, error_message):
        """传输错误回调"""
        # 更新状态标签（如果有）
        if hasattr(self, 'statusLabel'):
            self.statusLabel.setText(f"发送错误: {error_message}")
    
    def sendFiles(self):
        """发送文件按钮点击事件"""
        # 检查是否有选择的设备
        selected_device = self.deviceList.currentItem()
        if not selected_device:
            self.statusLabel.setText("请先选择一个设备")
            return
        
        # 获取设备ID
        device_id = selected_device.data(100)
        
        # 获取所有待发送文件路径
        file_paths = []
        for i in range(self.fileList.count()):
            file_paths.append(self.fileList.item(i).data(Qt.UserRole))
        
        if not file_paths:
            self.statusLabel.setText("请先添加要发送的文件")
            return
        
        # 如果AppController可用，使用它发送文件
        if self.app_controller:
            # 发送文件
            self.statusLabel.setText("正在发送文件...")
            transfer_ids = self.app_controller.send_files(device_id, file_paths)
            
            if transfer_ids:
                self.statusLabel.setText(f"已开始发送 {len(transfer_ids)} 个文件...")
            else:
                self.statusLabel.setText("文件发送失败，请检查网络连接")
        else:
            # 模拟发送成功
            print(f"模拟发送文件到设备 {device_id}: {file_paths}")
            self.statusLabel.setText("模拟发送文件（仅测试模式）")

    def setAppController(self, controller):
        """设置AppController引用"""
        self.app_controller = controller
        
        # 连接设备发现信号
        if self.app_controller:
            self.app_controller.deviceFound.connect(self.onDeviceFound)
            self.app_controller.deviceLost.connect(self.onDeviceLost)
            
            # 立即填充设备列表
            self.populateDeviceList()
    
    def refreshDevices(self):
        """刷新附近设备列表"""
        # 显示刷新状态
        self.searchStatusLabel.setText("正在刷新附近设备...")
        
        # 确保动画可见并运行
        self.searchAnimation.show()
        
        if self.app_controller:
            # 清空当前设备列表
            self.deviceList.clear()
            
            # 直接获取当前已知设备并显示
            self.populateDeviceList()
            
            # 主动触发一次设备发现（这将在后台进行）
            # 注意：NetworkManager的设备发现在discover_loop中自动进行
            # 这里只需要确保定时器在运行即可
            pass
        else:
            # 如果没有controller，使用模拟数据（开发测试用）
            QTimer.singleShot(2000, self.simulateDeviceDiscovery)
    
    def populateDeviceList(self):
        """填充设备列表"""
        if not self.app_controller:
            return
            
        # 获取当前已知设备
        devices = self.app_controller.get_devices()
        
        # 添加到列表
        for device in devices:
            self.addDeviceToList(device)
        
        # 更新状态消息
        self.searchStatusLabel.setText(f"找到 {len(devices)} 个设备")
    
    def addDeviceToList(self, device):
        """添加设备到列表"""
        # 检查是否已经在列表中
        for i in range(self.deviceList.count()):
            if self.deviceList.item(i).data(100) == device.device_id:
                return  # 已存在，不重复添加
        
        # 创建列表项
        item = QListWidgetItem()
        item.setText(f"{device.device_name} ({device.device_id})")
        item.setData(100, device.device_id)  # 存储设备ID
        
        # 添加到列表
        self.deviceList.addItem(item)
    
    def removeDeviceFromList(self, device):
        """从列表中移除设备"""
        for i in range(self.deviceList.count()):
            if self.deviceList.item(i).data(100) == device.device_id:
                self.deviceList.takeItem(i)
                break
    
    def onDeviceFound(self, device):
        """设备发现回调"""
        self.addDeviceToList(device)
        
        # 更新状态消息
        devices_count = self.deviceList.count()
        self.searchStatusLabel.setText(f"找到 {devices_count} 个设备")
    
    def onDeviceLost(self, device):
        """设备丢失回调"""
        self.removeDeviceFromList(device)
        
        # 更新状态消息
        devices_count = self.deviceList.count()
        self.searchStatusLabel.setText(f"找到 {devices_count} 个设备")
    
    def simulateDeviceDiscovery(self):
        """模拟发现设备（仅用于演示）"""
        # ... existing code ...

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
            box-shadow: 0px 3px 10px rgba(0, 0, 0, 0.2);
        """)
        
        # 添加到主布局
        layout.addWidget(contentWidget)
    
    def browseSavePath(self):
        """选择保存路径"""
        directory = QFileDialog.getExistingDirectory(self, "选择保存目录")
        if directory:
            self.savePathEdit.setText(directory)
            return directory

class MainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self):
        super().__init__()
        # 创建应用控制器
        self.app_controller = None
        self.initUI()
    
    def initUI(self):
        self.setWindowTitle("SendNow")  # 修改窗口标题
        self.setMinimumSize(900, 600)  # 稍微增大窗口最小尺寸
        
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
        mainLayout.setContentsMargins(0, 0, 0, 0)  # 移除边距，消除间隙
        mainLayout.setSpacing(0)  # 移除组件之间的间隙
        centralWidget = QWidget()
        centralWidget.setLayout(mainLayout)
        self.setCentralWidget(centralWidget)
        
        # 创建左侧导航栏
        navBar = QFrame()
        navBar.setStyleSheet(f"background-color: {DARK_BG};")
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
            padding: 18px 0;
            background-color: {QColor(DARK_BG).darker(150).name()};
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

    def setAppController(self, controller):
        """设置应用控制器"""
        self.app_controller = controller
        
        # 将控制器连接到面板
        self.sendPanel.setAppController(controller)
        
        # 启动网络服务
        if self.app_controller:
            self.app_controller.start()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_()) 