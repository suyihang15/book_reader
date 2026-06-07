"""导入对话框模块 - 文件/文件夹导入、进度显示、重复检测"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import shutil
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QProgressBar, QTextEdit, QFileDialog, QMessageBox, QListWidget,
    QListWidgetItem, QDialogButtonBox, QFrame, QSplitter, QComboBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt5.QtGui import QFont, QIcon

from utils import is_supported, get_book_format, get_file_hash, generate_default_cover
from parsers import BaseParser
from database import add_book, get_all_books, get_categories


class ImportWorker(QThread):
    """导入工作线程"""
    progress = pyqtSignal(int, str)  # 进度百分比, 状态文本
    finished = pyqtSignal(list)  # 导入结果列表

    def __init__(self, files, library_dir, category_id=None):
        super().__init__()
        self.files = files
        self.library_dir = library_dir
        self.category_id = category_id

    def run(self):
        results = []
        total = len(self.files)
        existing_hashes = self._get_existing_hashes()

        for i, filepath in enumerate(self.files):
            filename = os.path.basename(filepath)
            self.progress.emit(int((i / total) * 100), f"正在导入: {filename}")

            try:
                result = self._import_one(filepath, existing_hashes)
                results.append(result)
            except Exception as e:
                results.append({
                    'success': False,
                    'filename': filename,
                    'error': str(e),
                })

            self.progress.emit(int(((i + 1) / total) * 100), f"已完成: {i + 1}/{total}")

        self.progress.emit(100, "导入完成！")
        self.finished.emit(results)

    def _get_existing_hashes(self):
        """获取已有图书的哈希集合（用于重复检测）"""
        hashes = set()
        try:
            books = get_all_books()
            for book in books:
                filepath = book.get('file_path', '')
                if filepath and os.path.exists(filepath):
                    try:
                        hashes.add(get_file_hash(filepath))
                    except Exception:
                        pass
        except Exception:
            pass
        return hashes

    def _import_one(self, filepath, existing_hashes):
        """导入单个文件"""
        filename = os.path.basename(filepath)

        # 检查重复
        try:
            file_hash = get_file_hash(filepath)
            if file_hash in existing_hashes:
                return {
                    'success': False,
                    'filename': filename,
                    'error': '已存在（重复文件）',
                }
        except Exception:
            pass

        # 复制文件到 library 目录
        fmt = get_book_format(filepath)
        ext = os.path.splitext(filepath)[1].lower()
        new_filename = f"{os.path.splitext(filename)[0]}_{file_hash[:8]}{ext}"
        dest_path = os.path.join(self.library_dir, new_filename)

        try:
            shutil.copy2(filepath, dest_path)
        except Exception as e:
            return {
                'success': False,
                'filename': filename,
                'error': f'复制文件失败: {e}',
            }

        # 解析元数据
        parser = BaseParser.get_parser(filepath)
        if parser:
            try:
                metadata = parser.parse(filepath)
            except Exception:
                from parsers import BookMetadata
                metadata = BookMetadata()
                metadata.title = os.path.splitext(filename)[0]
                metadata.format = fmt
        else:
            from parsers import BookMetadata
            metadata = BookMetadata()
            metadata.title = os.path.splitext(filename)[0]
            metadata.format = fmt

        metadata.file_path = dest_path

        # 处理封面
        cover_path = ''
        if metadata.cover_image:
            # 保存提取的封面
            cover_dir = os.path.join(self.library_dir, '.covers')
            os.makedirs(cover_dir, exist_ok=True)
            cover_filename = f"{os.path.splitext(new_filename)[0]}_cover.png"
            cover_path = os.path.join(cover_dir, cover_filename)
            try:
                metadata.cover_image.save(cover_path, 'PNG')
            except Exception:
                cover_path = ''
        else:
            # 生成默认封面
            cover_dir = os.path.join(self.library_dir, '.covers')
            os.makedirs(cover_dir, exist_ok=True)
            cover_filename = f"{os.path.splitext(new_filename)[0]}_cover.png"
            cover_path = os.path.join(cover_dir, cover_filename)
            try:
                img = generate_default_cover(metadata.title, metadata.author)
                img.save(cover_path, 'PNG')
            except Exception:
                cover_path = ''

        # 添加到数据库
        book_data = {
            'title': metadata.title,
            'author': metadata.author,
            'publisher': metadata.publisher,
            'isbn': metadata.isbn,
            'description': metadata.description,
            'format': metadata.format,
            'file_path': dest_path,
            'cover_path': cover_path,
            'page_count': metadata.page_count,
            'tags': [],
            'category_id': self.category_id,
        }

        try:
            book_id = add_book(book_data)
            return {
                'success': True,
                'filename': filename,
                'title': metadata.title,
                'format': metadata.format,
                'book_id': book_id,
            }
        except Exception as e:
            return {
                'success': False,
                'filename': filename,
                'error': f'数据库写入失败: {e}',
            }


class ImportDialog(QDialog):
    """导入对话框"""

    def __init__(self, parent=None, files=None, import_path=None):
        super().__init__(parent)
        self.setWindowTitle("📥 导入图书")
        self.setMinimumSize(550, 450)
        self.resize(600, 500)
        self.setModal(True)

        # library 目录
        self.library_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'library'
        )
        os.makedirs(self.library_dir, exist_ok=True)

        # 待导入文件列表
        self.pending_files = files or []

        # 如果有导入路径，扫描文件
        if import_path:
            self._scan_path(import_path)

        self._setup_ui()

        # 如果有预设文件，直接开始
        if self.pending_files:
            self._populate_list()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 标题
        title = QLabel("选择要导入的图书文件")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(title)

        # 按钮区
        btn_layout = QHBoxLayout()

        add_files_btn = QPushButton("📂 添加文件")
        add_files_btn.clicked.connect(self._add_files)
        btn_layout.addWidget(add_files_btn)

        add_folder_btn = QPushButton("📁 添加文件夹")
        add_folder_btn.clicked.connect(self._add_folder)
        btn_layout.addWidget(add_folder_btn)

        clear_btn = QPushButton("🗑️ 清空列表")
        clear_btn.clicked.connect(self._clear_list)
        btn_layout.addWidget(clear_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # 文件列表
        self.file_list = QListWidget()
        self.file_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #dcdde1;
                border-radius: 6px;
                font-size: 12px;
            }
            QListWidget::item {
                padding: 6px;
                border-bottom: 1px solid #f0f0f0;
            }
        """)
        layout.addWidget(self.file_list)

        # 导入结果日志
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(120)
        self.log_text.setStyleSheet("""
            QTextEdit {
                border: 1px solid #dcdde1;
                border-radius: 6px;
                background-color: #f8f9fa;
                font-size: 11px;
                font-family: 'Consolas', 'Courier New', monospace;
            }
        """)
        self.log_text.hide()
        layout.addWidget(self.log_text)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #dcdde1;
                border-radius: 4px;
                text-align: center;
                height: 22px;
            }
            QProgressBar::chunk {
                background-color: #3498db;
                border-radius: 3px;
            }
        """)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        # 状态标签
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #636e72; font-size: 12px;")
        layout.addWidget(self.status_label)

        # 分类选择
        cat_layout = QHBoxLayout()
        cat_label = QLabel("导入到分类:")
        cat_label.setStyleSheet("font-size: 13px; color: #2c3e50;")
        cat_layout.addWidget(cat_label)

        self.category_combo = QComboBox()
        self.category_combo.setMinimumWidth(160)
        self.category_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #dcdde1;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 13px;
                background-color: white;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
        """)
        self.category_combo.addItem('-- 未分类 --', None)
        categories = get_categories()
        for cat in categories:
            self.category_combo.addItem(cat['name'], cat['id'])
        cat_layout.addWidget(self.category_combo)
        cat_layout.addStretch()
        layout.addLayout(cat_layout)

        # 按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.import_btn = QPushButton("🚀 开始导入")
        self.import_btn.setStyleSheet("""
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
            QPushButton:disabled {
                background-color: #b2bec3;
            }
        """)
        self.import_btn.clicked.connect(self._start_import)
        self.import_btn.setEnabled(bool(self.pending_files))
        button_layout.addWidget(self.import_btn)

        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

        if self.pending_files:
            self._populate_list()

    def _scan_path(self, path):
        """扫描路径获取图书文件"""
        files = []
        if os.path.isfile(path):
            if is_supported(path):
                files.append(path)
        elif os.path.isdir(path):
            for root, _, filenames in os.walk(path):
                for fname in filenames:
                    fpath = os.path.join(root, fname)
                    if is_supported(fpath):
                        files.append(fpath)
        self.pending_files = files

    def _add_files(self):
        """添加文件"""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "选择图书文件",
            "",
            "图书文件 (*.pdf *.epub *.mobi *.azw3 *.azw *.txt *.prc *.fb2);;所有文件 (*.*)"
        )
        if files:
            for f in files:
                if is_supported(f) and f not in self.pending_files:
                    self.pending_files.append(f)
            self._populate_list()

    def _add_folder(self):
        """添加文件夹"""
        folder = QFileDialog.getExistingDirectory(self, "选择包含图书的文件夹")
        if folder:
            self._scan_path(folder)
            self._populate_list()

    def _clear_list(self):
        """清空列表"""
        self.pending_files.clear()
        self.file_list.clear()
        self.import_btn.setEnabled(False)
        self.status_label.setText("")

    def _populate_list(self):
        """填充文件列表"""
        self.file_list.clear()
        for f in self.pending_files:
            name = os.path.basename(f)
            fmt = get_book_format(f)
            item = QListWidgetItem(f"📗 {name}  [{fmt}]")
            item.setToolTip(f)
            self.file_list.addItem(item)

        count = len(self.pending_files)
        self.status_label.setText(f"共 {count} 个文件待导入")
        self.import_btn.setEnabled(count > 0)

    def _start_import(self):
        """开始导入"""
        if not self.pending_files:
            return

        # 显示进度组件
        self.progress_bar.show()
        self.log_text.show()
        self.log_text.clear()
        self.import_btn.setEnabled(False)

        # 启动工作线程
        category_id = self.category_combo.currentData()
        self.worker = ImportWorker(self.pending_files, self.library_dir, category_id)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.start()

    def _on_progress(self, percent, message):
        """进度更新"""
        self.progress_bar.setValue(percent)
        self.status_label.setText(message)

    def _on_finished(self, results):
        """导入完成"""
        success_count = sum(1 for r in results if r['success'])
        fail_count = len(results) - success_count

        self.log_text.clear()
        self.log_text.append(f"========== 导入完成 ==========")
        self.log_text.append(f"✅ 成功: {success_count} 本")
        if fail_count > 0:
            self.log_text.append(f"❌ 失败: {fail_count} 本")
        self.log_text.append("")

        for r in results:
            if r['success']:
                self.log_text.append(f"✅ {r['title']} ({r['format']})")
            else:
                self.log_text.append(f"❌ {r['filename']}: {r.get('error', '未知错误')}")

        self.status_label.setText(f"导入完成！成功 {success_count} 本，失败 {fail_count} 本")

        # 如果全部成功，自动关闭
        if fail_count == 0 and success_count > 0:
            self.accept()
        else:
            self.import_btn.setText("关闭")
            self.import_btn.setStyleSheet("""
                QPushButton {
                    background-color: #3498db;
                    color: white;
                    border: none;
                    padding: 8px 24px;
                    border-radius: 4px;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background-color: #2980b9;
                }
            """)
            self.import_btn.setEnabled(True)
            self.import_btn.clicked.disconnect()
            self.import_btn.clicked.connect(self.accept)
