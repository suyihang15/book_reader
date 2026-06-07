"""图书格式解析器模块 - 支持 PDF、EPUB、MOBI、TXT 等格式"""

import os
import re
import shutil
from abc import ABC, abstractmethod
from io import BytesIO
from PIL import Image
from utils import get_file_hash


class BookMetadata:
    """图书元数据数据类"""
    def __init__(self):
        self.title = '未命名'
        self.author = ''
        self.publisher = ''
        self.isbn = ''
        self.description = ''
        self.format = ''
        self.page_count = 0
        self.file_path = ''
        self.cover_path = ''  # 提取的封面图片路径
        self.cover_image = None  # PIL Image 对象
        self.toc = []  # 目录 [(title, page/href), ...]
        self.file_hash = ''
        self.file_size = 0


class BaseParser(ABC):
    """解析器基类"""

    @abstractmethod
    def parse(self, filepath):
        """解析图书文件，返回 BookMetadata"""
        pass

    @abstractmethod
    def get_cover(self, filepath):
        """提取封面图片，返回 PIL Image 或 None"""
        pass

    @abstractmethod
    def get_content(self, filepath, page=0):
        """获取指定页的内容（用于阅读）

        Returns:
            dict: {'type': 'image'|'text'|'html', 'data': ..., 'page': int, 'total': int}
        """
        pass

    @abstractmethod
    def get_toc(self, filepath):
        """获取目录结构"""
        pass

    @staticmethod
    def get_parser(filepath):
        """工厂方法：根据文件扩展名返回对应的解析器"""
        ext = os.path.splitext(filepath)[1].lower()
        if ext == '.pdf':
            return PDFParser()
        elif ext == '.epub':
            return EPUBParser()
        elif ext in ('.mobi', '.azw3', '.azw', '.prc'):
            return MOBIParser()
        elif ext == '.txt':
            return TXTParser()
        elif ext == '.fb2':
            return FB2Parser()
        else:
            return None


# ==================== PDF 解析器 ====================

class PDFParser(BaseParser):
    """PDF 格式解析器 (使用 PyMuPDF)"""

    def parse(self, filepath):
        try:
            import fitz  # PyMuPDF
        except ImportError:
            return self._basic_parse(filepath)

        meta = BookMetadata()
        meta.format = 'PDF'
        meta.file_path = filepath
        meta.file_hash = get_file_hash(filepath)
        meta.file_size = os.path.getsize(filepath)

        try:
            doc = fitz.open(filepath)
            meta.page_count = doc.page_count

            # 提取元数据
            pdf_meta = doc.metadata
            if pdf_meta.get('title'):
                meta.title = pdf_meta['title'].strip()
            if pdf_meta.get('author'):
                meta.author = pdf_meta['author'].strip()
            if pdf_meta.get('publisher'):
                meta.publisher = pdf_meta.get('publisher', '')

            # 提取目录
            toc = doc.get_toc()
            if toc:
                meta.toc = [(item[1], item[2]) for item in toc]

            # 提取封面（第一页）
            if doc.page_count > 0:
                cover = self._render_page_as_image(doc, 0)
                if cover:
                    meta.cover_image = cover

            doc.close()
        except Exception as e:
            print(f"PDF 解析警告: {e}")
            meta.page_count = 0

        # 如果没有从元数据获取到标题，用文件名
        if not meta.title or meta.title == '未命名':
            meta.title = os.path.splitext(os.path.basename(filepath))[0]

        return meta

    def get_cover(self, filepath):
        try:
            import fitz
            doc = fitz.open(filepath)
            if doc.page_count > 0:
                cover = self._render_page_as_image(doc, 0)
                doc.close()
                return cover
            doc.close()
        except Exception:
            pass
        return None

    def get_content(self, filepath, page=0):
        try:
            import fitz
            doc = fitz.open(filepath)
            total = doc.page_count
            page = max(0, min(page, total - 1))

            page_obj = doc[page]
            pix = page_obj.get_pixmap(dpi=150)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            doc.close()
            return {
                'type': 'image',
                'data': img,
                'page': page,
                'total': total,
            }
        except Exception as e:
            return {
                'type': 'text',
                'data': f'无法加载页面: {e}',
                'page': page,
                'total': 0,
            }

    def get_toc(self, filepath):
        try:
            import fitz
            doc = fitz.open(filepath)
            toc = doc.get_toc()
            doc.close()
            return [(item[1], item[2]) for item in toc] if toc else []
        except Exception:
            return []

    def _render_page_as_image(self, doc, page_num):
        """将 PDF 页面渲染为 PIL Image"""
        try:
            page = doc[page_num]
            pix = page.get_pixmap(dpi=120)
            return Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        except Exception:
            return None

    def _basic_parse(self, filepath):
        """无 PyMuPDF 时的基础解析"""
        meta = BookMetadata()
        meta.format = 'PDF'
        meta.file_path = filepath
        meta.file_hash = get_file_hash(filepath)
        meta.file_size = os.path.getsize(filepath)
        meta.title = os.path.splitext(os.path.basename(filepath))[0]
        meta.page_count = 0
        return meta


