"""
股票管理路由
"""
from fastapi import APIRouter, HTTPException, Depends
import pymysql

from app.config.database import get_db_connection
from app.config.settings import classify_symbol_type
from app.auth.utils import get_current_user

router = APIRouter(prefix="/api/stocks", tags=["股票"])


@router.get("")
async def get_stocks(current_user: dict = Depends(get_current_user)):
    """获取股票列表"""
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    try:
        cursor.execute("SELECT * FROM stocks ORDER BY group_order ASC, id DESC")
        stocks = cursor.fetchall()
        return {"code": 0, "data": stocks}
    finally:
        cursor.close()
        conn.close()


@router.post("")
async def add_stock(stock: dict, current_user: dict = Depends(get_current_user)):
    """添加股票"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        symbol = stock.get('symbol', '').upper().strip()
        name = stock.get('name', symbol)
        group_name = stock.get('group_name', '默认分组')
        
        if not symbol:
            raise HTTPException(status_code=400, detail="股票代码不能为空")
        
        stock_type = classify_symbol_type(symbol)
        
        cursor.execute(
            """INSERT INTO stocks (symbol, name, stock_type, group_name, is_active) 
               VALUES (%s, %s, %s, %s, 1)
               ON DUPLICATE KEY UPDATE name = VALUES(name), group_name = VALUES(group_name), is_active = 1""",
            (symbol, name, stock_type, group_name)
        )
        conn.commit()
        
        return {"code": 0, "message": "添加成功", "data": {"symbol": symbol, "stock_type": stock_type}}
    finally:
        cursor.close()
        conn.close()


@router.delete("/{stock_id}")
async def delete_stock(stock_id: int, current_user: dict = Depends(get_current_user)):
    """删除股票"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("DELETE FROM stocks WHERE id = %s", (stock_id,))
        conn.commit()
        return {"code": 0, "message": "删除成功"}
    finally:
        cursor.close()
        conn.close()


@router.put("/{stock_id}/toggle")
async def toggle_stock(stock_id: int, current_user: dict = Depends(get_current_user)):
    """切换股票激活状态"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("UPDATE stocks SET is_active = NOT is_active WHERE id = %s", (stock_id,))
        conn.commit()
        return {"code": 0, "message": "状态已更新"}
    finally:
        cursor.close()
        conn.close()
