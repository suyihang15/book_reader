"""分类管理对话框 - 添加、重命名、删除、排序分类"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QInputDialog, QMessageBox, QFrame
)
from PyQt5.QtCore import Qt, QSize

from database import get_categories, add_category, update_category, delete_category


class CategoryDialog(QDialog):
    """分类管理对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📂 管理分类")
        self.setMinimumSize(400, 450)
        self.resize(450, 500)
        self.setModal(True)
        self._setup_ui()
        self._load_categories()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 标题
        title = QLabel("管理图书分类")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(title)

        # 说明
        hint = QLabel("拖拽排序功能暂未实现，可通过删除重建调整顺序。")
        hint.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        layout.addWidget(hint)

        # 分类列表
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                border: 1px solid #dcdde1;
                border-radius: 6px;
                font-size: 13px;
                background-color: #f8f9fa;
            }
            QListWidget::item {
                padding: 10px 16px;
                border-bottom: 1px solid #eee;
                background-color: white;
            }
            QListWidget::item:hover {
                background-color: #f0f8ff;
            }
            QListWidget::item:selected {
                background-color: #e8f4fd;
                color: #2c3e50;
            }
        """)
        layout.addWidget(self.list_widget)

        # 按钮区
        btn_frame = QFrame()
        btn_layout = QHBoxLayout(btn_frame)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(10)

        add_btn = QPushButton("➕ 添加分类")
        add_btn.setStyleSheet(self._btn_style('#27ae60', '#219a52'))
        add_btn.clicked.connect(self._add_category)
        btn_layout.addWidget(add_btn)

        rename_btn = QPushButton("✏️ 重命名")
        rename_btn.setStyleSheet(self._btn_style('#3498db', '#2980b9'))
        rename_btn.clicked.connect(self._rename_category)
        btn_layout.addWidget(rename_btn)

        delete_btn = QPushButton("🗑️ 删除")
        delete_btn.setStyleSheet(self._btn_style('#e74c3c', '#c0392b'))
        delete_btn.clicked.connect(self._delete_category)
        btn_layout.addWidget(delete_btn)

        layout.addWidget(btn_frame)

        # 底部按钮
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()

        close_btn = QPushButton("关闭")
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border: none;
                padding: 8px 24px;
                border-radius: 4px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
        """)
        close_btn.clicked.connect(self.accept)
        bottom_layout.addWidget(close_btn)

        layout.addLayout(bottom_layout)

    def _btn_style(self, bg, hover_bg):
        return f"""
            QPushButton {{
                background-color: {bg};
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {hover_bg};
            }}
        """

    def _load_categories(self):
        """加载分类列表"""
        self.list_widget.clear()
        categories = get_categories()
        for cat in categories:
            text = f"  {cat['name']}  ({cat['book_count']} 本)"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, cat['id'])
            item.setSizeHint(QSize(0, 42))
            self.list_widget.addItem(item)

    def _add_category(self):
        """添加新分类"""
        name, ok = QInputDialog.getText(
            self, "添加分类", "请输入分类名称:"
        )
        if ok and name.strip():
            cat_id = add_category(name.strip())
            if cat_id is None:
                QMessageBox.warning(self, "错误", f"分类「{name.strip()}」已存在。")
            else:
                self._load_categories()

    def _rename_category(self):
        """重命名选中分类"""
        item = self.list_widget.currentItem()
        if item is None:
            QMessageBox.information(self, "提示", "请先选择要重命名的分类。")
            return

        cat_id = item.data(Qt.UserRole)
        old_name = item.text().split('(')[0].strip()

        new_name, ok = QInputDialog.getText(
            self, "重命名分类", "请输入新名称:", text=old_name
        )
        if ok and new_name.strip() and new_name.strip() != old_name:
            update_category(cat_id, name=new_name.strip())
            self._load_categories()

    def _delete_category(self):
        """删除选中分类"""
        item = self.list_widget.currentItem()
        if item is None:
            QMessageBox.information(self, "提示", "请先选择要删除的分类。")
            return

        cat_id = item.data(Qt.UserRole)
        name = item.text().split('(')[0].strip()

        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除分类「{name}」吗？\n\n"
            "该分类下的图书将变为「未分类」，不会删除图书。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            delete_category(cat_id)
            self._load_categories()
