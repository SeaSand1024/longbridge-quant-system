#!/usr/bin/env python3
"""
真实下单测试脚本
用于验证长桥SDK是否能够真实下单
"""
import asyncio
import os
import sys
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from longbridge.openapi import Config, QuoteContext, TradeContext, OrderSide, OrderType, TimeInForceType
except ImportError:
    print("错误: 长桥SDK未安装")
    print("请运行: pip install longbridge-openapi")
    sys.exit(1)


async def test_real_order():
    """测试真实下单"""

    # 从环境变量获取配置
    app_key = os.getenv('LONGBRIDGE_APP_KEY')
    app_secret = os.getenv('LONGBRIDGE_APP_SECRET')
    access_token = os.getenv('LONGBRIDGE_ACCESS_TOKEN')

    if not all([app_key, app_secret, access_token]):
        print("=" * 60)
        print("错误: 长桥SDK配置不完整")
        print("=" * 60)
        print("请设置以下环境变量:")
        print("  - LONGBRIDGE_APP_KEY")
        print("  - LONGBRIDGE_APP_SECRET")
        print("  - LONGBRIDGE_ACCESS_TOKEN")
        print("=" * 60)
        sys.exit(1)

    print("=" * 60)
    print("真实下单测试")
    print("=" * 60)
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"股票代码: NVDA")
    print(f"操作方向: 买入")
    print(f"下单数量: 100股")
    print("=" * 60)
    print()

    try:
        # 1. 创建长桥配置
        print("[1/5] 正在创建长桥配置...")
        config = Config(
            app_key=app_key,
            app_secret=app_secret,
            access_token=access_token,
            http_url=os.getenv('LONGBRIDGE_HTTP_URL', 'https://openapi.longbridgeapp.com'),
            quote_ws_url=os.getenv('LONGBRIDGE_QUOTE_WS_URL', 'wss://openapi-quote.longbridgeapp.com'),
            trade_ws_url=os.getenv('LONGBRIDGE_TRADE_WS_URL', 'wss://openapi-trade.longbridgeapp.com')
        )
        print("      ✓ 配置创建成功")
        print()

        # 2. 连接长桥SDK
        print("[2/5] 正在连接长桥SDK...")
        quote_ctx = QuoteContext(config)
        trade_ctx = TradeContext(config)
        print("      ✓ SDK连接成功")
        print()

        # 3. 获取NVDA当前价格
        print("[3/5] 正在获取NVDA实时行情...")
        symbol = "NVDA.US"  # 美股需要加 .US 后缀
        try:
            quotes = quote_ctx.quote([symbol])
            if quotes and len(quotes) > 0:
                quote = quotes[0]
                current_price = float(quote.last_done) if hasattr(quote, 'last_done') else None
                # 计算涨跌幅
                if current_price and hasattr(quote, 'prev_close') and quote.prev_close:
                    change_pct = ((current_price - float(quote.prev_close)) / float(quote.prev_close)) * 100
                else:
                    change_pct = 0.0
                print(f"      当前价格: ${current_price:.2f}")
                print(f"      涨跌幅: {change_pct:.2f}%")
                print(f"      成交量: {quote.volume:,}")
            else:
                print("      ⚠ 无法获取实时价格,使用参考价格")
                current_price = None
        except Exception as e:
            print(f"      ⚠ 获取价格失败: {str(e)}")
            current_price = None
        print()

        # 4. 获取账户余额
        print("[4/5] 正在获取账户信息...")
        try:
            account = trade_ctx.account_balance()
            if account and len(account) > 0:
                acc = account[0]
                total_assets = float(getattr(acc, 'total_assets', acc.net_assets))
                total_cash = float(getattr(acc, 'total_cash', 0))
                currency = acc.currency

                print(f"      账户总资产: {total_assets:,.2f} {currency}")
                print(f"      可用资金: {total_cash:,.2f} {currency}")
            else:
                print("      ⚠ 无法获取账户信息")
        except Exception as e:
            print(f"      ⚠ 获取账户信息失败: {str(e)}")
        print()

        # 5. 确认并下单
        print("[5/5] 准备下单...")
        print("=" * 60)
        print("下单详情:")
        print(f"  股票代码: {symbol} (英伟达)")
        print(f"  操作: 买入 (BUY)")
        print(f"  数量: 100 股")

        # 如果获取到当前价格,使用当前价格作为限价
        if current_price:
            limit_price = current_price
        else:
            limit_price = 150.00  # 默认限价

        print(f"  限价: ${limit_price:.2f}")
        print(f"  预计金额: ${limit_price * 100:.2f}")
        print("=" * 60)
        print()

        # 二次确认
        print("⚠️  警告: 即将执行真实交易!")
        print("    这将从您的账户扣除真实资金!")
        print()
        confirm = input("确认下单? (输入 YES 确认): ")

        if confirm != "YES":
            print()
            print("=" * 60)
            print("下单已取消")
            print("=" * 60)
            return

        print()
        print("正在提交订单...")

        # 提交限价单
        order = trade_ctx.submit_order(
            symbol=symbol,
            order_type=OrderType.LO,
            side=OrderSide.Buy,
            submitted_quantity=100,
            submitted_price=limit_price,
            time_in_force=TimeInForceType.Day
        )

        print()
        print("=" * 60)
        print("✓ 下单成功!")
        print("=" * 60)
        print(f"订单号: {order.order_id}")
        print(f"股票代码: {symbol}")
        print(f"操作类型: 买入")
        print(f"订单数量: 100 股")
        print(f"订单价格: ${limit_price:.2f}")
        print(f"订单类型: 限价单")
        print(f"有效期: 当日有效")
        print("=" * 60)
        print()
        print("请登录长桥证券App查看订单状态")

    except Exception as e:
        print()
        print("=" * 60)
        print("✗ 下单失败")
        print("=" * 60)
        print(f"错误信息: {str(e)}")
        print()
        print("可能的原因:")
        print("  1. 账户余额不足")
        print("  2. 市场未开市")
        print("  3. 股票代码错误")
        print("  4. API权限不足")
        print("  5. 网络连接问题")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(test_real_order())
    except KeyboardInterrupt:
        print()
        print("\n用户中断操作")
        sys.exit(0)
