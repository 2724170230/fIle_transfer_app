# SendNow - 局域网文件传输工具 (Demo)
import sys
from localsend_ui_design import MainWindow
from PyQt5.QtWidgets import QApplication

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_()) 