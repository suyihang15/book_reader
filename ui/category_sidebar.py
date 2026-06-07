"""分类侧边栏组件 - 展示分类列表、筛选图书、管理分类"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QPushButton, QMenu, QAction, QInputDialog, QMessageBox,
    QSizePolicy
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QFont

from database import (
    get_categories, add_category, update_category, delete_category
)


class CategorySidebar(QWidget):
    """分类侧边栏"""
    category_selected = pyqtSignal(object)  # 发送 category_id (int) 或 None (全部)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(160)
        self.setMaximumWidth(260)
        self.setStyleSheet("""
            CategorySidebar {
                background-color: #ffffff;
                border-right: 1px solid #dcdde1;
            }
        """)
        self._setup_ui()
        self.load_categories()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 标题
        title_label = QLabel("   📂 图书分类")
        title_label.setStyleSheet("""
            QLabel {
                background-color: #f8f9fa;
                color: #2c3e50;
                font-size: 14px;
                font-weight: bold;
                padding: 12px 8px;
                border-bottom: 1px solid #dcdde1;
            }
        """)
        layout.addWidget(title_label)

        # 分类列表
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                border: none;
                background-color: #ffffff;
                font-size: 13px;
            }
            QListWidget::item {
                padding: 8px 16px;
                border: none;
                color: #2c3e50;
            }
            QListWidget::item:hover {
                background-color: #f0f8ff;
                color: #3498db;
            }
            QListWidget::item:selected {
                background-color: #e8f4fd;
                color: #2980b9;
                font-weight: bold;
                border-left: 3px solid #3498db;
            }
        """)
        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._on_context_menu)
        self.list_widget.currentRowChanged.connect(self._on_selection_changed)
        layout.addWidget(self.list_widget)

        # 底部按钮
        bottom_widget = QWidget()
        bottom_widget.setStyleSheet("""
            QWidget {
                background-color: #f8f9fa;
                border-top: 1px solid #dcdde1;
            }
        """)
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(10, 8, 10, 8)
        bottom_layout.setSpacing(6)

        manage_btn = QPushButton("⚙ 管理分类")
        manage_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 6px 14px;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        manage_btn.clicked.connect(self._on_manage_categories)
        bottom_layout.addWidget(manage_btn)

        layout.addWidget(bottom_widget)

    def load_categories(self):
        """加载分类列表"""
        current_id = self._get_selected_category_id()

        self.list_widget.blockSignals(True)
        self.list_widget.clear()

        # "全部" 项
        all_item = QListWidgetItem("📚 全部")
        all_item.setData(Qt.UserRole, None)  # None 表示全部
        all_item.setSizeHint(QSize(0, 38))
        self.list_widget.addItem(all_item)

        # 分隔线
        sep_item = QListWidgetItem("")
        sep_item.setFlags(Qt.NoItemFlags)
        sep_item.setSizeHint(QSize(0, 4))
        self.list_widget.addItem(sep_item)

        # 各分类
        categories = get_categories()
        for cat in categories:
            text = f"  {cat['name']}  ({cat['book_count']})"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, cat['id'])
            item.setSizeHint(QSize(0, 36))
            self.list_widget.addItem(item)

        # 未分类
        uncat_count = self._get_uncategorized_count()
        uncat_item = QListWidgetItem(f"  📭 未分类  ({uncat_count})")
        uncat_item.setData(Qt.UserRole, 'uncategorized')
        uncat_item.setSizeHint(QSize(0, 36))
        self.list_widget.addItem(uncat_item)

        # 恢复选中
        self._restore_selection(current_id)
        self.list_widget.blockSignals(False)

    def _get_selected_category_id(self):
        """获取当前选中的 category_id"""
        item = self.list_widget.currentItem()
        if item:
            return item.data(Qt.UserRole)
        return None

    def _restore_selection(self, category_id):
        """恢复之前的选中状态"""
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item and item.data(Qt.UserRole) == category_id:
                self.list_widget.setCurrentRow(i)
                return
        # 默认选中"全部"
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

    def _get_uncategorized_count(self):
        """获取未分类图书数量"""
        from database import get_connection
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM books WHERE category_id IS NULL')
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def _on_selection_changed(self, row):
        """分类选择变更"""
        item = self.list_widget.item(row)
        if item is None:
            return

        data = item.data(Qt.UserRole)
        if data == 'uncategorized':
            self.category_selected.emit(None)  # None 表示查询 category_id IS NULL
        else:
            self.category_selected.emit(data)  # int category_id 或 None (全部)

    def _on_context_menu(self, pos):
        """分类右键菜单"""
        item = self.list_widget.itemAt(pos)
        if item is None:
            return

        data = item.data(Qt.UserRole)
        # "全部"、分隔线、"未分类"不显示右键菜单
        if data is None or data == 'uncategorized':
            return
        if not isinstance(data, int):
            return

        menu = QMenu(self)
        rename_action = menu.addAction("✏️ 重命名")
        menu.addSeparator()
        delete_action = menu.addAction("🗑️ 删除分类")

        action = menu.exec_(self.list_widget.mapToGlobal(pos))
        if action == rename_action:
            self._rename_category(data)
        elif action == delete_action:
            self._delete_category(data)

    def _rename_category(self, category_id):
        """重命名分类"""
        # 获取当前名称
        from database import get_connection
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT name FROM categories WHERE id = ?', (category_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return

        old_name = row[0]
        new_name, ok = QInputDialog.getText(
            self, "重命名分类", "请输入新名称:", text=old_name
        )
        if ok and new_name.strip() and new_name.strip() != old_name:
            update_category(category_id, name=new_name.strip())
            self.load_categories()

    def _delete_category(self, category_id):
        """删除分类"""
        from database import get_connection
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT name FROM categories WHERE id = ?', (category_id,))
        row = cursor.fetchone()
        conn.close()

        name = row[0] if row else '未知'

        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除分类「{name}」吗？\n\n"
            "该分类下的图书将变为「未分类」，不会删除图书。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            delete_category(category_id)
            self.load_categories()
            self.category_selected.emit('all')  # 刷新显示

    def _on_manage_categories(self):
        """打开分类管理对话框"""
        from .category_dialog import CategoryDialog
        dialog = CategoryDialog(self)
        if dialog.exec_():
            self.load_categories()
            self.category_selected.emit('all')
