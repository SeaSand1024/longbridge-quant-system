"""
监控路由
"""
import logging
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
import asyncio

from app.auth.utils import get_current_user, is_test_mode
from app.services.trading_strategy import trading_strategy

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/monitoring", tags=["监控"])

# 监控状态
monitoring_task = None
is_monitoring = False


class StartMonitoringRequest(BaseModel):
    buy_amount: Optional[str] = None


@router.post("/start")
async def start_monitoring(
    request: StartMonitoringRequest = None, 
    current_user: dict = Depends(get_current_user)
):
    """启动监控"""
    global monitoring_task, is_monitoring
    
    try:
        if is_monitoring:
            return {"code": 0, "message": "监控已在运行中"}
        
        # 如果传入了 buy_amount，先更新配置
        if request and request.buy_amount:
            from app.config.database import get_db_connection
            import pymysql
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE system_config SET config_value = %s WHERE config_key = 'buy_amount'
            """, (request.buy_amount,))
            conn.commit()
            cursor.close()
            conn.close()
            logger.info(f"更新买入金额配置: {request.buy_amount}")
        
        # 加载配置
        await trading_strategy.load_config()
        
        # 启动监控任务
        from app.services.task_queue import task_queue
        await task_queue.start()
        
        is_monitoring = True
        
        return {
            "code": 0,
            "message": "监控已启动",
            "data": {
                "is_test_mode": is_test_mode(),
                "profit_target": trading_strategy.profit_target,
                "buy_amount": trading_strategy.buy_amount
            }
        }
    except Exception as e:
        logger.error(f"启动监控失败: {str(e)}", exc_info=True)
        return {"code": 1, "message": f"启动监控失败: {str(e)}"}



@router.post("/stop")
async def stop_monitoring(current_user: dict = Depends(get_current_user)):
    """停止监控"""
    global monitoring_task, is_monitoring
    
    is_monitoring = False
    
    from app.services.task_queue import task_queue
    await task_queue.stop()
    
    return {"code": 0, "message": "监控已停止"}


@router.get("/status")
async def get_monitoring_status(current_user: dict = Depends(get_current_user)):
    """获取监控状态"""
    from app.services.acceleration import acceleration_calculator
    
    test_mode = is_test_mode()
    
    return {
        "code": 0,
        "data": {
            "is_monitoring": is_monitoring,
            "is_test_mode": test_mode,
            "test_mode": test_mode,  # 前端兼容字段
            "config": {
                "profit_target": trading_strategy.profit_target,
                "buy_amount": trading_strategy.buy_amount,
                "max_concurrent_positions": trading_strategy.max_concurrent_positions
            },
            "top_accelerating": acceleration_calculator.get_top_accelerating(5)
        }
    }