# ==================== EPUB 解析器 ====================

class EPUBParser(BaseParser):
    """EPUB 格式解析器"""

    def parse(self, filepath):
        meta = BookMetadata()
        meta.format = 'EPUB'
        meta.file_path = filepath
        meta.file_hash = get_file_hash(filepath)
        meta.file_size = os.path.getsize(filepath)

        try:
            from ebooklib import epub
            book = epub.read_epub(filepath)

            # 提取元数据
            titles = book.get_metadata('DC', 'title')
            if titles:
                meta.title = titles[0][0].strip()

            creators = book.get_metadata('DC', 'creator')
            if creators:
                meta.author = creators[0][0].strip()

            publishers = book.get_metadata('DC', 'publisher')
            if publishers:
                meta.publisher = publishers[0][0].strip()

            identifiers = book.get_metadata('DC', 'identifier')
            for uid in identifiers:
                val = uid[0]
                if 'isbn' in str(val).lower() or (val.isdigit() and len(val) == 13):
                    meta.isbn = str(val)
                    break

            descriptions = book.get_metadata('DC', 'description')
            if descriptions:
                meta.description = descriptions[0][0][:500]

            # 提取封面图片
            cover = self._extract_cover_image(book)
            if cover:
                meta.cover_image = cover

            # 提取目录
            meta.toc = self._extract_toc(book)
            meta.page_count = self._estimate_pages(book)

        except Exception as e:
            print(f"EPUB 解析警告: {e}")

        if not meta.title or meta.title == '未命名':
            meta.title = os.path.splitext(os.path.basename(filepath))[0]

        return meta

    def get_cover(self, filepath):
        try:
            from ebooklib import epub
            book = epub.read_epub(filepath)
            return self._extract_cover_image(book)
        except Exception:
            return None

    def get_content(self, filepath, page=0):
        """获取 EPUB 内容 - 返回全文 HTML"""
        try:
            from ebooklib import epub
            from bs4 import BeautifulSoup

            book = epub.read_epub(filepath)
            items = list(book.get_items_of_type(9))  # ITEM_DOCUMENT = 9

            if not items:
                return {'type': 'text', 'data': '无法读取内容', 'page': 0, 'total': 0}

            page = max(0, min(page, len(items) - 1))
            item = items[page]

            content = item.get_content().decode('utf-8', errors='replace')
            soup = BeautifulSoup(content, 'lxml')
            body = soup.find('body')
            html = str(body) if body else content

            return {
                'type': 'html',
                'data': html,
                'page': page,
                'total': len(items),
            }
        except Exception as e:
            return {'type': 'text', 'data': f'加载失败: {e}', 'page': 0, 'total': 0}

    def get_toc(self, filepath):
        try:
            from ebooklib import epub
            book = epub.read_epub(filepath)
            return self._extract_toc(book)
        except Exception:
            return []

    def get_all_text(self, filepath):
        """获取 EPUB 全部文本内容（用于阅读器）"""
        try:
            from ebooklib import epub
            from bs4 import BeautifulSoup

            book = epub.read_epub(filepath)
            items = list(book.get_items_of_type(9))

            all_html_parts = []
            for item in items:
                content = item.get_content().decode('utf-8', errors='replace')
                soup = BeautifulSoup(content, 'lxml')
                body = soup.find('body')
                if body:
                    all_html_parts.append(str(body))
                else:
                    all_html_parts.append(content)

            return all_html_parts
        except Exception as e:
            return [f'<p>加载失败: {e}</p>']

    def _extract_cover_image(self, book):
        """从 EPUB 中提取封面图片"""
        try:
            from ebooklib import epub

            # 方法1：通过 cover 元数据查找
            covers = book.get_metadata('OPF', 'cover')
            if covers:
                cover_id = covers[0][0]
                cover_item = book.get_item_by_id(cover_id)
                if cover_item:
                    return Image.open(BytesIO(cover_item.get_content()))

            # 方法2：查找名称包含 cover 的图片
            for item in book.get_items_of_type(6):  # ITEM_IMAGE = 6
                name = item.get_name().lower()
                if 'cover' in name:
                    try:
                        return Image.open(BytesIO(item.get_content()))
                    except Exception:
                        continue

            # 方法3：返回第一张图片
            images = list(book.get_items_of_type(6))
            if images:
                try:
                    return Image.open(BytesIO(images[0].get_content()))
                except Exception:
                    pass
        except Exception:
            pass
        return None

    def _extract_toc(self, book):
        """提取 EPUB 目录"""
        toc = []
        try:
            from ebooklib import epub
            book_toc = book.toc
            for item in book_toc:
                if hasattr(item, 'title') and hasattr(item, 'href'):
                    toc.append((item.title, item.href))
        except Exception:
            pass
        return toc

    def _estimate_pages(self, book):
        """估算 EPUB 页数"""
        try:
            count = len(list(book.get_items_of_type(9)))
            return max(1, count)
        except Exception:
            return 0


