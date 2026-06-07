"""数据库操作模块 - SQLite 数据库初始化与 CRUD"""

import sqlite3
import os
import json
from datetime import datetime


DB_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DB_DIR, 'library.db')


def get_connection():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """初始化数据库，创建表结构"""
    conn = get_connection()
    cursor = conn.cursor()

    # 图书表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL DEFAULT '未命名',
            author TEXT DEFAULT '',
            publisher TEXT DEFAULT '',
            isbn TEXT DEFAULT '',
            description TEXT DEFAULT '',
            format TEXT DEFAULT '',
            file_path TEXT NOT NULL,
            cover_path TEXT DEFAULT '',
            page_count INTEGER DEFAULT 0,
            current_page INTEGER DEFAULT 0,
            tags TEXT DEFAULT '[]',
            date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_read TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # 创建索引
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_title ON books(title)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_author ON books(author)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_format ON books(format)')

    # 分类表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            sort_order INTEGER DEFAULT 0
        )
    ''')

    # 为 books 添加 category_id 列（兼容已有数据库）
    try:
        cursor.execute('ALTER TABLE books ADD COLUMN category_id INTEGER REFERENCES categories(id)')
    except sqlite3.OperationalError:
        pass  # 列已存在

    # 插入默认分类（如果表为空）
    cursor.execute('SELECT COUNT(*) FROM categories')
    if cursor.fetchone()[0] == 0:
        default_categories = [
            ('小说', 1), ('文学', 2), ('科技', 3), ('历史', 4),
            ('哲学', 5), ('艺术', 6), ('教育', 7), ('其他', 8),
        ]
        cursor.executemany(
            'INSERT INTO categories (name, sort_order) VALUES (?, ?)',
            default_categories
        )

    conn.commit()
    conn.close()


def add_book(metadata):
    """添加一本新书到数据库

    Args:
        metadata: dict，包含 title, author, format, file_path, cover_path,
                  page_count, publisher, isbn, description, tags, category_id

    Returns:
        int: 新书的 ID
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO books (title, author, publisher, isbn, description,
                          format, file_path, cover_path, page_count, tags, category_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        metadata.get('title', '未命名'),
        metadata.get('author', ''),
        metadata.get('publisher', ''),
        metadata.get('isbn', ''),
        metadata.get('description', ''),
        metadata.get('format', ''),
        metadata.get('file_path', ''),
        metadata.get('cover_path', ''),
        metadata.get('page_count', 0),
        json.dumps(metadata.get('tags', []), ensure_ascii=False),
        metadata.get('category_id', None),
    ))
    book_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return book_id


def get_all_books(order_by='date_added DESC'):
    """获取所有图书

    Args:
        order_by: 排序字段，默认按添加时间倒序

    Returns:
        list[dict]: 图书列表
    """
    allowed_orders = {
        'date_added': 'date_added DESC',
        'title': 'title ASC',
        'author': 'author ASC',
        'last_read': 'last_read DESC',
    }
    order = allowed_orders.get(order_by, 'date_added DESC')

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f'SELECT * FROM books ORDER BY {order}')
    rows = cursor.fetchall()
    conn.close()
    return [_row_to_dict(row) for row in rows]


def search_books(query, order_by='date_added DESC'):
    """搜索图书（按标题或作者）

    Args:
        query: 搜索关键词
        order_by: 排序字段

    Returns:
        list[dict]: 匹配的图书列表
    """
    allowed_orders = {
        'date_added': 'date_added DESC',
        'title': 'title ASC',
        'author': 'author ASC',
        'last_read': 'last_read DESC',
    }
    order = allowed_orders.get(order_by, 'date_added DESC')

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        f'SELECT * FROM books WHERE title LIKE ? OR author LIKE ? ORDER BY {order}',
        (f'%{query}%', f'%{query}%')
    )
    rows = cursor.fetchall()
    conn.close()
    return [_row_to_dict(row) for row in rows]


def get_book_by_id(book_id):
    """根据 ID 获取图书详情"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM books WHERE id = ?', (book_id,))
    row = cursor.fetchone()
    conn.close()
    return _row_to_dict(row) if row else None


def get_book_by_hash(file_hash):
    """根据文件哈希查找图书（用于重复检测）"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM books WHERE file_path LIKE ?', (f'%{file_hash}%',))
    row = cursor.fetchone()
    conn.close()
    return _row_to_dict(row) if row else None


def update_book(book_id, **kwargs):
    """更新图书信息"""
    allowed_fields = ['title', 'author', 'publisher', 'isbn', 'description',
                      'cover_path', 'page_count', 'tags', 'category_id']
    updates = {k: v for k, v in kwargs.items() if k in allowed_fields}

    if not updates:
        return

    if 'tags' in updates and isinstance(updates['tags'], list):
        updates['tags'] = json.dumps(updates['tags'], ensure_ascii=False)

    set_clause = ', '.join(f'{k} = ?' for k in updates)
    values = list(updates.values()) + [book_id]

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f'UPDATE books SET {set_clause} WHERE id = ?', values)
    conn.commit()
    conn.close()


def update_progress(book_id, current_page):
    """更新阅读进度"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE books SET current_page = ?, last_read = CURRENT_TIMESTAMP WHERE id = ?',
        (current_page, book_id)
    )
    conn.commit()
    conn.close()


def delete_book(book_id):
    """删除图书记录"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM books WHERE id = ?', (book_id,))
    conn.commit()
    conn.close()


def get_book_count():
    """获取图书总数"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM books')
    count = cursor.fetchone()[0]
    conn.close()
    return count


# ==================== 分类管理 ====================

def get_categories():
    """获取所有分类（按 sort_order 排序）

    Returns:
        list[dict]: 分类列表，每个包含 id, name, sort_order, book_count
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT c.id, c.name, c.sort_order,
               COUNT(b.id) AS book_count
        FROM categories c
        LEFT JOIN books b ON b.category_id = c.id
        GROUP BY c.id
        ORDER BY c.sort_order
    ''')
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def add_category(name, sort_order=None):
    """添加新分类

    Args:
        name: 分类名称
        sort_order: 排序序号（可选，默认取最大值+1）

    Returns:
        int: 新分类的 ID，失败返回 None
    """
    if sort_order is None:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT MAX(sort_order) FROM categories')
        max_order = cursor.fetchone()[0] or 0
        sort_order = max_order + 1
    else:
        conn = get_connection()
        cursor = conn.cursor()

    try:
        cursor.execute(
            'INSERT INTO categories (name, sort_order) VALUES (?, ?)',
            (name, sort_order)
        )
        cat_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return cat_id
    except sqlite3.IntegrityError:
        conn.close()
        return None  # 名称重复


def update_category(category_id, name=None, sort_order=None):
    """更新分类信息

    Args:
        category_id: 分类 ID
        name: 新名称（可选）
        sort_order: 新排序（可选）
    """
    updates = {}
    if name is not None:
        updates['name'] = name
    if sort_order is not None:
        updates['sort_order'] = sort_order
    if not updates:
        return

    set_clause = ', '.join(f'{k} = ?' for k in updates)
    values = list(updates.values()) + [category_id]

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(f'UPDATE categories SET {set_clause} WHERE id = ?', values)
        conn.commit()
    except sqlite3.IntegrityError:
        pass  # 名称重复
    finally:
        conn.close()


def delete_category(category_id):
    """删除分类，并将该分类下的图书设为未分类

    Args:
        category_id: 分类 ID
    """
    conn = get_connection()
    cursor = conn.cursor()
    # 将该分类下的图书 category_id 置空
    cursor.execute(
        'UPDATE books SET category_id = NULL WHERE category_id = ?',
        (category_id,)
    )
    cursor.execute('DELETE FROM categories WHERE id = ?', (category_id,))
    conn.commit()
    conn.close()


def get_books_by_category(category_id, order_by='date_added DESC'):
    """获取指定分类下的图书

    Args:
        category_id: 分类 ID，None 表示未分类
        order_by: 排序字段

    Returns:
        list[dict]: 图书列表
    """
    allowed_orders = {
        'date_added': 'date_added DESC',
        'title': 'title ASC',
        'author': 'author ASC',
        'last_read': 'last_read DESC',
    }
    order = allowed_orders.get(order_by, 'date_added DESC')

    conn = get_connection()
    cursor = conn.cursor()
    if category_id is None:
        cursor.execute(f'SELECT * FROM books WHERE category_id IS NULL ORDER BY {order}')
    else:
        cursor.execute(
            f'SELECT * FROM books WHERE category_id = ? ORDER BY {order}',
            (category_id,)
        )
    rows = cursor.fetchall()
    conn.close()
    return [_row_to_dict(row) for row in rows]


def _row_to_dict(row):
    """将 sqlite3.Row 转换为普通 dict"""
    d = dict(row)
    # 解析 tags JSON
    if 'tags' in d and isinstance(d['tags'], str):
        try:
            d['tags'] = json.loads(d['tags'])
        except (json.JSONDecodeError, TypeError):
            d['tags'] = []
    return d
