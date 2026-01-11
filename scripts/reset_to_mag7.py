#!/usr/bin/env python3
"""
重置股票为标准MAG7
"""
import pymysql
import sys

# 数据库配置
DB_CONFIG = {
    'host': '127.0.0.1',
    'port': 3306,
    'user': 'root',
    'password': '123456',
    'database': 'quant_system',
    'charset': 'utf8mb4'
}

# MAG7股票 (美股需加 .US 后缀)
MAG7_STOCKS = [
    ('AAPL.US', 'Apple Inc.', 'STOCK', 1),
    ('MSFT.US', 'Microsoft Corporation', 'STOCK', 1),
    ('GOOGL.US', 'Alphabet Inc. (Class C)', 'STOCK', 1),
    ('AMZN.US', 'Amazon.com Inc.', 'STOCK', 1),
    ('NVDA.US', 'NVIDIA Corporation', 'STOCK', 1),
    ('META.US', 'Meta Platforms Inc.', 'STOCK', 1),
    ('TSLA.US', 'Tesla Inc.', 'STOCK', 1),
]


def main():
    print("=" * 60)
    print("重置股票列表为标准MAG7")
    print("=" * 60)

    try:
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        # 查看当前股票数量
        cursor.execute("SELECT COUNT(*) as count FROM stocks")
        current_count = cursor.fetchone()['count']
        print(f"\n当前数据库中有 {current_count} 只股票")

        # 删除所有现有股票
        print("\n正在删除所有现有股票...")
        cursor.execute("DELETE FROM stocks")
        deleted_count = cursor.rowcount
        print(f"  已删除 {deleted_count} 只股票")

        # 清理相关数据
        print("\n正在清理交易记录和持仓...")
        cursor.execute("DELETE FROM trades")
        cursor.execute("DELETE FROM positions")
        print(f"  已清理交易记录和持仓")

        # 插入MAG7股票
        print("\n正在插入MAG7股票...")
        for symbol, name, stock_type, is_active in MAG7_STOCKS:
            cursor.execute("""
                INSERT INTO stocks (symbol, name, stock_type, is_active)
                VALUES (%s, %s, %s, %s)
            """, (symbol, name, stock_type, is_active))
            print(f"  ✓ {symbol} - {name}")

        conn.commit()

        # 显示结果
        cursor.execute("SELECT COUNT(*) as count FROM stocks")
        new_count = cursor.fetchone()['count']

        print("\n" + "=" * 60)
        print("✓ 重置完成")
        print(f"  股票数量: {current_count} → {new_count}")
        print("=" * 60)
        print("\nMAG7股票列表:")
        for symbol, name, stock_type, is_active in MAG7_STOCKS:
            status = "✓" if is_active else "✗"
            print(f"  {status} {symbol} - {name}")

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"\n✗ 错误: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
