"""
测试配置管理模块
"""
import os
import pymysql
import httpx
from typing import Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path
import json


@dataclass
class TestConfig:
    """测试配置类"""
    # 基础配置
    base_url: str = "http://localhost:8000"
    timeout: float = 30.0
    
    # 测试模式配置
    test_mode: bool = True
    enable_real_mode_tests: bool = False
    
    # 数据库配置
    db_host: str = "127.0.0.1"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = "123456"
    db_name: str = "quant_system_test"
    
    # 浏览器配置
    browser: str = "chrome"
    headless: bool = True
    window_size: tuple = (1920, 1080)
    
    # 测试数据配置
    test_data_dir: str = "tests/fixtures/data"
    cleanup_after_test: bool = True
    
    def __post_init__(self):
        """初始化后处理"""
        # 从环境变量覆盖配置
        self.base_url = os.getenv("TEST_BASE_URL", self.base_url)
        self.test_mode = os.getenv("TEST_MODE", "true").lower() == "true"
        self.enable_real_mode_tests = os.getenv("ENABLE_REAL_MODE_TESTS", "false").lower() == "true"
        
        # 数据库配置
        self.db_host = os.getenv("TEST_MYSQL_HOST", self.db_host)
        self.db_port = int(os.getenv("TEST_MYSQL_PORT", self.db_port))
        self.db_user = os.getenv("TEST_MYSQL_USER", self.db_user)
        self.db_password = os.getenv("TEST_MYSQL_PASSWORD", self.db_password)
        self.db_name = os.getenv("TEST_MYSQL_DB", self.db_name)
        
        # 浏览器配置
        self.browser = os.getenv("TEST_BROWSER", self.browser)
        self.headless = os.getenv("TEST_HEADLESS", "true").lower() == "true"
    
    @property
    def db_config(self) -> Dict[str, Any]:
        """获取数据库配置"""
        return {
            'host': self.db_host,
            'port': self.db_port,
            'user': self.db_user,
            'password': self.db_password,
            'database': self.db_name,
            'charset': 'utf8mb4'
        }
    
    def get_api_client(self) -> httpx.AsyncClient:
        """获取API客户端"""
        return httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout
        )
    
    def get_db_connection(self) -> pymysql.Connection:
        """获取数据库连接"""
        return pymysql.connect(**self.db_config)


class TestDataManager:
    """测试数据管理器"""
    
    def __init__(self, config: TestConfig):
        self.config = config
        self.data_dir = Path(config.test_data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    def load_test_data(self, filename: str) -> Dict[str, Any]:
        """加载测试数据"""
        file_path = self.data_dir / f"{filename}.json"
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def save_test_data(self, filename: str, data: Dict[str, Any]):
        """保存测试数据"""
        file_path = self.data_dir / f"{filename}.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def cleanup_test_data(self):
        """清理测试数据"""
        if self.config.cleanup_after_test:
            for file_path in self.data_dir.glob("*.json"):
                file_path.unlink()


class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self, config: TestConfig):
        self.config = config
    
    def setup_test_database(self):
        """设置测试数据库"""
        # 创建测试数据库
        temp_config = self.config.db_config.copy()
        temp_config.pop('database')
        
        conn = pymysql.connect(**temp_config)
        cursor = conn.cursor()
        
        try:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {self.config.db_name}")
            print(f"✅ 测试数据库 {self.config.db_name} 已准备就绪")
        except Exception as e:
            print(f"❌ 创建测试数据库失败: {e}")
        finally:
            cursor.close()
            conn.close()
    
    def init_test_tables(self):
        """初始化测试表结构"""
        conn = self.config.get_db_connection()
        cursor = conn.cursor()
        
        # 读取并执行SQL初始化脚本
        sql_file = Path("init_all_tables.sql")
        if sql_file.exists():
            with open(sql_file, 'r', encoding='utf-8') as f:
                sql_content = f.read()
            
            # 分割并执行SQL语句
            statements = sql_content.split(';')
            for statement in statements:
                statement = statement.strip()
                if statement:
                    try:
                        cursor.execute(statement)
                    except Exception as e:
                        print(f"执行SQL语句失败: {statement[:50]}... 错误: {e}")
            
            conn.commit()
            print("✅ 测试表结构初始化完成")
        else:
            print("❌ 未找到SQL初始化脚本")
        
        cursor.close()
        conn.close()
    
    def cleanup_test_data(self):
        """清理测试数据"""
        conn = self.config.get_db_connection()
        cursor = conn.cursor()
        
        # 清理所有测试数据
        tables = [
            'trades', 'positions', 'stocks', 'stock_predictions',
            'auto_trade_tasks', 'stock_kline_cache', 'user_config',
            'refresh_tokens', 'users', 'system_config'
        ]
        
        for table in tables:
            try:
                cursor.execute(f"DELETE FROM {table}")
            except pymysql.Error as e:
                print(f"清理表 {table} 失败: {e}")
        
        conn.commit()
        cursor.close()
        conn.close()


class TestEnvironment:
    """测试环境管理器"""
    
    def __init__(self):
        self.config = TestConfig()
        self.data_manager = TestDataManager(self.config)
        self.db_manager = DatabaseManager(self.config)
    
    def setup(self):
        """设置测试环境"""
        print("🚀 设置测试环境...")
        
        # 设置数据库
        self.db_manager.setup_test_database()
        self.db_manager.init_test_tables()
        
        # 创建测试数据目录
        self.data_manager.data_dir.mkdir(parents=True, exist_ok=True)
        
        print("✅ 测试环境设置完成")
    
    def teardown(self):
        """清理测试环境"""
        print("🧹 清理测试环境...")
        
        # 清理数据库
        self.db_manager.cleanup_test_data()
        
        # 清理测试数据文件
        self.data_manager.cleanup_test_data()
        
        print("✅ 测试环境清理完成")
    
    def switch_mode(self, test_mode: bool):
        """切换测试模式"""
        self.config.test_mode = test_mode
        mode_name = "测试模式" if test_mode else "真实模式"
        print(f"🔄 切换到{mode_name}")


# 全局测试环境实例
test_env = TestEnvironment()


def get_test_config() -> TestConfig:
    """获取测试配置"""
    return test_env.config


def get_test_environment() -> TestEnvironment:
    """获取测试环境"""
    return test_env