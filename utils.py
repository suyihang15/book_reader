"""工具函数模块 - 封面生成、文件哈希、格式判断等"""

import hashlib
import os
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import random


# 支持的图书格式
SUPPORTED_FORMATS = {
    '.pdf': 'PDF',
    '.epub': 'EPUB',
    '.mobi': 'MOBI',
    '.azw3': 'AZW3',
    '.azw': 'AZW',
    '.txt': 'TXT',
    '.prc': 'PRC',
    '.fb2': 'FB2',
}


def get_book_format(filepath):
    """根据文件扩展名获取格式名称"""
    ext = os.path.splitext(filepath)[1].lower()
    return SUPPORTED_FORMATS.get(ext, 'UNKNOWN')


def is_supported(filepath):
    """检查文件是否支持"""
    ext = os.path.splitext(filepath)[1].lower()
    return ext in SUPPORTED_FORMATS


def get_file_hash(filepath):
    """计算文件 MD5 哈希，用于检测重复导入"""
    hasher = hashlib.md5()
    with open(filepath, 'rb') as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()


def generate_default_cover(title, author, size=(300, 400)):
    """根据书名和作者生成默认封面图片

    生成一张纯色背景、带书名和作者文字的封面图
    """
    # 随机选择柔和的背景色（基于书名哈希保持一致性）
    hash_val = hash(title) if title else random.randint(0, 100000)
    colors = [
        (52, 73, 94),   # 深蓝灰
        (44, 62, 80),   # 深蓝
        (155, 89, 182), # 紫色
        (52, 152, 219), # 蓝色
        (26, 188, 156), # 青色
        (46, 204, 113), # 绿色
        (230, 126, 34), # 橙色
        (211, 84, 0),   # 深橙
        (192, 57, 43),  # 红色
        (127, 140, 141),# 灰色
    ]
    bg_color = colors[abs(hash_val) % len(colors)]

    img = Image.new('RGB', size, bg_color)
    draw = ImageDraw.Draw(img)

    # 尝试加载字体，失败则使用默认
    font_large = None
    font_small = None
    font_paths = [
        # Windows
        'C:/Windows/Fonts/msyh.ttc',      # 微软雅黑
        'C:/Windows/Fonts/simhei.ttf',    # 黑体
        'C:/Windows/Fonts/simsun.ttc',    # 宋体
        'C:/Windows/Fonts/arial.ttf',
        # Linux
        '/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf',
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    ]
    for font_path in font_paths:
        if os.path.exists(font_path):
            try:
                font_large = ImageFont.truetype(font_path, 24)
                font_small = ImageFont.truetype(font_path, 16)
                break
            except Exception:
                continue

    if font_large is None:
        font_large = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # 绘制装饰性边框
    margin = 15
    draw.rectangle(
        [margin, margin, size[0] - margin, size[1] - margin],
        outline=(255, 255, 255, 100),
        width=2
    )

    # 绘制书名（自动换行）
    title_text = title if title else "未命名图书"
    title_lines = _wrap_text(title_text, font_large, size[0] - 60)

    y_start = size[1] // 3
    for i, line in enumerate(title_lines):
        bbox = draw.textbbox((0, 0), line, font=font_large)
        text_width = bbox[2] - bbox[0]
        x = (size[0] - text_width) // 2
        draw.text((x, y_start + i * 35), line, fill=(255, 255, 255), font=font_large)

    # 绘制作者
    if author:
        author_text = f"— {author} —"
        bbox = draw.textbbox((0, 0), author_text, font=font_small)
        text_width = bbox[2] - bbox[0]
        x = (size[0] - text_width) // 2
        y_author = y_start + len(title_lines) * 35 + 40
        draw.text((x, y_author), author_text, fill=(200, 200, 200), font=font_small)

    # 绘制底部格式标识
    draw.text(
        (size[0] // 2 - 30, size[1] - 50),
        "📖 BookReader",
        fill=(180, 180, 180),
        font=font_small
    )

    return img


def _wrap_text(text, font, max_width):
    """将文本按宽度自动换行"""
    lines = []
    current_line = ""
    for char in text:
        test_line = current_line + char
        bbox = font.getbbox(test_line) if hasattr(font, 'getbbox') else (0, 0, len(test_line) * 15, 20)
        bbox_width = bbox[2] - bbox[0] if isinstance(bbox, tuple) else bbox[2] - bbox[0]
        if bbox_width > max_width and current_line:
            lines.append(current_line)
            current_line = char
        else:
            current_line = test_line
    if current_line:
        lines.append(current_line)
    return lines if lines else [text]


def image_to_bytes(image, format='PNG'):
    """将 PIL Image 转换为字节数据"""
    bio = BytesIO()
    image.save(bio, format=format)
    return bio.getvalue()


def scale_image(image, target_size, keep_aspect=True):
    """缩放图片到目标尺寸"""
    if keep_aspect:
        image.thumbnail(target_size, Image.LANCZOS)
        return image
    else:
        return image.resize(target_size, Image.LANCZOS)
