"""
系统配置路由
"""
from fastapi import APIRouter, Depends
import pymysql

from app.config.database import get_db_connection
from app.config.settings import CONFIG_DEFINITIONS, ensure_default_system_configs
from app.auth.utils import get_current_user

router = APIRouter(prefix="/api/config", tags=["配置"])


@router.get("")
async def get_config(current_user: dict = Depends(get_current_user)):
    """获取系统配置"""
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    try:
        ensure_default_system_configs(cursor)
        conn.commit()
        
        cursor.execute("SELECT * FROM system_config")
        configs = cursor.fetchall()
        
        config_dict = {c['config_key']: c['config_value'] for c in configs}
        
        return {
            "code": 0,
            "data": {
                "configs": config_dict,
                "values": config_dict,  # 前端兼容字段
                "definitions": CONFIG_DEFINITIONS
            }
        }
    finally:
        cursor.close()
        conn.close()


@router.put("")
async def update_config(config: dict, current_user: dict = Depends(get_current_user)):
    """更新系统配置"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        config_key = config.get('config_key')
        config_value = config.get('config_value')
        
        if not config_key:
            return {"code": 1, "message": "配置键不能为空"}
        
        cursor.execute("""
            INSERT INTO system_config (config_key, config_value) VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE config_value = VALUES(config_value)
        """, (config_key, str(config_value)))
        
        conn.commit()
        
        # 更新交易策略配置
        from app.services.trading_strategy import trading_strategy
        await trading_strategy.load_config()
        
        return {"code": 0, "message": "配置已更新"}
    finally:
        cursor.close()
        conn.close()
