"""
数据库连接管理
"""
import pymysql
from .settings import DB_CONFIG


def get_db_connection():
    """获取数据库连接"""
    return pymysql.connect(**DB_CONFIG)
