"""
交易记录路由
"""
from fastapi import APIRouter, Depends
import pymysql

from app.config.database import get_db_connection
from app.auth.utils import get_current_user, is_test_mode
from app.services.longbridge_sdk import longbridge_sdk

router = APIRouter(tags=["交易"])


@router.get("/api/trades")
async def get_trades(current_user: dict = Depends(get_current_user)):
    """获取交易记录"""
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    try:
        test_mode = 1 if is_test_mode() else 0
        cursor.execute(
            "SELECT * FROM trades WHERE test_mode = %s ORDER BY trade_time DESC LIMIT 100",
            (test_mode,)
        )
        trades = cursor.fetchall()
        return {"code": 0, "data": trades}
    finally:
        cursor.close()
        conn.close()


@router.get("/api/orders")
async def get_orders(current_user: dict = Depends(get_current_user)):
    """获取历史订单"""
    try:
        orders = await longbridge_sdk.get_history_orders(days=90, limit=100)
        return {"code": 0, "data": orders}
    except Exception as e:
        return {"code": 0, "data": [], "message": str(e)}
