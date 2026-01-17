#!/usr/bin/env python3
"""
为现有数据库表添加test_mode字段
"""

import pymysql
import os

# 数据库配置
DB_CONFIG = {
    'host': os.getenv('MYSQL_HOST', '127.0.0.1'),
    'port': int(os.getenv('MYSQL_PORT', 3306)),
    'user': os.getenv('MYSQL_USER', 'root'),
    'password': os.getenv('MYSQL_PASSWORD', '123456'),
    'database': os.getenv('MYSQL_DB', 'quant_system'),
    'charset': 'utf8mb4'
}

def add_test_mode_fields():
    """为现有表添加test_mode字段"""
    try:
        # 连接数据库
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        print("开始为数据库表添加test_mode字段...")
        
        # 为trades表添加test_mode字段
        print("1. 为trades表添加test_mode字段...")
        cursor.execute("""
            ALTER TABLE trades 
            ADD COLUMN test_mode TINYINT DEFAULT 0 COMMENT '0=真实环境, 1=测试模式'
        """)
        print("   ✓ trades表字段添加成功")
        
        # 为positions表添加test_mode字段
        print("2. 为positions表添加test_mode字段...")
        cursor.execute("""
            ALTER TABLE positions 
            ADD COLUMN test_mode TINYINT DEFAULT 0 COMMENT '0=真实环境, 1=测试模式'
        """)
        print("   ✓ positions表字段添加成功")
        
        # 提交更改
        conn.commit()
        print("\n✅ 所有表字段添加成功！")
        
        # 验证字段是否添加成功
        print("\n验证字段添加情况：")
        cursor.execute("DESCRIBE trades")
        trades_columns = [col[0] for col in cursor.fetchall()]
        print(f"   trades表字段: {trades_columns}")
        
        cursor.execute("DESCRIBE positions")
        positions_columns = [col[0] for col in cursor.fetchall()]
        print(f"   positions表字段: {positions_columns}")
        
        cursor.close()
        conn.close()
        
    except pymysql.Error as e:
        if "Duplicate column name" in str(e):
            print("⚠️  字段已存在，无需重复添加")
        else:
            print(f"❌ 数据库错误: {e}")
    except Exception as e:
        print(f"❌ 错误: {e}")

if __name__ == "__main__":
    add_test_mode_fields()