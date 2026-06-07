"""BookReader - 图书管理与阅读器 入口文件

使用方法:
    python main.py

依赖安装:
    pip install -r requirements.txt
"""

import sys
import os

# 确保当前目录在 Python 路径中
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

from ui.main_window import MainWindow


def main():
    # 启用高DPI支持
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("BookReader")
    app.setApplicationDisplayName("📚 BookReader - 图书管理与阅读器")
    app.setOrganizationName("BookReader")

    # 使用 Fusion 风格，在所有平台上外观一致
    app.setStyle('Fusion')

    # 创建并显示主窗口
    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
