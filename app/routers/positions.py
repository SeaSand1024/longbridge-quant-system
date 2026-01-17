"""
持仓路由
"""
import logging
from datetime import datetime
from fastapi import APIRouter, Depends
import pymysql

from app.config.database import get_db_connection
from app.auth.utils import get_current_user, is_test_mode
from app.services.longbridge_sdk import longbridge_sdk

logger = logging.getLogger(__name__)

router = APIRouter(tags=["持仓"])


@router.get("/api/positions")
async def get_positions(current_user: dict = Depends(get_current_user)):
    """获取持仓信息"""
    if is_test_mode():
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        try:
            cursor.execute(
                "SELECT * FROM positions WHERE quantity > 0 AND test_mode = 1"
            )
            positions = cursor.fetchall()
            # 为每个持仓计算盈亏
            for pos in positions:
                cost = float(pos.get('cost') or 0)
                current_price = float(pos.get('current_price') or pos.get('buy_price') or 0)
                quantity = pos.get('quantity') or 0
                market_value = current_price * quantity
                
                pos['market_value'] = market_value
                pos['profit_loss'] = market_value - cost if cost > 0 else 0
                pos['profit_loss_pct'] = ((market_value - cost) / cost * 100) if cost > 0 else 0
            
            return {"code": 0, "data": positions}
        finally:
            cursor.close()
            conn.close()
    else:
        # 真实模式：从SDK获取真实持仓
        lb_positions = await longbridge_sdk.get_stock_positions()
        
        if not lb_positions:
            return {"code": 0, "data": []}
        
        # 获取实时行情更新价格
        symbols = [p['symbol'] for p in lb_positions]
        quotes = await longbridge_sdk.get_realtime_quote(symbols)
        quotes_map = {q['symbol']: q for q in quotes}
        
        positions = []
        for p in lb_positions:
            symbol = p['symbol']
            quote = quotes_map.get(symbol, {})
            current_price = quote.get('price', p.get('cost_price', 0))
            
            quantity = p['quantity']
            cost_price = p['cost_price']
            market_value = current_price * quantity
            cost = cost_price * quantity
            
            # 计算盈亏
            profit_loss = market_value - cost if cost > 0 else 0
            profit_loss_pct = ((market_value - cost) / cost * 100) if cost > 0 else 0
            
            positions.append({
                'symbol': symbol,
                'quantity': quantity,
                'buy_price': cost_price,
                'current_price': current_price,
                'market_value': market_value,
                'cost': cost,
                'profit_loss': profit_loss,
                'profit_loss_pct': profit_loss_pct,
                'test_mode': 0
            })
        return {"code": 0, "data": positions}



