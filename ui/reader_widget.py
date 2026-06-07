"""阅读器视图模块 - PDF 逐页渲染、EPUB/TXT 文本显示、主题切换"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QScrollArea, QSlider, QComboBox, QTextBrowser, QFrame,
    QMessageBox, QSizePolicy, QSpacerItem
)
from PyQt5.QtCore import Qt, QSize, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QPixmap, QImage, QKeyEvent, QIcon, QColor
from io import BytesIO
from PIL import Image

from parsers import BaseParser


class PDFPageWidget(QLabel):
    """PDF 页面显示组件"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def show_page(self, pil_image):
        """显示 PDF 页面"""
        if pil_image is None:
            self.setText("无法加载页面")
            return

        # 转换 PIL Image 为 QPixmap
        bio = BytesIO()
        pil_image.save(bio, format='PNG')
        pixmap = QPixmap()
        pixmap.loadFromData(bio.getvalue())

        # 缩放到合适宽度
        if self.parent() and self.parent().width() > 100:
            target_width = self.parent().width() - 40
            scaled = pixmap.scaledToWidth(
                target_width,
                Qt.SmoothTransformation
            )
        else:
            scaled = pixmap

        self.setPixmap(scaled)
        self.setFixedHeight(scaled.height())


class ReaderWidget(QWidget):
    """阅读器视图"""
    back_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.book = None
        self.current_page = 0
        self.total_pages = 0
        self.parser = None
        self.epub_pages = []  # EPUB 的页面内容缓存
        self.pdf_pages = []   # PDF 的页面缓存（PIL Images）

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # === 顶部工具栏 ===
        toolbar = QFrame()
        toolbar.setStyleSheet("""
            QFrame {
                background-color: #2c3e50;
                border: none;
            }
        """)
        toolbar.setFixedHeight(48)
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(10, 6, 10, 6)

        # 返回按钮
        back_btn = QPushButton("← 返回书架")
        back_btn.setStyleSheet("""
            QPushButton {
                background-color: #34495e;
                color: white;
                border: none;
                padding: 6px 14px;
                border-radius: 4px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #2c3e50;
            }
        """)
        back_btn.clicked.connect(self._on_back)
        toolbar_layout.addWidget(back_btn)

        toolbar_layout.addSpacing(10)

        # 书名
        self.title_label = QLabel("")
        self.title_label.setStyleSheet("color: white; font-size: 14px; font-weight: bold;")
        toolbar_layout.addWidget(self.title_label)

        toolbar_layout.addStretch()

        # 页码
        self.page_label = QLabel("")
        self.page_label.setStyleSheet("color: #bdc3c7; font-size: 13px;")
        toolbar_layout.addWidget(self.page_label)

        toolbar_layout.addSpacing(15)

        # 字体缩小
        font_dec_btn = QPushButton("A-")
        font_dec_btn.setStyleSheet(self._toolbar_btn_style())
        font_dec_btn.clicked.connect(self._font_smaller)
        toolbar_layout.addWidget(font_dec_btn)

        # 字体放大
        font_inc_btn = QPushButton("A+")
        font_inc_btn.setStyleSheet(self._toolbar_btn_style())
        font_inc_btn.clicked.connect(self._font_larger)
        toolbar_layout.addWidget(font_inc_btn)

        toolbar_layout.addSpacing(10)

        # 主题切换
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["☀️ 日间", "🌙 夜间", "📜 护眼"])
        self.theme_combo.setStyleSheet("""
            QComboBox {
                background-color: #34495e;
                color: white;
                border: 1px solid #4a6375;
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 12px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: white;
                color: #2c3e50;
                selection-background-color: #3498db;
            }
        """)
        self.theme_combo.currentIndexChanged.connect(self._on_theme_change)
        toolbar_layout.addWidget(self.theme_combo)

        layout.addWidget(toolbar)

        # === 页面导航条 ===
        nav_frame = QFrame()
        nav_frame.setStyleSheet("background-color: #f8f9fa; border-bottom: 1px solid #e0e0e0;")
        nav_frame.setFixedHeight(40)
        nav_layout = QHBoxLayout(nav_frame)
        nav_layout.setContentsMargins(15, 4, 15, 4)

        # 上一页
        prev_btn = QPushButton("◀ 上一页")
        prev_btn.setStyleSheet(self._nav_btn_style())
        prev_btn.clicked.connect(self._prev_page)
        nav_layout.addWidget(prev_btn)

        # 页数滑块
        self.page_slider = QSlider(Qt.Horizontal)
        self.page_slider.setMinimum(0)
        self.page_slider.valueChanged.connect(self._on_slider_change)
        self.page_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 6px;
                background: #dfe6e9;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #3498db;
                width: 16px;
                height: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }
            QSlider::sub-page:horizontal {
                background: #3498db;
                border-radius: 3px;
            }
        """)
        nav_layout.addWidget(self.page_slider)

        # 下一页
        next_btn = QPushButton("下一页 ▶")
        next_btn.setStyleSheet(self._nav_btn_style())
        next_btn.clicked.connect(self._next_page)
        nav_layout.addWidget(next_btn)

        # 页码输入
        self.page_input_label = QLabel("跳转:")
        self.page_input_label.setStyleSheet("color: #636e72; font-size: 12px;")
        nav_layout.addWidget(self.page_input_label)

        from PyQt5.QtWidgets import QSpinBox
        self.page_spin = QSpinBox()
        self.page_spin.setMinimum(1)
        self.page_spin.setMaximum(1)
        self.page_spin.setStyleSheet("""
            QSpinBox {
                border: 1px solid #dcdde1;
                border-radius: 3px;
                padding: 2px 4px;
                width: 60px;
            }
        """)
        self.page_spin.valueChanged.connect(self._on_spin_change)
        nav_layout.addWidget(self.page_spin)

        layout.addWidget(nav_frame)

        # === 内容区域 ===
        # PDF 滚动视图
        self.pdf_scroll = QScrollArea()
        self.pdf_scroll.setWidgetResizable(True)
        self.pdf_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.pdf_scroll.setStyleSheet("background-color: #f5f6fa; border: none;")
        self.pdf_container = QWidget()
        self.pdf_layout = QVBoxLayout(self.pdf_container)
        self.pdf_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.pdf_layout.setSpacing(10)
        self.pdf_scroll.setWidget(self.pdf_container)

        # EPUB/TXT 文本浏览器
        self.text_browser = QTextBrowser()
        self.text_browser.setOpenExternalLinks(False)
        self.text_browser.setStyleSheet("""
            QTextBrowser {
                background-color: #ffffff;
                border: none;
                font-family: 'Microsoft YaHei', 'SimHei', 'Noto Sans CJK SC', sans-serif;
                font-size: 16px;
                padding: 30px;
            }
        """)

        # 默认显示 PDF 区域
        self.pdf_scroll.show()
        self.text_browser.hide()

        layout.addWidget(self.pdf_scroll)
        layout.addWidget(self.text_browser)

        # 当前字体大小
        self.current_font_size = 16
        self.current_theme = 'day'

    def load_book(self, book):
        """加载图书"""
        self.book = book
        self.current_page = book.get('current_page', 0)

        filepath = book['file_path']
        fmt = book.get('format', '')

        # 获取解析器
        self.parser = BaseParser.get_parser(filepath)
        if not self.parser:
            QMessageBox.warning(self, "错误", f"不支持的格式: {fmt}")
            self._on_back()
            return

        # 更新标题
        self.title_label.setText(f"📖 {book.get('title', '未命名')}")

        # 根据格式加载内容
        if fmt == 'PDF':
            self._load_pdf(filepath)
        elif fmt in ('EPUB',):
            self._load_epub(filepath)
        elif fmt in ('TXT',):
            self._load_txt(filepath)
        else:
            self._load_text_fallback(filepath, fmt)

        # 更新页码信息
        self._update_page_display()

        # 跳转到上次阅读位置
        self._go_to_page(min(self.current_page, self.total_pages - 1))

    def _load_pdf(self, filepath):
        """加载 PDF"""
        try:
            import fitz
            doc = fitz.open(filepath)
            self.total_pages = doc.page_count
            self.pdf_pages = []
            for i in range(doc.page_count):
                page = doc[i]
                pix = page.get_pixmap(dpi=150)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                self.pdf_pages.append(img)
            doc.close()
        except Exception as e:
            QMessageBox.warning(self, "加载失败", f"PDF 加载失败: {e}")
            self._on_back()
            return

        self.text_browser.hide()
        self.pdf_scroll.show()
        self._show_pdf_page(self.current_page)

    def _load_epub(self, filepath):
        """加载 EPUB"""
        try:
            content_pages = self.parser.get_all_text(filepath)
            self.epub_pages = content_pages
            self.total_pages = len(content_pages) if content_pages else 1
        except Exception as e:
            self.epub_pages = [f'<p>加载失败: {e}</p>']
            self.total_pages = 1

        self.pdf_scroll.hide()
        self.text_browser.show()
        self._show_epub_page(self.current_page)

    def _load_txt(self, filepath):
        """加载 TXT"""
        try:
            all_text = self.parser.get_all_text(filepath)
            if all_text:
                # 按字符数分页
                chars_per_page = 2000
                self.epub_pages = []
                for i in range(0, len(all_text), chars_per_page):
                    chunk = all_text[i:i + chars_per_page]
                    # 转换为简单的 HTML
                    html_chunk = '<pre style="white-space: pre-wrap; font-family: inherit;">' + chunk.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;') + '</pre>'
                    self.epub_pages.append(html_chunk)
                self.total_pages = len(self.epub_pages)
            else:
                self.epub_pages = ['<p>无法读取文件内容</p>']
                self.total_pages = 1
        except Exception as e:
            self.epub_pages = [f'<p>加载失败: {e}</p>']
            self.total_pages = 1

        self.pdf_scroll.hide()
        self.text_browser.show()
        self._show_epub_page(self.current_page)

    def _load_text_fallback(self, filepath, fmt):
        """不支持直接阅读的格式"""
        self.pdf_scroll.hide()
        self.text_browser.show()
        self.epub_pages = [
            f'<div style="text-align:center; padding:50px;">'
            f'<h2>⚠️ {fmt} 格式暂不支持直接阅读</h2>'
            f'<p>文件路径: {filepath}</p>'
            f'<p>建议使用 Calibre 等工具转换为 EPUB 或 PDF 格式后重新导入。</p>'
            f'</div>'
        ]
        self.total_pages = 1
        self._show_epub_page(0)

    def _show_pdf_page(self, page_num):
        """显示 PDF 页面"""
        if 0 <= page_num < len(self.pdf_pages):
            # 清除旧的内容
            while self.pdf_layout.count():
                item = self.pdf_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            # 显示当前页
            page_widget = PDFPageWidget(self.pdf_scroll)
            page_widget.show_page(self.pdf_pages[page_num])
            self.pdf_layout.addWidget(page_widget)

            # 预加载下一页
            if page_num + 1 < len(self.pdf_pages):
                next_widget = PDFPageWidget(self.pdf_scroll)
                next_widget.show_page(self.pdf_pages[page_num + 1])
                self.pdf_layout.addWidget(next_widget)

            self.current_page = page_num
            self.pdf_scroll.verticalScrollBar().setValue(0)
            self._save_progress()

    def _show_epub_page(self, page_num):
        """显示 EPUB/TXT 页面"""
        if 0 <= page_num < len(self.epub_pages):
            content = self.epub_pages[page_num]
            self.text_browser.setHtml(self._wrap_html(content))
            self.text_browser.verticalScrollBar().setValue(0)
            self.current_page = page_num
            self._save_progress()

    def _wrap_html(self, content):
        """包装 HTML 内容，应用当前主题"""
        if self.current_theme == 'night':
            bg = '#1a1a2e'
            fg = '#e0e0e0'
        elif self.current_theme == 'sepia':
            bg = '#f5deb3'
            fg = '#4a3728'
        else:
            bg = '#ffffff'
            fg = '#2c3e50'

        return f'''
        <html><head><style>
            body {{
                background-color: {bg};
                color: {fg};
                font-family: 'Microsoft YaHei', 'SimHei', 'Noto Sans CJK SC', 'DejaVu Sans', sans-serif;
                font-size: {self.current_font_size}px;
                line-height: 1.8;
                max-width: 800px;
                margin: 0 auto;
            }}
            img {{ max-width: 100%; }}
            h1, h2, h3 {{ color: {fg}; }}
        </style></head><body>{content}</body></html>
        '''

    def _go_to_page(self, page_num):
        """跳转到指定页"""
        page_num = max(0, min(page_num, self.total_pages - 1))
        if self.book and self.book.get('format') == 'PDF':
            self._show_pdf_page(page_num)
        else:
            self._show_epub_page(page_num)
        self._update_page_display()

    def _next_page(self):
        """下一页"""
        if self.current_page < self.total_pages - 1:
            self._go_to_page(self.current_page + 1)

    def _prev_page(self):
        """上一页"""
        if self.current_page > 0:
            self._go_to_page(self.current_page - 1)

    def _on_slider_change(self, value):
        """滑块值改变"""
        if value != self.current_page:
            self._go_to_page(value)

    def _on_spin_change(self, value):
        """页码输入改变"""
        page = value - 1  # 转为 0-based
        if page != self.current_page:
            self._go_to_page(page)

    def _update_page_display(self):
        """更新页码显示"""
        self.page_label.setText(f"📄 {self.current_page + 1} / {self.total_pages}")
        self.page_slider.blockSignals(True)
        self.page_slider.setMaximum(max(0, self.total_pages - 1))
        self.page_slider.setValue(self.current_page)
        self.page_slider.blockSignals(False)
        self.page_spin.blockSignals(True)
        self.page_spin.setMaximum(max(1, self.total_pages))
        self.page_spin.setValue(self.current_page + 1)
        self.page_spin.blockSignals(False)

    def _save_progress(self):
        """保存阅读进度"""
        if self.book:
            from database import update_progress
            update_progress(self.book['id'], self.current_page)

    def _on_theme_change(self, index):
        """主题切换"""
        themes = {0: 'day', 1: 'night', 2: 'sepia'}
        self.current_theme = themes.get(index, 'day')

        if self.book and self.book.get('format') == 'PDF':
            # PDF 模式下调整背景色
            if self.current_theme == 'night':
                self.pdf_scroll.setStyleSheet("background-color: #1a1a2e; border: none;")
            elif self.current_theme == 'sepia':
                self.pdf_scroll.setStyleSheet("background-color: #f5deb3; border: none;")
            else:
                self.pdf_scroll.setStyleSheet("background-color: #f5f6fa; border: none;")
        else:
            # 文本模式下重新渲染
            self._show_epub_page(self.current_page)

    def _font_larger(self):
        """放大字体"""
        self.current_font_size = min(32, self.current_font_size + 2)
        if not (self.book and self.book.get('format') == 'PDF'):
            self._show_epub_page(self.current_page)

    def _font_smaller(self):
        """缩小字体"""
        self.current_font_size = max(10, self.current_font_size - 2)
        if not (self.book and self.book.get('format') == 'PDF'):
            self._show_epub_page(self.current_page)

    def _on_back(self):
        """返回书架"""
        self.back_requested.emit()

    def keyPressEvent(self, event):
        """键盘事件"""
        if event.key() == Qt.Key_Left or event.key() == Qt.Key_A:
            self._prev_page()
        elif event.key() == Qt.Key_Right or event.key() == Qt.Key_D:
            self._next_page()
        elif event.key() == Qt.Key_Escape:
            self._on_back()
        elif event.key() == Qt.Key_Home:
            self._go_to_page(0)
        elif event.key() == Qt.Key_End:
            self._go_to_page(self.total_pages - 1)
        else:
            super().keyPressEvent(event)

    def _toolbar_btn_style(self):
        return """
            QPushButton {
                background-color: #34495e;
                color: white;
                border: none;
                padding: 4px 10px;
                border-radius: 3px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2c3e50;
            }
        """

    def _nav_btn_style(self):
        return """
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 4px 14px;
                border-radius: 3px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """
