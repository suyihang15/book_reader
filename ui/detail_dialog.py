"""图书详情编辑对话框"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTextEdit, QPushButton, QFormLayout, QFrame, QMessageBox,
    QFileDialog, QDialogButtonBox
)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QPixmap, QFont, QIcon
from io import BytesIO
from PIL import Image

from database import get_book_by_id, update_book, delete_book, get_categories
from utils import generate_default_cover


class DetailDialog(QDialog):
    """图书详情/编辑对话框"""

    def __init__(self, book_id, parent=None):
        super().__init__(parent)
        self.book_id = book_id
        self.book = get_book_by_id(book_id)
        self.new_cover_path = None

        if not self.book:
            QMessageBox.warning(self, "错误", "图书不存在")
            self.reject()
            return

        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        self.setWindowTitle(f"编辑详情 - {self.book.get('title', '未命名')}")
        self.setMinimumSize(550, 600)
        self.resize(600, 650)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # === 顶部：封面预览 ===
        cover_frame = QFrame()
        cover_frame.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border-radius: 8px;
                padding: 15px;
            }
        """)
        cover_layout = QHBoxLayout(cover_frame)

        self.cover_label = QLabel()
        self.cover_label.setFixedSize(150, 200)
        self.cover_label.setAlignment(Qt.AlignCenter)
        self.cover_label.setStyleSheet("""
            QLabel {
                border: 2px solid #dcdde1;
                border-radius: 6px;
                background-color: white;
            }
        """)
        cover_layout.addWidget(self.cover_label)

        cover_info_layout = QVBoxLayout()
        cover_info_layout.addStretch()
        change_cover_btn = QPushButton("🖼️ 更换封面")
        change_cover_btn.clicked.connect(self._change_cover)
        cover_info_layout.addWidget(change_cover_btn)

        reset_cover_btn = QPushButton("🔄 恢复默认封面")
        reset_cover_btn.clicked.connect(self._reset_cover)
        cover_info_layout.addWidget(reset_cover_btn)

        cover_info_layout.addStretch()
        cover_layout.addLayout(cover_info_layout)
        cover_layout.addStretch()

        layout.addWidget(cover_frame)

        # === 表单区域 ===
        form_frame = QFrame()
        form_frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 15px;
            }
        """)
        form_layout = QFormLayout(form_frame)
        form_layout.setSpacing(10)

        # 标题
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("输入书名...")
        self.title_edit.setMinimumHeight(32)
        form_layout.addRow("书名:", self.title_edit)

        # 作者
        self.author_edit = QLineEdit()
        self.author_edit.setPlaceholderText("输入作者...")
        self.author_edit.setMinimumHeight(32)
        form_layout.addRow("作者:", self.author_edit)

        # 出版社
        self.publisher_edit = QLineEdit()
        self.publisher_edit.setPlaceholderText("输入出版社...")
        self.publisher_edit.setMinimumHeight(32)
        form_layout.addRow("出版社:", self.publisher_edit)

        # ISBN
        self.isbn_edit = QLineEdit()
        self.isbn_edit.setPlaceholderText("输入 ISBN...")
        self.isbn_edit.setMinimumHeight(32)
        form_layout.addRow("ISBN:", self.isbn_edit)

        # 描述
        self.desc_edit = QTextEdit()
        self.desc_edit.setPlaceholderText("输入图书描述...")
        self.desc_edit.setMaximumHeight(100)
        form_layout.addRow("描述:", self.desc_edit)

        # 标签
        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText("用逗号分隔，如: 小说, 经典, 文学")
        self.tags_edit.setMinimumHeight(32)
        form_layout.addRow("标签:", self.tags_edit)

        # 分类
        self.category_combo = QComboBox()
        self.category_combo.setMinimumHeight(32)
        self.category_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #dcdde1;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 13px;
                background-color: white;
            }
            QComboBox:focus {
                border-color: #3498db;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
            QComboBox QAbstractItemView {
                background-color: white;
                selection-background-color: #3498db;
                selection-color: white;
            }
        """)
        form_layout.addRow("分类:", self.category_combo)

        layout.addWidget(form_frame)

        # === 信息显示 ===
        info_frame = QFrame()
        info_frame.setStyleSheet("color: #636e72; font-size: 11px;")
        info_layout = QHBoxLayout(info_frame)

        fmt = self.book.get('format', '未知')
        size_str = '未知'
        file_path = self.book.get('file_path', '')
        if file_path and os.path.exists(file_path):
            size = os.path.getsize(file_path)
            if size > 1024 * 1024:
                size_str = f"{size / (1024 * 1024):.1f} MB"
            else:
                size_str = f"{size / 1024:.1f} KB"

        pages = self.book.get('page_count', 0)
        added = self.book.get('date_added', '')
        last_read = self.book.get('last_read', '')

        info_layout.addWidget(QLabel(f"格式: {fmt}"))
        info_layout.addWidget(QLabel(f"|"))
        info_layout.addWidget(QLabel(f"大小: {size_str}"))
        info_layout.addWidget(QLabel(f"|"))
        info_layout.addWidget(QLabel(f"页数: {pages}"))
        info_layout.addWidget(QLabel(f"|"))
        info_layout.addWidget(QLabel(f"添加时间: {added}"))
        info_layout.addStretch()

        layout.addWidget(info_frame)

        # === 按钮 ===
        button_layout = QHBoxLayout()

        delete_btn = QPushButton("🗑️ 删除此图书")
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        delete_btn.clicked.connect(self._on_delete)
        button_layout.addWidget(delete_btn)

        button_layout.addStretch()

        save_btn = QPushButton("💾 保存")
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                padding: 8px 24px;
                border-radius: 4px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #219a52;
            }
        """)
        save_btn.clicked.connect(self._on_save)
        button_layout.addWidget(save_btn)

        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

    def _load_data(self):
        """加载图书数据到表单"""
        self.title_edit.setText(self.book.get('title', ''))
        self.author_edit.setText(self.book.get('author', ''))
        self.publisher_edit.setText(self.book.get('publisher', ''))
        self.isbn_edit.setText(self.book.get('isbn', ''))
        self.desc_edit.setText(self.book.get('description', ''))

        tags = self.book.get('tags', [])
        if isinstance(tags, list):
            self.tags_edit.setText(', '.join(tags))
        elif isinstance(tags, str):
            self.tags_edit.setText(tags)

        # 加载分类列表
        self.category_combo.addItem('-- 未分类 --', None)
        categories = get_categories()
        for cat in categories:
            self.category_combo.addItem(cat['name'], cat['id'])

        # 选中当前分类
        current_cat_id = self.book.get('category_id')
        for i in range(self.category_combo.count()):
            if self.category_combo.itemData(i) == current_cat_id:
                self.category_combo.setCurrentIndex(i)
                break

        self._load_cover()

    def _load_cover(self):
        """加载封面预览"""
        cover_path = self.book.get('cover_path', '')
        pixmap = None

        if cover_path and os.path.exists(cover_path):
            try:
                pixmap = QPixmap(cover_path)
            except Exception:
                pass

        if pixmap is None or pixmap.isNull():
            img = generate_default_cover(
                self.book.get('title', ''),
                self.book.get('author', ''),
                size=(280, 370)
            )
            bio = BytesIO()
            img.save(bio, format='PNG')
            pixmap = QPixmap()
            pixmap.loadFromData(bio.getvalue())

        scaled = pixmap.scaled(150, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.cover_label.setPixmap(scaled)

    def _change_cover(self):
        """更换封面"""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "选择封面图片",
            "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.gif);;所有文件 (*.*)"
        )
        if filepath:
            try:
                # 复制到 covers 目录
                import shutil
                library_dir = os.path.dirname(self.book.get('file_path', ''))
                covers_dir = os.path.join(library_dir, '.covers')
                if not os.path.exists(covers_dir):
                    # fallback
                    covers_dir = os.path.join(
                        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        'library', '.covers'
                    )
                os.makedirs(covers_dir, exist_ok=True)

                # 使用原始文件名
                cover_filename = f"custom_cover_{self.book_id}_{os.path.basename(filepath)}"
                dest_path = os.path.join(covers_dir, cover_filename)
                shutil.copy2(filepath, dest_path)
                self.new_cover_path = dest_path

                # 更新预览
                pixmap = QPixmap(dest_path)
                scaled = pixmap.scaled(150, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.cover_label.setPixmap(scaled)

            except Exception as e:
                QMessageBox.warning(self, "错误", f"设置封面失败: {e}")

    def _reset_cover(self):
        """恢复默认封面"""
        self.new_cover_path = ''  # 置空表示使用默认
        img = generate_default_cover(
            self.book.get('title', ''),
            self.book.get('author', ''),
            size=(280, 370)
        )
        bio = BytesIO()
        img.save(bio, format='PNG')
        pixmap = QPixmap()
        pixmap.loadFromData(bio.getvalue())
        scaled = pixmap.scaled(150, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.cover_label.setPixmap(scaled)

    def _on_save(self):
        """保存修改"""
        tags_text = self.tags_edit.text().strip()
        tags = [t.strip() for t in tags_text.split(',') if t.strip()] if tags_text else []

        updates = {
            'title': self.title_edit.text().strip(),
            'author': self.author_edit.text().strip(),
            'publisher': self.publisher_edit.text().strip(),
            'isbn': self.isbn_edit.text().strip(),
            'description': self.desc_edit.toPlainText().strip(),
            'tags': tags,
            'category_id': self.category_combo.currentData(),
        }

        # 处理封面
        if self.new_cover_path is not None:
            updates['cover_path'] = self.new_cover_path

        update_book(self.book_id, **updates)
        self.accept()

    def _on_delete(self):
        """删除图书"""
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除《{self.book.get('title', '未知')}》吗？\n\n"
            "此操作将删除图书记录、封面缓存及 library 目录中的图书文件。\n"
            "（不会影响原始文件）",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            # 删除封面文件
            cover_path = self.book.get('cover_path', '')
            if cover_path and os.path.exists(cover_path):
                try:
                    os.remove(cover_path)
                except Exception:
                    pass
            # 删除导入的图书文件
            file_path = self.book.get('file_path', '')
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception:
                    pass
            delete_book(self.book_id)
            self.accept()
