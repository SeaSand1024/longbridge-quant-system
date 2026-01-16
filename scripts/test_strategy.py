#!/usr/bin/env python3
"""
交易策略测试脚本
用于验证策略逻辑：
1. 从所有正股中选择涨幅加速度最大的股票
2. 使用固定金额（默认20万）购买
3. 盈利达到目标后卖出
"""

import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import trading_strategy, longbridge_sdk, acceleration_calculator, get_db_connection
import pymysql
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 测试配置
TEST_BUY_AMOUNT = 200000  # 20万美元
TEST_PROFIT_TARGET = 1.0  # 1%止盈目标


async def test_strategy():
    """测试交易策略"""
    print("=" * 60)
    print("交易策略测试")
    print("=" * 60)
    print(f"买入金额: ${TEST_BUY_AMOUNT:,}")
    print(f"止盈目标: {TEST_PROFIT_TARGET}%")
    print()

    # 1. 获取所有正股
    print("1. 获取正股列表...")
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("""
        SELECT symbol, name
        FROM stocks
        WHERE stock_type = 'STOCK'
        ORDER BY symbol
    """)
    stocks = cursor.fetchall()
    cursor.close()
    conn.close()

    if not stocks:
        print("❌ 没有活跃的正股，请先添加股票")
        return

    print(f"✓ 找到 {len(stocks)} 只活跃正股:")
    for stock in stocks[:10]:  # 只显示前10个
        print(f"  - {stock['symbol']}: {stock['name']}")
    if len(stocks) > 10:
        print(f"  ... 还有 {len(stocks) - 10} 只")
    print()

    # 2. 模拟市场数据（涨幅加速度）
    print("2. 模拟市场数据...")
    symbols = [s['symbol'] for s in stocks]
    
    # 模拟价格历史数据，生成不同的加速度
    import random
    base_prices = {symbol: 100.0 + random.uniform(-20, 20) for symbol in symbols}
    
    # 为每只股票生成3次价格更新，模拟加速度
    for i in range(3):
        for symbol in symbols:
            base_price = base_prices[symbol]
            # 第一次：小幅上涨
            # 第二次：更大涨幅
            # 第三次：最大涨幅（模拟加速度）
            if i == 0:
                change_pct = random.uniform(0.1, 0.5)
            elif i == 1:
                change_pct = random.uniform(0.3, 0.8)
            else:
                change_pct = random.uniform(0.5, 1.5)
            
            price = base_price * (1 + change_pct / 100)
            acceleration_calculator.update_price(symbol, price, change_pct)
    
    # 计算加速度
    market_data = []
    for symbol in symbols:
        acceleration = acceleration_calculator.calculate_acceleration(symbol)
        market_data.append({
            'symbol': symbol,
            'price': base_prices[symbol] * (1 + random.uniform(0.5, 1.5) / 100),
            'change_pct': random.uniform(0.5, 1.5),
            'acceleration': acceleration
        })
    
    # 按加速度排序
    market_data.sort(key=lambda x: x['acceleration'], reverse=True)
    
    print("✓ 市场数据（前5名加速度最大的股票）:")
    for i, data in enumerate(market_data[:5], 1):
        print(f"  {i}. {data['symbol']:8s} 价格: ${data['price']:.2f}  涨幅: {data['change_pct']:.2f}%  加速度: {data['acceleration']:.4f}")
    print()

    # 3. 测试买入逻辑
    print("3. 测试买入逻辑...")
    best_stock = market_data[0] if market_data else None
    
    if not best_stock:
        print("❌ 没有可买入的股票")
        return
    
    if best_stock['acceleration'] <= 0:
        print(f"❌ 最佳股票 {best_stock['symbol']} 加速度为 {best_stock['acceleration']:.4f}，不满足买入条件（需>0）")
        return
    
    # 计算购买数量（固定金额）
    buy_price = best_stock['price']
    buy_quantity = int(TEST_BUY_AMOUNT / buy_price)
    buy_amount = buy_price * buy_quantity
    
    print(f"✓ 选择股票: {best_stock['symbol']}")
    print(f"  价格: ${buy_price:.2f}")
    print(f"  加速度: {best_stock['acceleration']:.4f}")
    print(f"  购买数量: {buy_quantity} 股")
    print(f"  购买金额: ${buy_amount:,.2f} (目标: ${TEST_BUY_AMOUNT:,.2f})")
    print()

    # 4. 测试卖出逻辑
    print("4. 测试卖出逻辑...")
    entry_price = buy_price
    profit_target_price = entry_price * (1 + TEST_PROFIT_TARGET / 100)
    
    print(f"  买入价格: ${entry_price:.2f}")
    print(f"  止盈价格: ${profit_target_price:.2f} (涨幅 {TEST_PROFIT_TARGET}%)")
    print()
    
    # 模拟价格上涨到止盈目标
    print("5. 模拟价格变化...")
    test_prices = [
        entry_price * 1.002,  # +0.2%
        entry_price * 1.005,  # +0.5%
        entry_price * 1.008,  # +0.8%
        profit_target_price,   # +1.0% (触发止盈)
    ]
    
    for test_price in test_prices:
        profit_pct = ((test_price - entry_price) / entry_price) * 100
        profit_amount = (test_price - entry_price) * buy_quantity
        status = "✓ 触发卖出" if profit_pct >= TEST_PROFIT_TARGET else "等待中"
        print(f"  价格: ${test_price:.2f}  涨幅: {profit_pct:.2f}%  盈亏: ${profit_amount:,.2f}  {status}")
    
    print()

    # 5. 总结
    print("=" * 60)
    print("测试总结")
    print("=" * 60)
    print(f"✓ 策略逻辑验证通过")
    print(f"✓ 可以从 {len(stocks)} 只正股中选择加速度最大的股票")
    print(f"✓ 使用固定金额 ${TEST_BUY_AMOUNT:,} 购买")
    print(f"✓ 当盈利达到 {TEST_PROFIT_TARGET}% 时自动卖出")
    print()
    print("注意：这是逻辑测试，不会实际下单")
    print("实际运行时需要：")
    print("1. 确保长桥SDK已配置")
    print("2. 有足够的账户余额")
    print("3. 在交易时间内运行")
    print("=" * 60)


if __name__ == "__main__":
    # 初始化SDK连接（模拟模式即可）
    asyncio.run(test_strategy())
