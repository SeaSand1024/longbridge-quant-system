#!/usr/bin/env python3
"""
确保数据库中有MAG7股票数据
通过API方式添加
"""
import requests
import sys

API_BASE = "http://localhost:8000"

MAG7_STOCKS = [
    ('AAPL', 'Apple Inc.'),
    ('MSFT', 'Microsoft Corporation'),
    ('GOOGL', 'Alphabet Inc.'),
    ('AMZN', 'Amazon.com Inc.'),
    ('NVDA', 'NVIDIA Corporation'),
    ('META', 'Meta Platforms Inc.'),
    ('TSLA', 'Tesla Inc.'),
]


def add_stock(symbol, name):
    """添加股票"""
    try:
        response = requests.post(
            f"{API_BASE}/api/stocks",
            json={"symbol": symbol, "name": name, "is_active": 1},
            timeout=5
        )
        result = response.json()

        if result.get("code") == 0:
            print(f"  ✓ {symbol} - {name}")
            return True
        else:
            print(f"  ✗ {symbol} - {name}: {result.get('message', 'Unknown error')}")
            return False
    except Exception as e:
        print(f"  ✗ {symbol} - {name}: {str(e)}")
        return False


def get_stocks():
    """获取股票列表"""
    try:
        response = requests.get(f"{API_BASE}/api/stocks", timeout=5)
        result = response.json()

        if result.get("code") == 0:
            return result.get("data", [])
        return []
    except Exception as e:
        print(f"获取股票列表失败: {e}")
        return []


def main():
    print("=" * 60)
    print("确保MAG7股票数据存在")
    print("=" * 60)

    # 获取现有股票
    print("\n检查现有股票...")
    existing = get_stocks()
    existing_symbols = {stock['symbol'] for stock in existing}

    if existing:
        print(f"  现有 {len(existing)} 只股票:")
        for stock in existing:
            status = "活跃" if stock['is_active'] else "停用"
            print(f"    - {stock['symbol']} ({stock['name']}) [{status}]")
    else:
        print("  数据库为空")

    # 添加缺失的股票
    print("\n添加MAG7股票...")
    added = 0
    for symbol, name in MAG7_STOCKS:
        if symbol not in existing_symbols:
            if add_stock(symbol, name):
                added += 1
        else:
            print(f"  - {symbol} 已存在，跳过")

    print("\n" + "=" * 60)
    if added > 0:
        print(f"✓ 成功添加 {added} 只新股票")
    else:
        print("✓ 所有MAG7股票已存在")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
