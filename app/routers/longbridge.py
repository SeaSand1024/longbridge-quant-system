"""
长桥SDK路由
"""
import logging
from fastapi import APIRouter, HTTPException, Depends
import pymysql

from app.config.database import get_db_connection
from app.config.settings import LONGBRIDGE_CONFIG
from app.auth.utils import get_current_user, load_user_longbridge_config
from app.services.longbridge_sdk import longbridge_sdk, LONGBRIDGE_AVAILABLE
from app.models.schemas import LongBridgeConfigUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/longbridge", tags=["长桥SDK"])


@router.get("/config")
async def get_longbridge_config(current_user: dict = Depends(get_current_user)):
    """获取长桥配置（用户级）"""
    user_id = current_user['id']
    
    # 从用户配置表加载
    user_config = load_user_longbridge_config(user_id)
    
    # 判断用户是否已配置
    is_configured = bool(
        user_config.get('app_key') and 
        user_config.get('app_secret') and 
        user_config.get('access_token')
    )
    
    # 如果用户有配置，显示用户配置；否则显示全局配置状态
    app_key = user_config.get('app_key') or LONGBRIDGE_CONFIG.get('app_key', '')
    app_secret = user_config.get('app_secret') or LONGBRIDGE_CONFIG.get('app_secret', '')
    access_token = user_config.get('access_token') or LONGBRIDGE_CONFIG.get('access_token', '')
    
    return {
        "code": 0,
        "data": {
            "app_key": app_key[:10] + '***' if app_key else '',
            "app_key_full": app_key,  # 用于前端回填
            "has_secret": bool(app_secret),
            "has_token": bool(access_token),
            "http_url": LONGBRIDGE_CONFIG['http_url'],
            "is_connected": longbridge_sdk.is_connected,
            "use_real_sdk": longbridge_sdk.use_real_sdk,
            "sdk_available": LONGBRIDGE_AVAILABLE,
            "is_configured": is_configured
        }
    }


@router.post("/config")
async def update_longbridge_config(config: LongBridgeConfigUpdate, current_user: dict = Depends(get_current_user)):
    """更新长桥配置（保存到用户配置表）"""
    user_id = current_user['id']
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        updates = []
        if config.app_key:
            updates.append(('longbridge_app_key', config.app_key))
            LONGBRIDGE_CONFIG['app_key'] = config.app_key
        if config.app_secret:
            updates.append(('longbridge_app_secret', config.app_secret))
            LONGBRIDGE_CONFIG['app_secret'] = config.app_secret
        if config.access_token:
            updates.append(('longbridge_access_token', config.access_token))
            LONGBRIDGE_CONFIG['access_token'] = config.access_token
        
        # 保存到用户配置表（user_config）
        for key, value in updates:
            cursor.execute("""
                INSERT INTO user_config (user_id, config_key, config_value, description)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE config_value = VALUES(config_value)
            """, (user_id, key, value, f'长桥配置: {key}'))
        
        conn.commit()
        
        # 重新连接SDK
        longbridge_sdk.use_real_sdk = (
            LONGBRIDGE_AVAILABLE and 
            LONGBRIDGE_CONFIG.get('app_key') and 
            LONGBRIDGE_CONFIG.get('app_secret') and 
            LONGBRIDGE_CONFIG.get('access_token')
        )
        await longbridge_sdk.connect()
        
        return {
            "code": 0, 
            "message": "长桥配置已更新",
            "data": {
                "use_real_sdk": longbridge_sdk.use_real_sdk,
                "is_connected": longbridge_sdk.is_connected
            }
        }
    finally:
        cursor.close()
        conn.close()


@router.post("/sync-watchlist")
async def sync_watchlist(current_user: dict = Depends(get_current_user)):
    """同步自选股"""
    conn = None
    try:
        watchlist = await longbridge_sdk.get_watchlist()
        
        if not watchlist:
            return {"code": 0, "message": "无自选股数据", "data": []}
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        added = 0
        for item in watchlist:
            symbol = item.get('symbol', '')
            name = item.get('name', symbol)
            group = item.get('group', '默认分组')
            
            # 限制 symbol 长度，避免超过数据库字段长度
            if symbol:
                symbol = str(symbol)[:20]  # 数据库 symbol 列最多 20 字符
                name = str(name)[:90]
                group = str(group)[:90]
                
                try:
                    cursor.execute("""
                        INSERT INTO stocks (symbol, name, group_name, is_active)
                        VALUES (%s, %s, %s, 1)
                        ON DUPLICATE KEY UPDATE name = VALUES(name), group_name = VALUES(group_name), is_active = 1
                    """, (symbol, name, group))
                    added += 1
                except Exception as e:
                    logger.warning(f"同步单只股票 {symbol} 失败: {e}")
                    continue
        
        conn.commit()
        return {"code": 0, "message": f"同步完成，共{added}只股票", "data": watchlist}
    except Exception as e:
        logger.error(f"同步自选股发生严重错误: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@router.post("/sync-positions")
async def sync_positions(current_user: dict = Depends(get_current_user)):
    """同步持仓"""
    try:
        positions = await longbridge_sdk.get_stock_positions()
        return {"code": 0, "message": f"同步完成，共{len(positions)}个持仓", "data": positions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
