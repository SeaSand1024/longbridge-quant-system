#!/usr/bin/env python3
"""
删除数据库中的模拟数据
"""
import pymysql

# 数据库配置
DB_CONFIG = {
    'host': '127.0.0.1',
    'port': 3306,
    'user': 'root',
    'password': '123456',
    'database': 'quant_system',
    'charset': 'utf8mb4'
}

def main():
    print("=" * 60)
    print("删除数据库中的模拟数据")
    print("=" * 60)

    try:
        # 连接数据库
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # 删除MAG7股票
        mag7_symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA']
        placeholders = ', '.join(['%s'] * len(mag7_symbols))
        cursor.execute(f"DELETE FROM stocks WHERE symbol IN ({placeholders})", mag7_symbols)
        deleted_stocks = cursor.rowcount
        print(f"✓ 删除股票数据: {deleted_stocks} 条")

        # 删除所有持仓
        cursor.execute("DELETE FROM positions")
        deleted_positions = cursor.rowcount
        print(f"✓ 删除持仓数据: {deleted_positions} 条")

        # 删除所有交易记录
        cursor.execute("DELETE FROM trades")
        deleted_trades = cursor.rowcount
        print(f"✓ 删除交易记录: {deleted_trades} 条")

        # 提交更改
        conn.commit()

        print("\n" + "=" * 60)
        print("✓ 模拟数据删除完成")
        print("=" * 60)

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"\n✗ 错误: {e}")

if __name__ == "__main__":
    main()
