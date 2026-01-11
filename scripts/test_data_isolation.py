#!/usr/bin/env python3
"""
测试数据隔离功能：插入测试模式和真实环境的数据，验证隔离效果
"""

import pymysql
import os
from datetime import datetime, timedelta

# 数据库配置
DB_CONFIG = {
    'host': os.getenv('MYSQL_HOST', '127.0.0.1'),
    'port': int(os.getenv('MYSQL_PORT', 3306)),
    'user': os.getenv('MYSQL_USER', 'root'),
    'password': os.getenv('MYSQL_PASSWORD', '123456'),
    'database': os.getenv('MYSQL_DB', 'quant_system'),
    'charset': 'utf8mb4'
}


def insert_test_data():
    """插入测试数据"""
    try:
        # 连接数据库
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()

        print("开始插入测试数据...")

        # 清空现有测试数据（可选）
        cursor.execute("DELETE FROM trades WHERE test_mode = 1")
        cursor.execute("DELETE FROM positions WHERE test_mode = 1")

        # 插入测试模式交易数据
        test_trades = [
            ('AAPL', 'BUY', 150.00, 100, 15000.00, 0.001, 0),
            ('GOOGL', 'BUY', 2800.00, 10, 28000.00, 0.002, 0),
            ('MSFT', 'SELL', 300.00, 50, 15000.00, 0.001, 0),
        ]

        for trade in test_trades:
            cursor.execute("""
                INSERT INTO trades (symbol, action, price, quantity, amount, acceleration, test_mode)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, trade)

        # 插入测试模式持仓数据
        test_positions = [
            ('AAPL', 100, 150.00, 155.00, 500.00, 3.33, 0),
            ('GOOGL', 10, 2800.00, 2850.00, 500.00, 1.79, 0),
        ]

        for position in test_positions:
            cursor.execute("""
                INSERT INTO positions (symbol, quantity, avg_cost, current_price, profit_loss, profit_loss_pct, test_mode)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, position)

        # 插入真实环境数据（test_mode=1）
        real_trades = [
            ('TSLA', 'BUY', 200.00, 50, 10000.00, 0.001, 1),
            ('NVDA', 'BUY', 500.00, 20, 10000.00, 0.002, 1),
        ]

        for trade in real_trades:
            cursor.execute("""
                INSERT INTO trades (symbol, action, price, quantity, amount, acceleration, test_mode)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, trade)

        real_positions = [
            ('TSLA', 50, 200.00, 210.00, 500.00, 5.00, 1),
        ]

        for position in real_positions:
            cursor.execute("""
                INSERT INTO positions (symbol, quantity, avg_cost, current_price, profit_loss, profit_loss_pct, test_mode)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, position)

        # 提交更改
        conn.commit()
        print("✅ 测试数据插入成功！")

        # 验证数据隔离
        print("\n验证数据隔离效果：")

        # 查询测试模式数据
        cursor.execute("SELECT COUNT(*) FROM trades WHERE test_mode = 0")
        test_trades_count = cursor.fetchone()[0]
        print(f"   测试模式交易记录数: {test_trades_count}")

        cursor.execute("SELECT COUNT(*) FROM positions WHERE test_mode = 0")
        test_positions_count = cursor.fetchone()[0]
        print(f"   测试模式持仓记录数: {test_positions_count}")

        # 查询真实环境数据
        cursor.execute("SELECT COUNT(*) FROM trades WHERE test_mode = 1")
        real_trades_count = cursor.fetchone()[0]
        print(f"   真实环境交易记录数: {real_trades_count}")

        cursor.execute("SELECT COUNT(*) FROM positions WHERE test_mode = 1")
        real_positions_count = cursor.fetchone()[0]
        print(f"   真实环境持仓记录数: {real_positions_count}")

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"❌ 错误: {e}")


if __name__ == "__main__":
    insert_test_data()
