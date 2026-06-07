"""主窗口模块 - 菜单栏、工具栏、状态栏、中央切换"""

import os
import sys
# 确保父目录在 Python 路径中，以便可以导入 database, parsers, utils 等模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt5.QtWidgets import (
    QMainWindow, QStackedWidget, QMenuBar, QMenu, QAction,
    QToolBar, QStatusBar, QMessageBox, QFileDialog, QApplication,
    QLabel, QLineEdit, QComboBox, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QSplitter
)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QIcon, QFont, QKeySequence

from database import init_db, get_all_books, get_book_count, get_book_by_id
from .library_widget import LibraryWidget
from .reader_widget import ReaderWidget
from .import_dialog import ImportDialog
from .category_sidebar import CategorySidebar


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("📚 BookReader - 图书管理与阅读器")
        self.resize(1200, 800)
        self.setMinimumSize(900, 600)

        # 初始化数据库
        init_db()

        # 设置窗口样式
        self._setup_style()

        # 创建分类侧边栏
        self.category_sidebar = CategorySidebar()

        # 创建中央 stacked widget
        self.stack = QStackedWidget()

        # 创建各页面
        self.library_widget = LibraryWidget()
        self.reader_widget = ReaderWidget()

        self.stack.addWidget(self.library_widget)  # index 0
        self.stack.addWidget(self.reader_widget)   # index 1

        # 使用 QSplitter 组合侧边栏和主内容区
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(self.category_sidebar)
        self.splitter.addWidget(self.stack)
        self.splitter.setStretchFactor(0, 0)  # 侧边栏不拉伸
        self.splitter.setStretchFactor(1, 1)  # 主内容区拉伸
        self.splitter.setSizes([200, 1000])    # 默认宽度
        self.setCentralWidget(self.splitter)

        # 创建菜单栏
        self._setup_menu()

        # 创建工具栏
        self._setup_toolbar()

        # 创建状态栏
        self._setup_statusbar()

        # 连接信号
        self._connect_signals()

        # 初始加载
        self._refresh_status_bar()

        # 支持拖拽导入
        self.setAcceptDrops(True)

    def _setup_style(self):
        """设置全局样式"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f6fa;
            }
            QToolBar {
                background-color: #ffffff;
                border-bottom: 1px solid #dcdde1;
                padding: 6px;
                spacing: 8px;
            }
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #2471a3;
            }
            QLineEdit {
                border: 1px solid #dcdde1;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 13px;
                background-color: white;
            }
            QLineEdit:focus {
                border-color: #3498db;
            }
            QComboBox {
                border: 1px solid #dcdde1;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 13px;
                background-color: white;
            }
            QStatusBar {
                background-color: #ffffff;
                border-top: 1px solid #dcdde1;
                color: #636e72;
                font-size: 12px;
            }
            QMenuBar {
                background-color: #ffffff;
                border-bottom: 1px solid #dcdde1;
                padding: 2px;
            }
            QMenuBar::item:selected {
                background-color: #3498db;
                color: white;
                border-radius: 3px;
            }
        """)

    def _setup_menu(self):
        """创建菜单栏"""
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu("文件(&F)")
        import_action = QAction("导入图书(&I)...", self)
        import_action.setShortcut(QKeySequence("Ctrl+I"))
        import_action.triggered.connect(self._on_import)
        file_menu.addAction(import_action)

        import_folder_action = QAction("导入文件夹(&D)...", self)
        import_folder_action.setShortcut(QKeySequence("Ctrl+Shift+I"))
        import_folder_action.triggered.connect(self._on_import_folder)
        file_menu.addAction(import_folder_action)

        file_menu.addSeparator()
        exit_action = QAction("退出(&X)", self)
        exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # 视图菜单
        view_menu = menubar.addMenu("视图(&V)")
        self.grid_action = QAction("网格视图", self)
        self.grid_action.triggered.connect(lambda: self.library_widget.set_view_mode('grid'))
        self.grid_action.setCheckable(True)
        self.grid_action.setChecked(True)
        view_menu.addAction(self.grid_action)

        self.list_action = QAction("列表视图", self)
        self.list_action.triggered.connect(lambda: self.library_widget.set_view_mode('list'))
        self.list_action.setCheckable(True)
        view_menu.addAction(self.list_action)

        # 帮助菜单
        help_menu = menubar.addMenu("帮助(&H)")
        about_action = QAction("关于(&A)", self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)

    def _setup_toolbar(self):
        """创建工具栏"""
        toolbar = self.addToolBar("主工具栏")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(20, 20))

        # 导入按钮
        import_btn = QPushButton("📥 导入图书")
        import_btn.clicked.connect(self._on_import)
        toolbar.addWidget(import_btn)

        toolbar.addSeparator()

        # 搜索框
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("🔍  搜索书名或作者...")
        self.search_box.setMaximumWidth(300)
        self.search_box.textChanged.connect(self._on_search)
        toolbar.addWidget(self.search_box)

        toolbar.addSeparator()

        # 排序选择
        sort_label = QLabel("排序:")
        toolbar.addWidget(sort_label)

        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["最近添加", "书名 A-Z", "作者 A-Z", "最近阅读"])
        self.sort_combo.currentIndexChanged.connect(self._on_sort_changed)
        toolbar.addWidget(self.sort_combo)

        # 刷新按钮
        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.clicked.connect(self._refresh_library)
        toolbar.addWidget(refresh_btn)

    def _setup_statusbar(self):
        """创建状态栏"""
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.status_label = QLabel("就绪")
        self.statusbar.addWidget(self.status_label)

    def _connect_signals(self):
        """连接信号"""
        # 书架发出阅读请求信号
        self.library_widget.read_requested.connect(self._on_open_reader)
        # 阅读器发出返回信号
        self.reader_widget.back_requested.connect(self._on_back_to_library)
        # 分类侧边栏筛选
        self.category_sidebar.category_selected.connect(self._on_category_selected)

    def _on_import(self):
        """处理导入图书"""
        dialog = ImportDialog(self)
        if dialog.exec_():
            self._refresh_library()
            self._refresh_status_bar()

    def _on_import_folder(self):
        """处理导入文件夹"""
        folder = QFileDialog.getExistingDirectory(self, "选择包含图书的文件夹")
        if folder:
            dialog = ImportDialog(self, import_path=folder)
            if dialog.exec_():
                self._refresh_library()
                self._refresh_status_bar()

    def _on_search(self, text):
        """处理搜索"""
        self.library_widget.filter_books(text)

    def _on_category_selected(self, category_id):
        """处理分类选择变更"""
        # category_id: None=全部, int=指定分类ID
        self.library_widget.filter_by_category(category_id)

    def _on_sort_changed(self, index):
        """处理排序变更"""
        sort_map = {
            0: 'date_added',
            1: 'title',
            2: 'author',
            3: 'last_read',
        }
        sort_key = sort_map.get(index, 'date_added')
        self.library_widget.sort_books(sort_key)

    def _on_open_reader(self, book_id):
        """打开阅读器"""
        book = get_book_by_id(book_id)
        if book:
            self.reader_widget.load_book(book)
            self.stack.setCurrentIndex(1)
            self.search_box.setVisible(False)
            self.sort_combo.setVisible(False)
            self.category_sidebar.setVisible(False)

    def _on_back_to_library(self):
        """返回书架"""
        self.stack.setCurrentIndex(0)
        self.search_box.setVisible(True)
        self.sort_combo.setVisible(True)
        self.category_sidebar.setVisible(True)
        self._refresh_library()
        self._refresh_status_bar()
        self.category_sidebar.load_categories()

    def _refresh_library(self):
        """刷新书架"""
        self.library_widget.load_books()
        self.category_sidebar.load_categories()

    def _refresh_status_bar(self):
        """刷新状态栏"""
        count = get_book_count()
        self.status_label.setText(f"📚 共 {count} 本图书")

    def _on_about(self):
        """关于对话框"""
        QMessageBox.about(
            self,
            "关于 BookReader",
            "<h3>📚 BookReader v1.0</h3>"
            "<p>一款简洁、实用的图书管理与阅读器</p>"
            "<p>支持格式：PDF · EPUB · MOBI · TXT · AZW3 · FB2</p>"
            "<hr>"
            "<p>技术栈：Python + PyQt5</p>"
        )

    def dragEnterEvent(self, event):
        """处理拖拽进入事件"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        """处理拖拽放下事件"""
        files = []
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if os.path.isfile(path):
                files.append(path)
            elif os.path.isdir(path):
                for root, _, filenames in os.walk(path):
                    for fname in filenames:
                        files.append(os.path.join(root, fname))

        if files:
            from utils import is_supported
            book_files = [f for f in files if is_supported(f)]
            if book_files:
                dialog = ImportDialog(self, files=book_files)
                if dialog.exec_():
                    self._refresh_library()
                    self._refresh_status_bar()
            else:
                QMessageBox.information(self, "提示", "未找到支持的图书文件。")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
