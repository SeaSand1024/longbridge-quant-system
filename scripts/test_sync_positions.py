#!/usr/bin/env python3
"""
测试长桥持仓同步功能
"""
import asyncio
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import TradingStrategy, longbridge_sdk, is_test_mode, get_db_connection
import pymysql
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_sync_positions():
    """测试持仓同步功能"""
    try:
        # 初始化长桥SDK
        await longbridge_sdk.connect()
        if not longbridge_sdk.is_connected:
            logger.error("长桥SDK连接失败")
            return

        # 检查是否是测试模式
        if is_test_mode():
            logger.warning("当前是测试模式，跳过持仓同步测试")
            logger.info("如需测试实盘同步，请先关闭测试模式")
            return

        # 创建交易策略实例
        trading_strategy = TradingStrategy()

        # 执行同步
        logger.info("开始同步长桥持仓...")
        await trading_strategy.sync_positions_from_longbridge()

        # 验证同步结果
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute("SELECT symbol, quantity, avg_cost FROM positions WHERE test_mode = 0 AND quantity > 0")
        positions = cursor.fetchall()
        cursor.close()
        conn.close()

        logger.info(f"同步完成，当前本地持仓: {len(positions)}只")
        for pos in positions:
            logger.info(f"  - {pos['symbol']}: 数量={pos['quantity']}, 成本=${pos['avg_cost']:.2f}")

    except Exception as e:
        logger.error(f"测试失败: {str(e)}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(test_sync_positions())
