"""
美股量化交易系统 - 主入口
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 导入配置和服务
from app.config.settings import (
    LONGBRIDGE_CONFIG, ensure_default_system_configs
)
from app.config.database import get_db_connection

# 导入服务
from app.services.longbridge_sdk import LongBridgeSDK, longbridge_sdk
from app.services.task_queue import task_queue
from app.services.smart_trader import smart_trader
from app.services.trading_strategy import trading_strategy

# 导入路由
from app.routers import (
    auth_router, stocks_router, trades_router,
    positions_router, config_router, monitoring_router,
    smart_trade_router, longbridge_router, market_data_router
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    # 启动事件
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        inserted = ensure_default_system_configs(cursor)
        if inserted:
            conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        logger.warning(f"初始化系统配置失败: {e}")

    # 加载长桥配置
    _load_longbridge_config()

    # 初始化SDK
    from app.services import longbridge_sdk as sdk_module
    sdk_module.longbridge_sdk = LongBridgeSDK(LONGBRIDGE_CONFIG)
    await sdk_module.longbridge_sdk.connect()

    # 启动异步任务队列
    await task_queue.start()

    logger.info("系统启动完成")

    yield

    # 关闭事件
    await task_queue.stop()
    logger.info("系统已关闭")


# 创建FastAPI应用
app = FastAPI(title="美股量化交易系统", lifespan=lifespan)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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


@app.get("/")
async def root():
    """根路径重定向到静态页面"""
    return RedirectResponse(url="/static/index.html")


def _load_longbridge_config():
    """从数据库加载长桥配置"""
    try:
        import pymysql.cursors
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


# 挂载静态文件（必须在最后）
app.mount("/static", StaticFiles(directory="static", html=True), name="static")


# 启动入口
if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )
