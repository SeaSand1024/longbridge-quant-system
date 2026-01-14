from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import pymysql

from app.core.config import DB_CONFIG


def get_db_connection():
    """创建新的数据库连接。"""
    return pymysql.connect(**DB_CONFIG)


@contextmanager
def get_cursor(dict_cursor: bool = True) -> Iterator[pymysql.cursors.Cursor]:
    """提供一个自动提交/关闭的游标上下文。"""
    conn = get_db_connection()
    cursor_class = pymysql.cursors.DictCursor if dict_cursor else None
    cursor = conn.cursor(cursor_class)
    try:
        yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()
