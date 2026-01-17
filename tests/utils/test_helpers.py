"""
测试辅助工具
"""
import os
import json
import asyncio
import subprocess
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime, timedelta


class TestHelpers:
    """测试辅助工具类"""
    
    @staticmethod
    def load_test_config() -> Dict[str, Any]:
        """加载测试配置"""
        config_file = Path("tests/fixtures/test_config.json")
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    @staticmethod
    def save_test_config(config: Dict[str, Any]):
        """保存测试配置"""
        config_file = Path("tests/fixtures/test_config.json")
        config_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    
    @staticmethod
    def is_server_running(host: str = "localhost", port: int = 8000) -> bool:
        """检查服务器是否运行"""
        import socket
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except:
            return False
    
    @staticmethod
    async def start_test_server(timeout: int = 30) -> bool:
        """启动测试服务器"""
        if TestHelpers.is_server_running():
            return True
        
        try:
            # 启动服务器进程
            process = await asyncio.create_subprocess_exec(
                "python", "main.py",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # 等待服务器启动
            for _ in range(timeout):
                if TestHelpers.is_server_running():
                    return True
                await asyncio.sleep(1)
            
            # 如果超时，终止进程
            process.terminate()
            await process.wait()
            return False
            
        except Exception as e:
            print(f"启动测试服务器失败: {e}")
            return False
    
    @staticmethod
    def get_project_root() -> Path:
        """获取项目根目录"""
        return Path(__file__).parent.parent.parent
    
    @staticmethod
    def get_test_data_dir() -> Path:
        """获取测试数据目录"""
        return TestHelpers.get_project_root() / "tests" / "fixtures" / "data"
    
    @staticmethod
    def ensure_test_dirs():
        """确保测试目录存在"""
        dirs = [
            "tests/fixtures/data",
            "tests/reports",
            "tests/logs",
            "htmlcov"
        ]
        
        for dir_path in dirs:
            Path(dir_path).mkdir(parents=True, exist_ok=True)
    
    @staticmethod
    def cleanup_test_files():
        """清理测试文件"""
        test_data_dir = TestHelpers.get_test_data_dir()
        
        # 清理测试数据文件
        for file_path in test_data_dir.glob("*.json"):
            if file_path.name.startswith("test_"):
                file_path.unlink()
        
        # 清理日志文件
        logs_dir = Path("tests/logs")
        for file_path in logs_dir.glob("*.log"):
            if file_path.stat().st_mtime < (datetime.now() - timedelta(days=7)).timestamp():
                file_path.unlink()
    
    @staticmethod
    def generate_test_report_summary(test_results: Dict[str, Any]) -> str:
        """生成测试报告摘要"""
        total_tests = test_results.get('total', 0)
        passed_tests = test_results.get('passed', 0)
        failed_tests = test_results.get('failed', 0)
        skipped_tests = test_results.get('skipped', 0)
        
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        summary = f"""
测试执行摘要
============
总测试数: {total_tests}
通过: {passed_tests}
失败: {failed_tests}
跳过: {skipped_tests}
成功率: {success_rate:.1f}%

执行时间: {test_results.get('duration', 'N/A')}
覆盖率: {test_results.get('coverage', 'N/A')}
        """
        
        return summary.strip()
    
    @staticmethod
    def validate_test_environment() -> List[str]:
        """验证测试环境"""
        issues = []
        
        # 检查Python版本
        import sys
        if sys.version_info < (3, 8):
            issues.append("Python版本过低，需要3.8+")
        
        # 检查必要的包
        required_packages = [
            'pytest', 'httpx', 'pymysql', 'selenium', 'factory_boy'
        ]
        
        for package in required_packages:
            try:
                __import__(package)
            except ImportError:
                issues.append(f"缺少必要的包: {package}")
        
        # 检查数据库连接
        try:
            from tests.test_config import TestConfig
            config = TestConfig()
            import pymysql
            conn = pymysql.connect(**config.db_config)
            conn.close()
        except Exception as e:
            issues.append(f"数据库连接失败: {e}")
        
        # 检查Chrome浏览器（用于Selenium测试）
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            options = Options()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            driver = webdriver.Chrome(options=options)
            driver.quit()
        except Exception as e:
            issues.append(f"Chrome浏览器不可用: {e}")
        
        return issues
    
    @staticmethod
    def setup_test_logging():
        """设置测试日志"""
        import logging
        
        # 创建日志目录
        log_dir = Path("tests/logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # 配置日志格式
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        
        # 文件日志
        file_handler = logging.FileHandler(
            log_dir / f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(log_format))
        
        # 控制台日志
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter(log_format))
        
        # 配置根日志器
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)
        
        return root_logger
    
    @staticmethod
    def measure_test_performance(func):
        """测试性能测量装饰器"""
        import time
        import functools
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                end_time = time.time()
                duration = end_time - start_time
                print(f"测试 {func.__name__} 执行时间: {duration:.3f}秒")
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                end_time = time.time()
                duration = end_time - start_time
                print(f"测试 {func.__name__} 执行时间: {duration:.3f}秒")
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    @staticmethod
    def create_test_snapshot(test_name: str, data: Dict[str, Any]):
        """创建测试快照"""
        snapshot_dir = Path("tests/fixtures/snapshots")
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        
        snapshot_file = snapshot_dir / f"{test_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(snapshot_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        
        return snapshot_file
    
    @staticmethod
    def compare_test_snapshots(snapshot1_path: Path, snapshot2_path: Path) -> Dict[str, Any]:
        """比较测试快照"""
        with open(snapshot1_path, 'r', encoding='utf-8') as f:
            data1 = json.load(f)
        
        with open(snapshot2_path, 'r', encoding='utf-8') as f:
            data2 = json.load(f)
        
        def deep_compare(obj1, obj2, path=""):
            differences = []
            
            if type(obj1) != type(obj2):
                differences.append(f"{path}: 类型不同 {type(obj1)} vs {type(obj2)}")
                return differences
            
            if isinstance(obj1, dict):
                all_keys = set(obj1.keys()) | set(obj2.keys())
                for key in all_keys:
                    new_path = f"{path}.{key}" if path else key
                    if key not in obj1:
                        differences.append(f"{new_path}: 仅在快照2中存在")
                    elif key not in obj2:
                        differences.append(f"{new_path}: 仅在快照1中存在")
                    else:
                        differences.extend(deep_compare(obj1[key], obj2[key], new_path))
            
            elif isinstance(obj1, list):
                if len(obj1) != len(obj2):
                    differences.append(f"{path}: 列表长度不同 {len(obj1)} vs {len(obj2)}")
                else:
                    for i, (item1, item2) in enumerate(zip(obj1, obj2)):
                        differences.extend(deep_compare(item1, item2, f"{path}[{i}]"))
            
            else:
                if obj1 != obj2:
                    differences.append(f"{path}: 值不同 {obj1} vs {obj2}")
            
            return differences
        
        differences = deep_compare(data1, data2)
        
        return {
            'identical': len(differences) == 0,
            'differences': differences,
            'snapshot1': snapshot1_path.name,
            'snapshot2': snapshot2_path.name
        }