# ==================== TXT 解析器 ====================

class TXTParser(BaseParser):
    """TXT 格式解析器"""

    def parse(self, filepath):
        meta = BookMetadata()
        meta.format = 'TXT'
        meta.file_path = filepath
        meta.file_hash = get_file_hash(filepath)
        meta.file_size = os.path.getsize(filepath)

        try:
            # 尝试多种编码
            content = None
            for encoding in ['utf-8', 'gbk', 'gb18030', 'latin-1']:
                try:
                    with open(filepath, 'r', encoding=encoding) as f:
                        content = f.read(5000)  # 读取前 5000 字符
                    break
                except UnicodeDecodeError:
                    continue

            if content:
                lines = content.strip().split('\n')
                # 使用第一行非空行作为标题
                for line in lines[:10]:
                    line = line.strip()
                    if line and len(line) > 1:
                        meta.title = line[:100]
                        break

                # 估算页数（按每页 2000 字符计算）
                total_chars = os.path.getsize(filepath)
                # 粗略估算（中文每字符 2-3 字节）
                estimated_chars = total_chars // 2
                meta.page_count = max(1, estimated_chars // 2000)

        except Exception as e:
            print(f"TXT 解析警告: {e}")

        if not meta.title or meta.title == '未命名':
            meta.title = os.path.splitext(os.path.basename(filepath))[0]

        return meta

    def get_cover(self, filepath):
        return None  # TXT 没有封面

    def get_content(self, filepath, page=0):
        """获取 TXT 指定页内容"""
        try:
            content = self._read_full_text(filepath)
            if not content:
                return {'type': 'text', 'data': '无法读取文件', 'page': 0, 'total': 0}

            # 按段落分割，每 50 段一页
            paragraphs = content.split('\n')
            chars_per_page = 2000
            pages = []
            current_page = ""
            for para in paragraphs:
                if len(current_page) + len(para) < chars_per_page:
                    current_page += para + '\n'
                else:
                    pages.append(current_page)
                    current_page = para + '\n'
            if current_page:
                pages.append(current_page)

            if not pages:
                pages = [content]

            total = len(pages)
            page = max(0, min(page, total - 1))

            return {
                'type': 'text',
                'data': pages[page],
                'page': page,
                'total': total,
            }
        except Exception as e:
            return {'type': 'text', 'data': f'加载失败: {e}', 'page': 0, 'total': 0}

    def get_toc(self, filepath):
        return []

    def get_all_text(self, filepath):
        """获取全部文本"""
        return self._read_full_text(filepath)

    def _read_full_text(self, filepath):
        """读取完整文本内容"""
        for encoding in ['utf-8', 'gbk', 'gb18030', 'latin-1']:
            try:
                with open(filepath, 'r', encoding=encoding) as f:
                    return f.read()
            except (UnicodeDecodeError, UnicodeError):
                continue
        return None


# ==================== MOBI 解析器 ====================

class MOBIParser(BaseParser):
    """MOBI/AZW 格式解析器（基础支持）"""

    def parse(self, filepath):
        meta = BookMetadata()
        ext = os.path.splitext(filepath)[1].lower()
        fmt_map = {'.mobi': 'MOBI', '.azw3': 'AZW3', '.azw': 'AZW', '.prc': 'PRC'}
        meta.format = fmt_map.get(ext, 'MOBI')
        meta.file_path = filepath
        meta.file_hash = get_file_hash(filepath)
        meta.file_size = os.path.getsize(filepath)

        # 尝试提取元数据
        try:
            self._parse_mobi_header(filepath, meta)
        except Exception as e:
            print(f"MOBI 解析警告: {e}")

        if not meta.title or meta.title == '未命名':
            meta.title = os.path.splitext(os.path.basename(filepath))[0]

        return meta

    def get_cover(self, filepath):
        """尝试从 MOBI 中提取封面"""
        try:
            # MOBI 格式封面提取较复杂，尝试使用简单方法
            with open(filepath, 'rb') as f:
                data = f.read()

            # 查找 JPEG/GIF/PNG 图片标记
            # 这是简化版，完整版需要解析 PDB 头
            img_start = data.find(b'\xff\xd8\xff')  # JPEG SOI
            if img_start > 0:
                img_end = data.find(b'\xff\xd9', img_start)  # JPEG EOI
                if img_end > img_start:
                    img_data = data[img_start:img_end + 2]
                    try:
                        return Image.open(BytesIO(img_data))
                    except Exception:
                        pass
        except Exception:
            pass
        return None

    def get_content(self, filepath, page=0):
        return {'type': 'text', 'data': 'MOBI 格式暂不支持直接阅读，请转换为 EPUB 或 PDF 格式后导入。', 'page': 0, 'total': 0}

    def get_toc(self, filepath):
        return []

    def _parse_mobi_header(self, filepath, meta):
        """解析 MOBI 文件头，提取元数据"""
        try:
            with open(filepath, 'rb') as f:
                # 读取前 1024 字节来解析基本头信息
                header = f.read(1024)

            # 尝试在二进制数据中查找文本元数据
            # MOBI 文件的 text record 中包含元数据
            text = header.decode('ascii', errors='ignore')

            # 查找标题（通常以特定标记出现）
            for pattern in [r'(\w[\w\s]{2,80})']:
                match = re.search(pattern, text)
                if match and len(match.group(1)) > 3:
                    potential_title = match.group(1).strip()
                    if not any(skip in potential_title.lower() for skip in ['mobi', 'book', 'content']):
                        if meta.title == '未命名':
                            meta.title = potential_title

        except Exception:
            pass


# ==================== FB2 解析器 ====================

class FB2Parser(BaseParser):
    """FB2 格式解析器 (FictionBook 2)"""

    def parse(self, filepath):
        meta = BookMetadata()
        meta.format = 'FB2'
        meta.file_path = filepath
        meta.file_hash = get_file_hash(filepath)
        meta.file_size = os.path.getsize(filepath)

        try:
            import xml.etree.ElementTree as ET
            tree = ET.parse(filepath)
            root = tree.getroot()

            # 查找 title
            for title_elem in root.iter('{http://www.gribuser.ru/xml/fictionbook/2.0}book-title'):
                meta.title = title_elem.text.strip() if title_elem.text else meta.title
                break

            # 查找 author
            for author_elem in root.iter('{http://www.gribuser.ru/xml/fictionbook/2.0}author'):
                first = author_elem.find('{http://www.gribuser.ru/xml/fictionbook/2.0}first-name')
                last = author_elem.find('{http://www.gribuser.ru/xml/fictionbook/2.0}last-name')
                parts = []
                if first is not None and first.text:
                    parts.append(first.text.strip())
                if last is not None and last.text:
                    parts.append(last.text.strip())
                if parts:
                    meta.author = ' '.join(parts)
                    break

            # 查找封面
            for cover in root.iter('{http://www.gribuser.ru/xml/fictionbook/2.0}coverpage'):
                for img in cover.iter('{http://www.gribuser.ru/xml/fictionbook/2.0}image'):
                    href = img.get('{http://www.w3.org/1999/xlink}href', '')
                    if href:
                        # 尝试从同一目录加载图片
                        base_dir = os.path.dirname(filepath)
                        img_path = os.path.join(base_dir, href.lstrip('#'))
                        if os.path.exists(img_path):
                            try:
                                meta.cover_image = Image.open(img_path)
                            except Exception:
                                pass

        except Exception as e:
            print(f"FB2 解析警告: {e}")

        if not meta.title or meta.title == '未命名':
            meta.title = os.path.splitext(os.path.basename(filepath))[0]

        return meta

    def get_cover(self, filepath):
        return None

    def get_content(self, filepath, page=0):
        return {'type': 'text', 'data': 'FB2 格式基础支持，请转换为 EPUB 格式以获得更好的阅读体验。', 'page': 0, 'total': 0}

    def get_toc(self, filepath):
        return []
