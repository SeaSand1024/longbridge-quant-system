"""
pytest配置文件和全局fixtures
"""
import pytest
import asyncio
import pymysql
import httpx
from typing import AsyncGenerator, Generator
import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.config.database import get_db_connection
from app.config import settings as app_settings


@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环用于异步测试"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def settings():
    """获取应用设置"""
    return {
        'db_config': app_settings.DB_CONFIG,
        'longbridge_config': app_settings.LONGBRIDGE_CONFIG,
        'llm_config': app_settings.LLM_CONFIG,
        'secret_key': app_settings.SECRET_KEY,
        'algorithm': app_settings.ALGORITHM,
    }


@pytest.fixture(scope="session")
def test_db_config():
    """测试数据库配置"""
    return {
        'host': os.getenv('TEST_MYSQL_HOST', '127.0.0.1'),
        'port': int(os.getenv('TEST_MYSQL_PORT', 3306)),
        'user': os.getenv('TEST_MYSQL_USER', 'root'),
        'password': os.getenv('TEST_MYSQL_PASSWORD', '123456'),
        'database': os.getenv('TEST_MYSQL_DB', 'quant_system_test'),
        'charset': 'utf8mb4'
    }


@pytest.fixture(scope="session")
def db_connection(test_db_config):
    """数据库连接fixture"""
    # 创建测试数据库（如果不存在）
    temp_config = test_db_config.copy()
    temp_config.pop('database')
    
    conn = pymysql.connect(**temp_config)
    cursor = conn.cursor()
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {test_db_config['database']}")
    cursor.close()
    conn.close()
    
    # 连接到测试数据库
    conn = pymysql.connect(**test_db_config)
    yield conn
    conn.close()


@pytest.fixture(scope="function")
def clean_db(db_connection):
    """清理数据库fixture - 每个测试前后清理"""
    cursor = db_connection.cursor()
    
    # 测试前清理
    tables = [
        'trades', 'positions', 'stocks', 'stock_predictions',
        'auto_trade_tasks', 'stock_kline_cache', 'user_config',
        'refresh_tokens', 'users', 'system_config'
    ]
    
    for table in tables:
        try:
            cursor.execute(f"DELETE FROM {table}")
        except pymysql.Error:
            # 表可能不存在，忽略错误
            pass
    
    db_connection.commit()
    
    yield
    
    # 测试后清理
    for table in tables:
        try:
            cursor.execute(f"DELETE FROM {table}")
        except pymysql.Error:
            pass
    
    db_connection.commit()


@pytest.fixture(scope="function")
async def api_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """API客户端fixture"""
    async with httpx.AsyncClient(
        base_url="http://localhost:8000",
        timeout=30.0
    ) as client:
        yield client


@pytest.fixture(scope="function")
def test_user_data():
    """测试用户数据"""
    return {
        "username": "test_user",
        "email": "test@example.com",
        "password": "test_password_123"
    }


@pytest.fixture(scope="function")
def test_stock_data():
    """测试股票数据"""
    return [
        {
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "stock_type": "STOCK",
            "group_name": "Tech",
            "is_active": True
        },
        {
            "symbol": "GOOGL",
            "name": "Alphabet Inc.",
            "stock_type": "STOCK", 
            "group_name": "Tech",
            "is_active": True
        },
        {
            "symbol": "TSLA",
            "name": "Tesla Inc.",
            "stock_type": "STOCK",
            "group_name": "Auto",
            "is_active": True
        }
    ]


@pytest.fixture(scope="function")
def test_trade_data():
    """测试交易数据"""
    return [
        {
            "symbol": "AAPL",
            "action": "BUY",
            "price": 150.00,
            "quantity": 100,
            "amount": 15000.00,
            "acceleration": 0.001,
            "test_mode": 0  # 测试模式
        },
        {
            "symbol": "GOOGL", 
            "action": "BUY",
            "price": 2800.00,
            "quantity": 10,
            "amount": 28000.00,
            "acceleration": 0.002,
            "test_mode": 0
        }
    ]


@pytest.fixture(scope="function")
def authenticated_headers(api_client, test_user_data):
    """认证头部fixture"""
    # 这个fixture需要在具体测试中实现登录逻辑
    # 返回包含认证信息的headers
    return {"Authorization": "Bearer test_token"}


# 测试模式标记
def pytest_configure(config):
    """pytest配置"""
    # 创建报告目录
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)
    
    # 创建覆盖率报告目录
    htmlcov_dir = Path("htmlcov")
    htmlcov_dir.mkdir(exist_ok=True)


def pytest_collection_modifyitems(config, items):
    """修改测试收集项"""
    # 为没有标记的测试添加默认标记
    for item in items:
        if not any(item.iter_markers()):
            item.add_marker(pytest.mark.unit)


# 跳过条件
def pytest_runtest_setup(item):
    """测试运行前的设置"""
    # 检查是否需要跳过真实模式测试
    if item.get_closest_marker("real_mode"):
        if not os.getenv("ENABLE_REAL_MODE_TESTS"):
            pytest.skip("真实模式测试被禁用，设置 ENABLE_REAL_MODE_TESTS=1 启用")