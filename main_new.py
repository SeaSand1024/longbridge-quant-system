"""
美股量化交易系统 - 主入口文件
模块化重构版本
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
import logging
import pymysql

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title="美股量化交易系统",
    description="基于长桥SDK的量化交易系统，支持智能预测和自动交易",
    version="2.0.0"
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 导入配置
from app.config.settings import LONGBRIDGE_CONFIG
from app.config.database import get_db_connection

# 导入路由
from app.routers import (
    auth_router, stocks_router, trades_router, 
    positions_router, config_router, monitoring_router,
    smart_trade_router, longbridge_router, market_data_router
)

# 注册路由
app.include_router(auth_router)
app.include_router(stocks_router)
app.include_router(trades_router)
app.include_router(positions_router)
app.include_router(config_router)
app.include_router(monitoring_router)
app.include_router(smart_trade_router)
app.include_router(longbridge_router)
app.include_router(market_data_router)

# 静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    """根路由，重定向到静态页面"""
    return RedirectResponse(url="/static/index.html")


def _load_longbridge_config():
    """从数据库加载长桥配置"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute("""
            SELECT config_key, config_value FROM system_config 
            WHERE config_key IN (
                'longbridge_app_key', 'longbridge_app_secret', 'longbridge_access_token',
                'longbridge_http_url', 'longbridge_quote_ws_url', 'longbridge_trade_ws_url'
            )
        """)
        configs = cursor.fetchall()
        cursor.close()
        conn.close()

        for config in configs:
            key = config['config_key']
            value = config['config_value']
            if key == 'longbridge_app_key':
                LONGBRIDGE_CONFIG['app_key'] = value
            elif key == 'longbridge_app_secret':
                LONGBRIDGE_CONFIG['app_secret'] = value
            elif key == 'longbridge_access_token':
                LONGBRIDGE_CONFIG['access_token'] = value
            elif key == 'longbridge_http_url' and value:
                LONGBRIDGE_CONFIG['http_url'] = value
            elif key == 'longbridge_quote_ws_url' and value:
                LONGBRIDGE_CONFIG['quote_ws_url'] = value
            elif key == 'longbridge_trade_ws_url' and value:
                LONGBRIDGE_CONFIG['trade_ws_url'] = value

        if LONGBRIDGE_CONFIG['app_key']:
            logger.info(f"从数据库加载长桥配置: app_key={LONGBRIDGE_CONFIG['app_key'][:8]}...")
    except Exception as e:
        logger.warning(f"从数据库加载长桥配置失败: {str(e)}")


@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    logger.info("=" * 50)
    logger.info("美股量化交易系统启动中...")
    logger.info("=" * 50)
    
    # 加载长桥配置（从system_config表）
    _load_longbridge_config()
    
    # 连接长桥SDK
    from app.services.longbridge_sdk import longbridge_sdk
    await longbridge_sdk.connect()
    
    # 启动任务队列
    from app.services.task_queue import task_queue
    await task_queue.start()
    
    # 加载交易策略配置
    from app.services.trading_strategy import trading_strategy
    await trading_strategy.load_config()
    
    # 加载智能交易配置
    from app.services.smart_trader import smart_trader
    await smart_trader.load_config()
    
    logger.info("系统启动完成!")
    logger.info(f"访问地址: http://localhost:8000")


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    logger.info("系统正在关闭...")
    
    from app.services.task_queue import task_queue
    await task_queue.stop()
    
    logger.info("系统已关闭")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main_new:app", host="0.0.0.0", port=8000, reload=True)
