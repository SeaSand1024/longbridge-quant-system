"""
市场数据路由
"""
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
import pymysql
import asyncio
import json

from app.config.database import get_db_connection
from app.auth.utils import get_current_user, is_test_mode
from app.services.longbridge_sdk import longbridge_sdk
from app.services.acceleration import acceleration_calculator
from app.services.sse import sse_clients

router = APIRouter(tags=["市场数据"])


@router.get("/api/market-data")
async def get_market_data(current_user: dict = Depends(get_current_user)):
    """获取实时市场数据（按分组）"""
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    try:
        # 获取自选股/股票池
        cursor.execute("""
            SELECT symbol, name, stock_type, group_name, group_order 
            FROM stocks WHERE is_active = 1 
            ORDER BY group_order ASC, id DESC
        """)
        stocks = cursor.fetchall()
        
        if not stocks and not is_test_mode():
            # 真实模式：如果本地股票池为空，尝试从长桥自选股同步
            lb_watchlist = await longbridge_sdk.get_watchlist()
            if lb_watchlist:
                for item in lb_watchlist:
                    try:
                        cursor.execute("""
                            INSERT IGNORE INTO stocks (symbol, name, group_name)
                            VALUES (%s, %s, %s)
                        """, (item['symbol'], item['name'], item['group']))
                    except Exception:
                        pass
                conn.commit()
                # 重新查询
                cursor.execute("""
                    SELECT symbol, name, stock_type, group_name, group_order 
                    FROM stocks WHERE is_active = 1 
                    ORDER BY group_order ASC, id DESC
                """)
                stocks = cursor.fetchall()

        if not stocks:
            return {"code": 0, "data": {}}
        
        symbols = [s['symbol'] for s in stocks]
        quotes = await longbridge_sdk.get_realtime_quote(symbols)
        quotes_map = {q['symbol']: q for q in quotes}
        
        # 按分组组织数据
        grouped_data = {}
        # 预先获取分组顺序（可选，如果需要更精确的顺序）
        group_orders = {}
        for stock in stocks:
            group = stock.get('group_name') or '默认分组'
            if group not in grouped_data:
                grouped_data[group] = {
                    "group_name": group,
                    "group_order": stock.get('group_order', 0),
                    "stocks": []
                }
            
            symbol = stock['symbol']
            quote = quotes_map.get(symbol, {})
            
            # 真实模式下，如果行情获取失败且非测试模式，价格显示为0或上一次价格
            price = quote.get('price', 0)
            change_pct = quote.get('change_pct', 0)
            
            acceleration = acceleration_calculator.update(
                symbol,
                price,
                change_pct
            )
            
            grouped_data[group]["stocks"].append({
                'symbol': symbol,
                'name': stock['name'],
                'stock_type': stock.get('stock_type', 'STOCK'),
                'price': price,
                'change_pct': change_pct,
                'volume': quote.get('volume', 0),
                'acceleration': acceleration
            })
        
        return {"code": 0, "data": grouped_data}
    finally:
        cursor.close()
        conn.close()


@router.get("/api/stock/history/{symbol}")
async def get_stock_history(symbol: str, period: str = 'day', count: int = 30, 
                           current_user: dict = Depends(get_current_user)):
    """获取股票历史K线"""
    try:
        klines = await longbridge_sdk.get_stock_history(symbol, period, count)
        return {"code": 0, "data": klines}
    except Exception as e:
        return {"code": 1, "message": str(e), "data": []}


@router.get("/api/events")
async def events(current_user: dict = Depends(get_current_user)):
    """SSE事件流"""
    async def event_generator():
        queue = asyncio.Queue()
        sse_clients.add(queue)
        
        try:
            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {message}\n\n"
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
        finally:
            sse_clients.discard(queue)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
