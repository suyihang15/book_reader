"""书架视图模块 - 图书网格/列表展示、搜索过滤、右键菜单"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import shutil
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QGridLayout,
    QLabel, QPushButton, QMenu, QAction, QMessageBox, QFrame,
    QLineEdit, QComboBox, QSizePolicy, QListWidget, QListWidgetItem,
    QAbstractItemView
)
from PyQt5.QtCore import Qt, QSize, pyqtSignal, QEvent
from PyQt5.QtGui import QFont, QPixmap, QImage, QIcon, QColor, QPalette

from database import get_all_books, search_books, delete_book, get_book_count, get_categories, get_books_by_category
from utils import generate_default_cover, scale_image
from .detail_dialog import DetailDialog
from PIL import Image
from io import BytesIO


class BookCard(QFrame):
    """图书卡片组件"""
    clicked = pyqtSignal(int)
    detail_requested = pyqtSignal(int)
    delete_requested = pyqtSignal(int)

    def __init__(self, book_data, parent=None):
        super().__init__(parent)
        self.book_id = book_data['id']
        self.book_data = book_data
        self.setFixedSize(160, 260)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(f"{book_data['title']}\n{book_data['author']}\n格式: {book_data['format']}")
        self._setup_ui()
        self._apply_style()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # 封面图片
        self.cover_label = QLabel()
        self.cover_label.setFixedSize(140, 185)
        self.cover_label.setAlignment(Qt.AlignCenter)
        self.cover_label.setScaledContents(False)
        self._load_cover()
        layout.addWidget(self.cover_label, alignment=Qt.AlignCenter)

        # 书名
        title = self.book_data.get('title', '未命名')
        if len(title) > 12:
            title = title[:11] + '…'
        self.title_label = QLabel(title)
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setWordWrap(True)
        self.title_label.setMaximumHeight(36)
        font = QFont()
        font.setPointSize(10)
        font.setBold(True)
        self.title_label.setFont(font)
        layout.addWidget(self.title_label)

        # 作者
        author = self.book_data.get('author', '未知作者')
        if len(author) > 15:
            author = author[:14] + '…'
        self.author_label = QLabel(author)
        self.author_label.setAlignment(Qt.AlignCenter)
        self.author_label.setStyleSheet("color: #636e72; font-size: 11px;")
        layout.addWidget(self.author_label)

        # 格式标签
        fmt = self.book_data.get('format', '')
        self.format_label = QLabel(fmt)
        self.format_label.setAlignment(Qt.AlignCenter)
        self.format_label.setStyleSheet("""
            background-color: #dfe6e9;
            color: #636e72;
            border-radius: 3px;
            padding: 2px 8px;
            font-size: 10px;
            font-weight: bold;
        """)
        self.format_label.setFixedWidth(50)
        layout.addWidget(self.format_label, alignment=Qt.AlignCenter)

        # 分类标签
        category_name = self._get_category_name()
        self.category_label = QLabel(category_name)
        self.category_label.setAlignment(Qt.AlignCenter)
        self.category_label.setStyleSheet("""
            background-color: #e8f4fd;
            color: #2980b9;
            border-radius: 3px;
            padding: 2px 8px;
            font-size: 10px;
        """)
        self.category_label.setFixedWidth(70)
        layout.addWidget(self.category_label, alignment=Qt.AlignCenter)

    def _get_category_name(self):
        """获取分类名称"""
        cat_id = self.book_data.get('category_id')
        if cat_id:
            categories = get_categories()
            for cat in categories:
                if cat['id'] == cat_id:
                    return cat['name']
        return '未分类'

    def _load_cover(self):
        """加载封面图片"""
        cover_path = self.book_data.get('cover_path', '')
        pixmap = None

        if cover_path and os.path.exists(cover_path):
            try:
                pixmap = QPixmap(cover_path)
            except Exception:
                pass

        if pixmap is None or pixmap.isNull():
            # 生成默认封面
            img = generate_default_cover(
                self.book_data.get('title', ''),
                self.book_data.get('author', ''),
                size=(280, 370)
            )
            bio = BytesIO()
            img.save(bio, format='PNG')
            pixmap = QPixmap()
            pixmap.loadFromData(bio.getvalue())

        scaled = pixmap.scaled(
            140, 185,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        self.cover_label.setPixmap(scaled)

    def _apply_style(self):
        self.setStyleSheet("""
            BookCard {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
            }
            BookCard:hover {
                border-color: #3498db;
                background-color: #f0f8ff;
            }
        """)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.book_id)
        elif event.button() == Qt.RightButton:
            self._show_context_menu(event.globalPos())

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        read_action = menu.addAction("📖 阅读")
        detail_action = menu.addAction("✏️ 编辑详情")
        menu.addSeparator()
        delete_action = menu.addAction("🗑️ 删除")

        action = menu.exec_(pos)
        if action == read_action:
            self.clicked.emit(self.book_id)
        elif action == detail_action:
            self.detail_requested.emit(self.book_id)
        elif action == delete_action:
            self.delete_requested.emit(self.book_id)

    def enterEvent(self, event):
        """鼠标进入时升高卡片"""
        self.setFixedSize(162, 262)

    def leaveEvent(self, event):
        """鼠标离开时恢复"""
        self.setFixedSize(160, 260)


class LibraryWidget(QWidget):
    """书架视图"""
    read_requested = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.all_books = []
        self.filtered_books = []
        self.current_sort = 'date_added'
        self.view_mode = 'grid'  # grid 或 list
        self.current_category_id = None  # None=全部, 'all'=所有分类, int=指定分类
        self.current_filter_query = ''    # 当前搜索关键词

        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 滚动区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #f5f6fa;
            }
        """)

        # 网格容器
        self.grid_container = QWidget()
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setContentsMargins(20, 20, 20, 20)
        self.grid_layout.setSpacing(16)
        self.grid_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        self.scroll_area.setWidget(self.grid_container)

        # 列表视图
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                border: none;
                background-color: #f5f6fa;
                font-size: 13px;
            }
            QListWidget::item {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                padding: 8px;
                margin: 3px 10px;
            }
            QListWidget::item:hover {
                border-color: #3498db;
                background-color: #f0f8ff;
            }
        """)
        self.list_widget.itemDoubleClicked.connect(self._on_list_item_clicked)
        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._on_list_context_menu)
        self.list_widget.hide()

        main_layout.addWidget(self.scroll_area)
        main_layout.addWidget(self.list_widget)

    def load_books(self):
        """加载所有图书"""
        self.all_books = get_all_books(order_by=self.current_sort)
        self._apply_filters()

    def filter_by_category(self, category_id):
        """按分类筛选图书

        Args:
            category_id: None=全部显示, 'all'=所有分类(刷新用), int=指定分类ID
        """
        if category_id == 'all':
            self.current_category_id = None
            self.all_books = get_all_books(order_by=self.current_sort)
        else:
            self.current_category_id = category_id
        self._apply_filters()

    def filter_books(self, query=''):
        """按关键词过滤图书"""
        self.current_filter_query = query.strip()
        self._apply_filters()

    def sort_books(self, sort_key):
        """排序图书"""
        self.current_sort = sort_key
        self.all_books = get_all_books(order_by=sort_key)
        self._apply_filters()

    def _apply_filters(self):
        """综合应用分类筛选 + 关键词搜索"""
        # 第一步：分类筛选
        if self.current_category_id is None:
            # 显示全部
            books = list(self.all_books)
        elif self.current_category_id == 'uncategorized':
            books = get_books_by_category(None, order_by=self.current_sort)
        else:
            books = get_books_by_category(self.current_category_id, order_by=self.current_sort)

        # 第二步：关键词搜索
        query = self.current_filter_query
        if query:
            books = [
                b for b in books
                if query.lower() in b.get('title', '').lower()
                or query.lower() in b.get('author', '').lower()
            ]

        self.filtered_books = books
        self._render_books()

    def set_view_mode(self, mode):
        """切换视图模式"""
        self.view_mode = mode
        self._render_books()

    def _render_books(self):
        """渲染图书列表"""
        # 清空现有内容
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.list_widget.clear()

        if self.view_mode == 'grid':
            self.scroll_area.show()
            self.list_widget.hide()
            self._render_grid()
        else:
            self.scroll_area.hide()
            self.list_widget.show()
            self._render_list()

    def _render_grid(self):
        """渲染网格视图"""
        books = self.filtered_books
        if not books:
            empty_label = QLabel("📭 图书架空空如也\n拖拽图书文件到窗口或点击「导入图书」开始")
            empty_label.setAlignment(Qt.AlignCenter)
            empty_label.setStyleSheet("color: #b2bec3; font-size: 18px; padding: 100px;")
            self.grid_layout.addWidget(empty_label, 0, 0)
            return

        # 计算列数
        container_width = self.scroll_area.viewport().width() if self.scroll_area.viewport() else 1000
        card_width = 180
        cols = max(1, container_width // card_width)

        for i, book in enumerate(books):
            card = BookCard(book)
            card.clicked.connect(self._on_book_clicked)
            card.detail_requested.connect(self._on_detail_requested)
            card.delete_requested.connect(self._on_delete_requested)

            row = i // cols
            col = i % cols
            self.grid_layout.addWidget(card, row, col)

    def _render_list(self):
        """渲染列表视图"""
        for book in self.filtered_books:
            title = book.get('title', '未命名')
            author = book.get('author', '未知')
            fmt = book.get('format', '')
            item_text = f"  {title}    — {author}    [{fmt}]"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, book['id'])
            item.setSizeHint(QSize(0, 45))

            # 尝试加载封面做图标
            cover_path = book.get('cover_path', '')
            if cover_path and os.path.exists(cover_path):
                icon = QIcon(cover_path)
                item.setIcon(icon)

            self.list_widget.addItem(item)

    def _on_book_clicked(self, book_id):
        """点击图书，进入阅读"""
        self.read_requested.emit(book_id)

    def _on_list_item_clicked(self, item):
        """列表项双击"""
        book_id = item.data(Qt.UserRole)
        if book_id:
            self.read_requested.emit(book_id)

    def _on_detail_requested(self, book_id):
        """编辑图书详情"""
        dialog = DetailDialog(book_id, self)
        if dialog.exec_():
            self.load_books()

    def _on_delete_requested(self, book_id):
        """删除图书"""
        from database import get_book_by_id
        book = get_book_by_id(book_id)
        title = book.get('title', '未知') if book else '未知'

        reply = QMessageBox.question(
            self,
            "确认删除",
            f'确定要删除《{title}》吗？\n\n此操作将删除图书记录、封面缓存及 library 目录中的图书文件。\n（不会影响原始文件）',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            # 删除封面缓存
            if book and book.get('cover_path'):
                try:
                    os.remove(book['cover_path'])
                except Exception:
                    pass
            # 删除导入的图书文件
            if book and book.get('file_path'):
                try:
                    os.remove(book['file_path'])
                except Exception:
                    pass
            delete_book(book_id)
            self.load_books()

    def _on_list_context_menu(self, pos):
        """列表视图右键菜单"""
        item = self.list_widget.itemAt(pos)
        if not item:
            return

        book_id = item.data(Qt.UserRole)
        if not book_id:
            return

        menu = QMenu(self)
        read_action = menu.addAction("📖 阅读")
        detail_action = menu.addAction("✏️ 编辑详情")
        menu.addSeparator()
        delete_action = menu.addAction("🗑️ 删除")

        action = menu.exec_(self.list_widget.mapToGlobal(pos))
        if action == read_action:
            self.read_requested.emit(book_id)
        elif action == detail_action:
            self._on_detail_requested(book_id)
        elif action == delete_action:
            self._on_delete_requested(book_id)
