"""
测试数据库管理器
"""
import pymysql
import subprocess
import os
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime


class TestDatabaseManager:
    """测试数据库管理器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.db_name = config['database']
        self.connection = None
    
    def create_test_database(self):
        """创建测试数据库"""
        # 连接到MySQL服务器（不指定数据库）
        temp_config = self.config.copy()
        temp_config.pop('database')
        
        conn = pymysql.connect(**temp_config)
        cursor = conn.cursor()
        
        try:
            # 删除现有测试数据库（如果存在）
            cursor.execute(f"DROP DATABASE IF EXISTS {self.db_name}")
            
            # 创建新的测试数据库
            cursor.execute(f"CREATE DATABASE {self.db_name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            
            print(f"✅ 测试数据库 {self.db_name} 创建成功")
            
        except Exception as e:
            print(f"❌ 创建测试数据库失败: {e}")
            raise
        finally:
            cursor.close()
            conn.close()
    
    def init_database_schema(self):
        """初始化数据库结构"""
        sql_file = Path("init_all_tables.sql")
        
        if not sql_file.exists():
            raise FileNotFoundError("未找到数据库初始化脚本 init_all_tables.sql")
        
        # 连接到测试数据库
        conn = pymysql.connect(**self.config)
        cursor = conn.cursor()
        
        try:
            # 读取SQL文件
            with open(sql_file, 'r', encoding='utf-8') as f:
                sql_content = f.read()
            
            # 分割SQL语句并执行
            statements = self._split_sql_statements(sql_content)
            
            for statement in statements:
                if statement.strip():
                    try:
                        cursor.execute(statement)
                    except Exception as e:
                        print(f"执行SQL语句失败: {statement[:100]}...")
                        print(f"错误: {e}")
                        # 继续执行其他语句
            
            conn.commit()
            print(f"✅ 数据库结构初始化完成")
            
        except Exception as e:
            print(f"❌ 初始化数据库结构失败: {e}")
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()
    
    def _split_sql_statements(self, sql_content: str) -> List[str]:
        """分割SQL语句"""
        # 简单的SQL语句分割，处理分号分隔的语句
        statements = []
        current_statement = ""
        in_string = False
        string_char = None
        
        for char in sql_content:
            if char in ('"', "'") and not in_string:
                in_string = True
                string_char = char
            elif char == string_char and in_string:
                in_string = False
                string_char = None
            elif char == ';' and not in_string:
                if current_statement.strip():
                    statements.append(current_statement.strip())
                current_statement = ""
                continue
            
            current_statement += char
        
        # 添加最后一个语句
        if current_statement.strip():
            statements.append(current_statement.strip())
        
        return statements
    
    def backup_database(self, backup_name: Optional[str] = None) -> str:
        """备份数据库"""
        if not backup_name:
            backup_name = f"test_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        backup_dir = Path("tests/fixtures/backups")
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        backup_file = backup_dir / f"{backup_name}.sql"
        
        # 使用mysqldump备份
        cmd = [
            "mysqldump",
            f"--host={self.config['host']}",
            f"--port={self.config['port']}",
            f"--user={self.config['user']}",
            f"--password={self.config['password']}",
            "--single-transaction",
            "--routines",
            "--triggers",
            self.db_name
        ]
        
        try:
            with open(backup_file, 'w') as f:
                subprocess.run(cmd, stdout=f, check=True)
            
            print(f"✅ 数据库备份完成: {backup_file}")
            return str(backup_file)
            
        except subprocess.CalledProcessError as e:
            print(f"❌ 数据库备份失败: {e}")
            raise
    
    def restore_database(self, backup_file: str):
        """恢复数据库"""
        backup_path = Path(backup_file)
        
        if not backup_path.exists():
            raise FileNotFoundError(f"备份文件不存在: {backup_file}")
        
        # 先重新创建数据库
        self.create_test_database()
        
        # 使用mysql命令恢复
        cmd = [
            "mysql",
            f"--host={self.config['host']}",
            f"--port={self.config['port']}",
            f"--user={self.config['user']}",
            f"--password={self.config['password']}",
            self.db_name
        ]
        
        try:
            with open(backup_path, 'r') as f:
                subprocess.run(cmd, stdin=f, check=True)
            
            print(f"✅ 数据库恢复完成: {backup_file}")
            
        except subprocess.CalledProcessError as e:
            print(f"❌ 数据库恢复失败: {e}")
            raise
    
    def clear_all_data(self):
        """清空所有数据"""
        conn = pymysql.connect(**self.config)
        cursor = conn.cursor()
        
        try:
            # 禁用外键检查
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
            
            # 获取所有表名
            cursor.execute("SHOW TABLES")
            tables = [row[0] for row in cursor.fetchall()]
            
            # 清空所有表
            for table in tables:
                cursor.execute(f"TRUNCATE TABLE {table}")
            
            # 重新启用外键检查
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
            
            conn.commit()
            print(f"✅ 清空所有数据完成，共清理 {len(tables)} 个表")
            
        except Exception as e:
            print(f"❌ 清空数据失败: {e}")
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()
    
    def get_table_stats(self) -> Dict[str, int]:
        """获取表统计信息"""
        conn = pymysql.connect(**self.config)
        cursor = conn.cursor()
        
        stats = {}
        
        try:
            # 获取所有表名
            cursor.execute("SHOW TABLES")
            tables = [row[0] for row in cursor.fetchall()]
            
            # 统计每个表的记录数
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                stats[table] = count
            
        except Exception as e:
            print(f"❌ 获取表统计信息失败: {e}")
        finally:
            cursor.close()
            conn.close()
        
        return stats
    
    def validate_data_integrity(self) -> List[str]:
        """验证数据完整性"""
        issues = []
        conn = pymysql.connect(**self.config)
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        try:
            # 检查用户表
            cursor.execute("SELECT COUNT(*) as count FROM users WHERE username IS NULL OR username = ''")
            if cursor.fetchone()['count'] > 0:
                issues.append("用户表存在空用户名")
            
            # 检查股票表
            cursor.execute("SELECT COUNT(*) as count FROM stocks WHERE symbol IS NULL OR symbol = ''")
            if cursor.fetchone()['count'] > 0:
                issues.append("股票表存在空股票代码")
            
            # 检查交易记录
            cursor.execute("SELECT COUNT(*) as count FROM trades WHERE symbol IS NULL OR price <= 0 OR quantity <= 0")
            if cursor.fetchone()['count'] > 0:
                issues.append("交易记录存在无效数据")
            
            # 检查持仓记录
            cursor.execute("SELECT COUNT(*) as count FROM positions WHERE symbol IS NULL OR quantity < 0")
            if cursor.fetchone()['count'] > 0:
                issues.append("持仓记录存在无效数据")
            
            # 检查数据隔离
            cursor.execute("SELECT DISTINCT test_mode FROM trades")
            trade_modes = [row['test_mode'] for row in cursor.fetchall()]
            
            cursor.execute("SELECT DISTINCT test_mode FROM positions")
            position_modes = [row['test_mode'] for row in cursor.fetchall()]
            
            if len(set(trade_modes) - {0, 1}) > 0:
                issues.append("交易记录存在无效的test_mode值")
            
            if len(set(position_modes) - {0, 1}) > 0:
                issues.append("持仓记录存在无效的test_mode值")
            
        except Exception as e:
            issues.append(f"数据完整性检查失败: {e}")
        finally:
            cursor.close()
            conn.close()
        
        return issues
    
    def setup_test_environment(self):
        """设置完整的测试环境"""
        print("🚀 设置测试数据库环境...")
        
        try:
            # 1. 创建测试数据库
            self.create_test_database()
            
            # 2. 初始化数据库结构
            self.init_database_schema()
            
            # 3. 验证数据完整性
            issues = self.validate_data_integrity()
            if issues:
                print("⚠️  发现数据完整性问题:")
                for issue in issues:
                    print(f"   - {issue}")
            
            # 4. 获取表统计
            stats = self.get_table_stats()
            print(f"📊 数据库表统计: {len(stats)} 个表已创建")
            
            print("✅ 测试数据库环境设置完成")
            
        except Exception as e:
            print(f"❌ 设置测试数据库环境失败: {e}")
            raise
    
    def teardown_test_environment(self):
        """清理测试环境"""
        print("🧹 清理测试数据库环境...")
        
        try:
            # 删除测试数据库
            temp_config = self.config.copy()
            temp_config.pop('database')
            
            conn = pymysql.connect(**temp_config)
            cursor = conn.cursor()
            
            cursor.execute(f"DROP DATABASE IF EXISTS {self.db_name}")
            
            cursor.close()
            conn.close()
            
            print("✅ 测试数据库环境清理完成")
            
        except Exception as e:
            print(f"❌ 清理测试数据库环境失败: {e}")
            # 不抛出异常，避免影响测试结果