@router.get("/api/portfolio")
async def get_portfolio(current_user: dict = Depends(get_current_user)):
    """获取账户总览"""
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    try:
        test_mode = 1 if is_test_mode() else 0
        
        # 获取今日交易统计
        today_trades = {"count": 0, "buy_count": 0, "sell_count": 0, "volume": 0}
        
        if is_test_mode():
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN action = 'BUY' THEN 1 ELSE 0 END) as buy_count,
                    SUM(CASE WHEN action = 'SELL' THEN 1 ELSE 0 END) as sell_count,
                    SUM(amount) as total_volume
                FROM trades 
                WHERE DATE(trade_time) = CURDATE() AND test_mode = 1
            """)
            today_stats = cursor.fetchone()
            if today_stats:
                today_trades = {
                    "count": today_stats.get('total_trades', 0) or 0,
                    "buy_count": today_stats.get('buy_count', 0) or 0,
                    "sell_count": today_stats.get('sell_count', 0) or 0,
                    "volume": float(today_stats.get('total_volume', 0) or 0)
                }
        else:
            # 真实模式：从SDK获取今日订单统计
            try:
                orders = await longbridge_sdk.get_history_orders(days=1) # 获取最近1天的订单
                today_str = datetime.now().strftime('%Y-%m-%d')
                
                for order in orders:
                    # 检查订单日期是否是今天 (ISO格式 2026-01-17T...)
                    if order['updated_at'].startswith(today_str) and order['status'] == 'Filled':
                        today_trades['count'] += 1
                        if order['side'] == 'Buy':
                            today_trades['buy_count'] += 1
                        else:
                            today_trades['sell_count'] += 1
                        today_trades['volume'] += order['executed_price'] * order['executed_quantity']
            except Exception as e:
                logger.error(f"获取今日交易统计失败: {str(e)}")
        
        # 获取账户余额
        balance = await longbridge_sdk.get_account_balance()
        available_cash = balance.get('available_cash', 0)
        net_assets = balance.get('net_assets', 0)
        currency = balance.get('currency', 'USD')
        
        positions = []
        total_market_value = 0
        total_cost = 0

        if is_test_mode():
            # 测试模式：从本地数据库获取持仓
            cursor.execute(
                "SELECT * FROM positions WHERE quantity > 0 AND test_mode = 1"
            )
            positions = cursor.fetchall()
            
            for pos in positions:
                cost_val = pos.get('cost')
                total_cost += float(cost_val) if cost_val is not None else 0
                
                current_price = pos.get('current_price')
                if current_price is None:
                    current_price = pos.get('buy_price')
                current_price = float(current_price) if current_price is not None else 0
                
                quantity = pos.get('quantity') or 0
                total_market_value += current_price * quantity
        else:
            # 真实模式：直接从长桥SDK获取真实持仓
            lb_positions = await longbridge_sdk.get_stock_positions()
            
            # 获取这些持仓的实时行情以更新价格
            symbols = [p['symbol'] for p in lb_positions]
            quotes = await longbridge_sdk.get_realtime_quote(symbols)
            quotes_map = {q['symbol']: q for q in quotes}
            
            for p in lb_positions:
                symbol = p['symbol']
                quote = quotes_map.get(symbol, {})
                current_price = quote.get('price', p.get('cost_price', 0))
                
                quantity = p['quantity']
                cost_price = p['cost_price']
                market_value = current_price * quantity
                cost_total = cost_price * quantity
                
                total_market_value += market_value
                total_cost += cost_total
                
                positions.append({
                    'symbol': symbol,
                    'quantity': quantity,
                    'buy_price': cost_price,
                    'current_price': current_price,
                    'market_value': market_value,
                    'cost': cost_total,
                    'profit_loss': market_value - cost_total if cost_total > 0 else 0,
                    'profit_loss_pct': ((market_value - cost_total) / cost_total * 100) if cost_total > 0 else 0,
                    'test_mode': 0
                })
        # 计算盈亏
        # 真实模式下，优先使用 SDK 返回的 net_assets
        if not is_test_mode() and net_assets > 0:
            total_assets = net_assets
        else:
            total_assets = available_cash + total_market_value
            
        position_profit_loss = total_market_value - total_cost if total_cost > 0 else 0
        position_profit_loss_pct = (position_profit_loss / total_cost * 100) if total_cost > 0 else 0
        
        # 构造多币种数据
        multi_currency = {
            "USD": {"total_assets": 0},
            "CNY": {"total_assets": 0},
            "HKD": {"total_assets": 0}
        }
        if currency in multi_currency:
            multi_currency[currency]["total_assets"] = total_assets
        else:
            multi_currency["USD"]["total_assets"] = total_assets

        return {
            "code": 0,
            "data": {
                "total_assets": total_assets,
                "available_cash": available_cash,
                "position_market_value": total_market_value,
                "total_cost": total_cost,
                "position_profit_loss": position_profit_loss,
                "position_profit_loss_pct": position_profit_loss_pct,
                "daily_profit_loss": 0,  
                "daily_profit_loss_pct": 0,
                "positions": positions,
                "today_trades": today_trades,
                "is_test_mode": is_test_mode(),
                "currency": currency,
                "multi_currency": multi_currency
            }
        }
    finally:
        cursor.close()
        conn.close()
