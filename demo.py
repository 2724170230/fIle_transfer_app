"""
SendNow演示程序 (Demo Program)

这是SendNow应用程序的简化演示版本，用于快速启动和展示应用的基本功能。
该脚本仅导入主窗口并显示应用程序界面，不包含完整的应用程序逻辑。
主要用于演示和测试UI界面。
"""

# SendNow - 局域网文件传输工具 (Demo)
import sys
from sendnow_ui_design import MainWindow
from PyQt5.QtWidgets import QApplication

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_()) 