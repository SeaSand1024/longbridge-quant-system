from fastapi import FastAPI, HTTPException, Depends, status, Cookie, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, StreamingResponse, JSONResponse
from pydantic import BaseModel
from typing import List, Optional
import pymysql
import os
from datetime import datetime, date, timedelta
import asyncio
import logging
import json
import secrets
from passlib.context import CryptContext
from jose import JWTError, jwt
import hashlib
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 长桥SDK导入
try:
    from longbridge.openapi import QuoteContext, TradeContext, Config as LBConfig, Market, OrderSide, OrderType, \
        TimeInForceType, SubType, PushQuote

    LONGBRIDGE_AVAILABLE = True
except ImportError:
    LONGBRIDGE_AVAILABLE = False


    # 定义模拟类型
    class PushQuote:
        """模拟PushQuote类型"""
        pass

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 数据库配置（从环境变量获取）
DB_CONFIG = {
    'host': os.getenv('MYSQL_HOST', '127.0.0.1'),
    'port': int(os.getenv('MYSQL_PORT', 3306)),
    'user': os.getenv('MYSQL_USER', 'root'),
    'password': os.getenv('MYSQL_PASSWORD', '123456'),
    'database': os.getenv('MYSQL_DB', 'quant_system'),
    'charset': 'utf8mb4'
}

# 长桥SDK配置（初始为空，从数据库加载）
LONGBRIDGE_CONFIG = {
    'app_key': '',
    'app_secret': '',
    'access_token': '',
    'http_url': 'https://openapi.longbridgeapp.com',
    'quote_ws_url': 'wss://openapi-quote.longbridgeapp.com',
    'trade_ws_url': 'wss://openapi-trade.longbridgeapp.com'
}

# 全局变量
monitoring_task = None
is_monitoring = False

# JWT配置
SECRET_KEY = os.getenv('SECRET_KEY', secrets.token_urlsafe(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24小时
REFRESH_TOKEN_EXPIRE_DAYS = 7  # 7天

# 密码加密配置
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 汇率配置（相对于美元的基础汇率）
EXCHANGE_RATES = {
    'USD': 1.0,  # 美元
    'HKD': 0.128,  # 港币（1 HKD = 0.128 USD）
    'CNY': 0.138  # 人民币（1 CNY = 0.138 USD）
}

# 微信登录配置（需要配置）
WECHAT_CONFIG = {
    'app_id': os.getenv('WECHAT_APP_ID', ''),
    'app_secret': os.getenv('WECHAT_APP_SECRET', ''),
    'enabled': os.getenv('WECHAT_LOGIN_ENABLED', 'false').lower() == 'true'
}

# 系统配置默认值（用于初始化 system_config 表）
DEFAULT_SYSTEM_CONFIGS = {
    'profit_target': {
        'value': '1.0',
        'description': '单笔止盈目标（百分比）'
    },
    'buy_amount': {
        'value': '200000',
        'description': '单笔买入金额（USD）'
    },
    'max_concurrent_positions': {
        'value': '1',
        'description': '最大并发持仓数量'
    }
}

# 配置元数据，供前端渲染配置项（例如显示单位）
CONFIG_DEFINITIONS = {
    'profit_target': {
        'label': '止盈目标',
        'type': 'number',
        'unit': '%',
        'step': 0.1,
        'min': 0.1,
        'max': 100
    },
    'buy_amount': {
        'label': '单笔买入金额',
        'type': 'number',
        'unit': 'USD',
        'step': 1000,
        'min': 1000
    },
    'max_concurrent_positions': {
        'label': '最大持仓数',
        'type': 'number',
        'min': 1
    }
}


def ensure_default_system_configs(cursor, existing_keys=None):
    """确保默认系统配置存在于数据库中，返回是否插入了新记录"""
    if existing_keys is None:
        cursor.execute("SELECT config_key FROM system_config")
        rows = cursor.fetchall()
        if rows:
            # 支持 DictCursor 和默认游标
            first_row = rows[0]
            if isinstance(first_row, dict):
                existing_keys = {row['config_key'] for row in rows}
            else:
                existing_keys = {row[0] for row in rows}
        else:
            existing_keys = set()
    else:
        existing_keys = set(existing_keys)

    inserted = False
    for key, meta in DEFAULT_SYSTEM_CONFIGS.items():
        if key not in existing_keys:
            cursor.execute(
                "INSERT INTO system_config (config_key, config_value, description) VALUES (%s, %s, %s)",
                (key, meta['value'], meta.get('description', ''))
            )
            existing_keys.add(key)
            inserted = True
    return inserted


def convert_currency(amount: float, from_currency: str = 'USD', to_currency: str = 'USD') -> float:
    """货币转换（EXCHANGE_RATES 保存的是 1 单位货币折算成的美元）"""
    if from_currency == to_currency:
        return amount

    from_rate = EXCHANGE_RATES.get(from_currency, 1.0)
    to_rate = EXCHANGE_RATES.get(to_currency, 1.0)

    # 先把原币种金额换算成美元，再转换为目标币种
    amount_in_usd = amount * from_rate
    return amount_in_usd / to_rate


def classify_symbol_type(symbol: str, security_type_hint=None) -> str:
    """
    根据长桥静态信息或代码格式推断股票类型（正股/期权）。
    :param security_type_hint: 来自长桥静态信息的类型字段，可能是枚举或字符串
    """
    # 1) 使用长桥返回的 security_type
    if security_type_hint is not None:
        name = ''
        if hasattr(security_type_hint, 'name'):
            name = security_type_hint.name.lower()
        else:
            name = str(security_type_hint).lower()

        if 'option' in name:
            return 'OPTION'
        if 'equity' in name or 'stock' in name or 'common' in name:
            return 'STOCK'

    # 2) 代码模式推断：长桥期权代码通常包含较长的数字串
    if len(symbol) > 10 and any(ch.isdigit() for ch in symbol):
        return 'OPTION'
    if any(ch.isdigit() for ch in symbol) and len(symbol.replace('.', '')) > 8:
        return 'OPTION'

    # 3) 后缀推断（.US/.HK 等）
    if '.' in symbol:
        return 'STOCK'

    return 'STOCK'


# 数据库连接
def get_db_connection():
    return pymysql.connect(**DB_CONFIG)


# ==================== 认证相关函数 ====================

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    import bcrypt
    password_bytes = plain_password.encode('utf-8')
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
    return bcrypt.checkpw(password_bytes, hashed_password.encode('utf-8'))

def get_password_hash(password: str) -> str:
    """获取密码哈希"""
    # bcrypt 限制密码最长72字节，直接在hash前截断
    import bcrypt
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode('utf-8')

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建访问令牌"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token() -> str:
    """创建刷新令牌"""
    return secrets.token_urlsafe(64)

async def get_current_user(request: Request, access_token: Optional[str] = Cookie(None)) -> dict:
    """获取当前登录用户"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="未认证",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not access_token:
        # 尝试从Authorization header获取
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            access_token = auth_header.split(" ")[1]
        else:
            raise credentials_exception

    token = access_token

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        user_id: int = payload.get("user_id")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    # 从数据库获取用户信息
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT * FROM users WHERE id = %s AND username = %s", (user_id, username))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if user is None:
        raise credentials_exception

    # 移除密码字段
    user.pop('password', None)

    return user

async def get_current_active_user(current_user: dict = Depends(get_current_user)) -> dict:
    """获取当前活跃用户"""
    if not current_user.get('is_active', False):
        raise HTTPException(status_code=400, detail="用户已被禁用")
    return current_user

def require_auth():
    """认证装饰器 - 返回Depends"""
    return Depends(get_current_user)


def is_test_mode() -> bool:
    """检查是否处于测试模式"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute("SELECT config_value FROM system_config WHERE config_key = 'test_mode'")
        result = cursor.fetchone()
        cursor.close()
        conn.close()

        if result and result['config_value'].lower() == 'true':
            return True
        return False
    except Exception:
        return False


# SSE 连接管理
sse_clients = set()


async def notify_sse_clients(event_type: str, data: dict):
    """通知所有 SSE 客户端"""
    if not sse_clients:
        return

    message = f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
    disconnected_clients = set()

    for client in sse_clients:
        try:
            await client.put(message)
        except:
            disconnected_clients.add(client)

    # 移除断开的客户端
    for client in disconnected_clients:
        sse_clients.remove(client)


# 性能监控装饰器
import time
from functools import wraps


def async_performance_monitor(func_name: str = None):
    """异步性能监控装饰器"""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                execution_time = time.time() - start_time

                # 记录执行时间（如果超过阈值）
                if execution_time > 1.0:  # 超过1秒的慢操作
                    logger.warning(f"[性能警告] {func_name or func.__name__} 执行时间: {execution_time:.3f}秒")
                elif execution_time > 0.5:  # 超过0.5秒的操作
                    logger.info(f"[性能监控] {func_name or func.__name__} 执行时间: {execution_time:.3f}秒")

                return result
            except Exception as e:
                execution_time = time.time() - start_time
                logger.error(
                    f"[性能错误] {func_name or func.__name__} 执行失败，耗时: {execution_time:.3f}秒，错误: {str(e)}")
                raise

        return wrapper

    return decorator


# 异步任务队列管理
class AsyncTaskQueue:
    """异步任务队列，用于分离监控任务和API请求"""

    def __init__(self):
        self.queue = asyncio.Queue()
        self.is_running = False
        self.processing_task = None

    async def start(self):
        """启动任务队列"""
        if not self.is_running:
            self.is_running = True
            self.processing_task = asyncio.create_task(self._process_queue())
            logger.info("异步任务队列已启动")

    async def stop(self):
        """停止任务队列"""
        if self.is_running:
            self.is_running = False
            if self.processing_task:
                self.processing_task.cancel()
                try:
                    await self.processing_task
                except asyncio.CancelledError:
                    pass
            logger.info("异步任务队列已停止")

    async def add_task(self, task_func, *args, **kwargs):
        """添加任务到队列"""
        await self.queue.put((task_func, args, kwargs))

    async def _process_queue(self):
        """处理队列中的任务"""
        while self.is_running:
            try:
                # 非阻塞等待任务，避免阻塞主线程
                try:
                    task_func, args, kwargs = await asyncio.wait_for(self.queue.get(), timeout=0.1)
                except asyncio.TimeoutError:
                    continue

                # 执行任务
                try:
                    if asyncio.iscoroutinefunction(task_func):
                        await task_func(*args, **kwargs)
                    else:
                        # 如果是普通函数，在后台线程中执行
                        loop = asyncio.get_event_loop()
                        await loop.run_in_executor(None, task_func, *args, **kwargs)
                except Exception as e:
                    logger.error(f"任务执行失败: {str(e)}")
                finally:
                    self.queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"任务队列处理出错: {str(e)}")
                await asyncio.sleep(1)


# 创建全局任务队列
task_queue = AsyncTaskQueue()


# Pydantic模型
class Stock(BaseModel):
    id: Optional[int] = None
    symbol: str
    name: str
    is_active: Optional[int] = 1


class Trade(BaseModel):
    id: Optional[int] = None
    symbol: str
    action: str
    price: float
    quantity: int
    amount: float
    acceleration: Optional[float] = None
    trade_time: Optional[str] = None
    status: Optional[str] = 'PENDING'
    message: Optional[str] = None


class Position(BaseModel):
    id: Optional[int] = None
    symbol: str
    quantity: int
    avg_cost: float
    current_price: Optional[float] = None
    profit_loss: Optional[float] = None
    profit_loss_pct: Optional[float] = None


class SystemConfig(BaseModel):
    config_key: str
    config_value: str
    description: Optional[str] = None


class MarketData(BaseModel):
    symbol: str
    price: float
    change_pct: float
    acceleration: float
    volume: int
    timestamp: str


# 测试模式模拟价格管理
class TestModePriceManager:
    """测试模式下管理模拟价格的持续性"""

    def __init__(self):
        self.base_prices = {}  # {symbol: base_price}
        self.current_prices = {}  # {symbol: current_price}
        self.price_trends = {}  # {symbol: trend}  # 1=上涨, -1=下跌, 0=震荡

    def get_price(self, symbol: str) -> tuple:
        """获取模拟价格和涨跌幅，返回(price, change_pct)"""
        import random

        # 如果没有基础价格，初始化
        if symbol not in self.base_prices:
            self.base_prices[symbol] = 100.0 + random.uniform(-30, 50)
            self.current_prices[symbol] = self.base_prices[symbol]
            self.price_trends[symbol] = random.choice([-1, 0, 1])

        base_price = self.base_prices[symbol]
        current_price = self.current_prices[symbol]
        trend = self.price_trends[symbol]

        # 检查是否有持仓，如果有持仓则倾向于上涨
        # 通过数据库查询持仓状态（避免循环依赖）
        has_position = False
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as cnt FROM positions WHERE symbol = %s AND quantity > 0", (symbol,))
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            has_position = result[0] > 0 if result else False
        except:
            pass

        # 价格变化：小幅波动 + 趋势
        if has_position:
            # 持仓时，价格逐步上涨（更容易达到止盈）
            change_pct = random.uniform(0.1, 0.5)  # 每次上涨0.1%-0.5%
            trend = 1
        else:
            # 无持仓时，根据趋势小幅变化
            if trend > 0:
                change_pct = random.uniform(-0.2, 0.8)
            elif trend < 0:
                change_pct = random.uniform(-0.8, 0.2)
            else:
                change_pct = random.uniform(-0.5, 0.5)

            # 偶尔改变趋势
            if random.random() < 0.1:  # 10%概率改变趋势
                self.price_trends[symbol] = random.choice([-1, 0, 1])

        # 更新当前价格
        new_price = current_price * (1 + change_pct / 100)
        # 限制价格范围（基础价格的50%-200%）
        price_range = (base_price * 0.5, base_price * 2.0)
        new_price = max(price_range[0], min(price_range[1], new_price))

        self.current_prices[symbol] = new_price

        # 计算相对于基础价格的涨跌幅
        change_pct_from_base = ((new_price - base_price) / base_price) * 100

        return new_price, change_pct_from_base

    def reset_price(self, symbol: str):
        """重置某个股票的价格（卖出后重置）"""
        if symbol in self.base_prices:
            del self.base_prices[symbol]
            del self.current_prices[symbol]
            del self.price_trends[symbol]


test_mode_price_manager = TestModePriceManager()


# 模拟长桥SDK功能
class LongBridgeSDK:
    """长桥SDK封装类，支持真实SDK和模拟模式"""

    def __init__(self, config):
        self.config = config
        self.is_connected = False
        self.quote_ctx = None
        self.trade_ctx = None
        self.use_real_sdk = LONGBRIDGE_AVAILABLE and config.get('app_key') and config.get('app_secret') and config.get \
            ('access_token')

        if self.use_real_sdk:
            logger.info("使用真实长桥SDK")
        else:
            logger.info("使用模拟模式（长桥SDK未配置或未安装）")

    async def connect(self):
        """连接到长桥"""
        logger.info("正在连接长桥SDK...")

        if self.use_real_sdk:
            try:
                # 创建长桥配置
                lb_config = LBConfig(
                    app_key=self.config['app_key'],
                    app_secret=self.config['app_secret'],
                    access_token=self.config['access_token'],
                    http_url=self.config.get('http_url', 'https://openapi.longbridgeapp.com'),
                    quote_ws_url=self.config.get('quote_ws_url', 'wss://openapi-quote.longbridgeapp.com'),
                    trade_ws_url=self.config.get('trade_ws_url', 'wss://openapi-trade.longbridgeapp.com')
                )

                # 创建行情上下文
                self.quote_ctx = QuoteContext(lb_config)

                # 创建交易上下文
                self.trade_ctx = TradeContext(lb_config)

                self.is_connected = True
                logger.info("长桥SDK连接成功（真实模式）")
            except Exception as e:
                logger.error(f"长桥SDK连接失败: {str(e)}")
                logger.info("切换到模拟模式")
                self.use_real_sdk = False
                self.is_connected = True
        else:
            # 模拟模式
            self.is_connected = True
            logger.info("长桥SDK连接成功（模拟模式）")

    def subscribe_realtime_quotes(self, symbols: List[str], callback):
        """订阅实时行情推送"""
        if self.use_real_sdk and self.quote_ctx:
            try:
                # 设置行情回调
                self.quote_ctx.set_on_quote(callback)

                # 订阅行情
                self.quote_ctx.subscribe(symbols, [SubType.Quote], is_first_push=False)
                logger.info(f"已订阅实时行情: {symbols}")
                return True
            except Exception as e:
                logger.error(f"订阅实时行情失败: {str(e)}")
                return False
        else:
            logger.info("模拟模式，不需要订阅实时行情")
            return False

    def unsubscribe_realtime_quotes(self, symbols: List[str]):
        """取消订阅实时行情推送"""
        if self.use_real_sdk and self.quote_ctx:
            try:
                self.quote_ctx.unsubscribe(symbols, [SubType.Quote])
                logger.info(f"已取消订阅实时行情: {symbols}")
            except Exception as e:
                logger.error(f"取消订阅实时行情失败: {str(e)}")

    async def get_realtime_quote(self, symbols: List[str]) -> List[dict]:
        """获取实时行情"""
        # 如果是测试模式，直接返回模拟数据
        if is_test_mode():
            return self._get_mock_quotes(symbols)

        if self.use_real_sdk and self.quote_ctx:
            try:
                # 使用真实SDK获取行情
                quotes = self.quote_ctx.quote(symbols)
                result = []
                for quote in quotes:
                    # 计算涨跌幅
                    current_price = float(quote.last_done)
                    prev_close = float(quote.prev_close) if hasattr(quote,
                                                                    'prev_close') and quote.prev_close else current_price
                    change_pct = ((current_price - prev_close) / prev_close) * 100 if prev_close > 0 else 0.0

                    result.append({
                        'symbol': quote.symbol,
                        'price': current_price,
                        'change_pct': change_pct,  # 百分比
                        'volume': int(quote.volume),
                        'timestamp': datetime.now().isoformat()
                    })
                return result
            except Exception as e:
                logger.error(f"获取行情失败: {str(e)}")
                # 失败时返回模拟数据
                return self._get_mock_quotes(symbols)
        else:
            # 模拟数据
            return self._get_mock_quotes(symbols)

    async def get_history_orders(self, symbol: Optional[str] = None, status_filter: Optional[List] = None,
                                 days: int = 90, limit: int = 50) -> List[dict]:
        """获取历史订单"""
        if self.use_real_sdk and self.trade_ctx:
            try:
                # 使用真实SDK获取历史订单
                from longbridge.openapi import OrderStatus
                from datetime import timedelta

                # 计算时间范围（最近90天）
                end_at = datetime.now()
                start_at = end_at - timedelta(days=days)

                # 设置状态过滤（查询所有非New状态的订单）
                if status_filter is None:
                    status_filter = [
                        OrderStatus.Filled,
                        OrderStatus.Canceled,
                        OrderStatus.Rejected,
                        OrderStatus.PartialFilled,
                        OrderStatus.Expired,
                        OrderStatus.PendingCancel,
                        OrderStatus.Replaced
                    ]

                orders = self.trade_ctx.history_orders(
                    symbol=symbol,
                    status=status_filter,
                    start_at=start_at,
                    end_at=end_at
                )

                logger.info(f"从长桥获取到 {len(orders)} 条历史订单")

                def enum_to_str(value, default="Unknown"):
                    if value is None:
                        return default
                    value_str = str(value)
                    if '.' in value_str:
                        value_str = value_str.split('.')[-1]
                    return value_str or default

                def safe_float(val):
                    try:
                        return float(val)
                    except Exception:
                        return 0.0

                def safe_int(val):
                    try:
                        return int(val)
                    except Exception:
                        return 0

                result = []
                for order in orders:
                    order_id = getattr(order, 'order_id', '')
                    symbol_val = getattr(order, 'symbol', '')
                    side = getattr(order, 'side', None)
                    order_type = getattr(order, 'order_type', None)

                    # 调试：记录第一条订单的side类型
                    if len(result) == 0:
                        logger.info(f"订单调试 - side类型: {type(side)}, 值: {side}, repr: {repr(side)}")
                        logger.info(f"side是否有name属性: {hasattr(side, 'name')}")
                        if hasattr(side, 'name'):
                            logger.info(f"side.name = {side.name}")
                        logger.info(f"side是字符串吗: {isinstance(side, str)}")

                    # 安全处理价格字段（可能是None）
                    submitted_price = safe_float(getattr(order, 'submitted_price', None))
                    executed_price = safe_float(getattr(order, 'executed_price', None))
                    order_price = safe_float(getattr(order, 'order_price', None))

                    # 安全处理数量字段
                    submitted_quantity = safe_int(getattr(order, 'submitted_quantity', None))
                    executed_quantity = safe_int(getattr(order, 'executed_quantity', None))

                    status = getattr(order, 'status', None)
                    updated_at = getattr(order, 'updated_at', None)
                    currency = enum_to_str(getattr(order, 'currency', 'USD'), default='USD')
                    remark = getattr(order, 'remark', '')

                    # 将枚举对象转换为字符串（避免FastAPI序列化错误）
                    side_str = enum_to_str(side, default='Unknown')
                    order_type_str = enum_to_str(order_type, default='Unknown')
                    status_str = enum_to_str(status, default='Unknown')

                    # 记录第一条订单的详细信息用于调试
                    if len(result) == 0:
                        logger.info(
                            f"第一条订单示例 - order_id={order_id}, symbol={symbol_val}, side_str={side_str}, status_str={status_str}")

                    result.append({
                        'order_id': order_id,
                        'symbol': symbol_val,
                        'side': side_str,
                        'order_type': order_type_str,
                        'status': status_str,
                        'submitted_price': submitted_price,
                        'executed_price': executed_price,
                        'submitted_quantity': submitted_quantity,
                        'executed_quantity': executed_quantity,
                        'updated_at': updated_at.isoformat() if updated_at else '',
                        'currency': currency,
                        'order_price': order_price,
                        'remark': remark
                    })

                # 按更新时间倒序排列
                result.sort(key=lambda x: x['updated_at'], reverse=True)

                # 限制返回数量
                return result[:limit]
            except Exception as e:
                logger.error(f"获取历史订单失败: {str(e)}")
                import traceback
                logger.error(traceback.format_exc())
                return []
        else:
            logger.warning("SDK未配置，无法获取历史订单")
            return []

    async def get_static_info(self, symbols: List[str]) -> dict:
        """
        获取标的静态信息（用于判定正股/期权）。
        返回：{symbol: security_type_object_or_string}
        """
        if self.use_real_sdk and self.quote_ctx:
            try:
                info_list = []
                if hasattr(self.quote_ctx, "static_info"):
                    info_list = self.quote_ctx.static_info(symbols)
                elif hasattr(self.quote_ctx, "securities_static_info"):
                    info_list = self.quote_ctx.securities_static_info(symbols)

                type_map = {}
                for info in info_list or []:
                    sec_symbol = getattr(info, 'symbol', None)
                    sec_type = getattr(info, 'security_type', None) or getattr(info, 'type', None)
                    if sec_symbol:
                        type_map[sec_symbol.replace('.US', '').replace('.HK', '').replace('.SH', '').replace('.SZ',
                                                                                                             '')] = sec_type
                return type_map
            except Exception as e:
                logger.warning(f"获取静态信息失败，使用本地规则判定: {e}")
                return {}
        return {}

    def _get_mock_quotes(self, symbols: List[str]) -> List[dict]:
        """生成模拟行情数据"""
        import random
        result = []
        for symbol in symbols:
            # 使用测试模式价格管理器获取持续性价格
            if is_test_mode():
                price, change_pct = test_mode_price_manager.get_price(symbol)
            else:
                # 非测试模式，使用随机价格
                base_price = 100.0 + random.uniform(-50, 100)
                change_pct = random.uniform(-5.0, 5.0)
                price = base_price * (1 + change_pct / 100)

            result.append({
                'symbol': symbol,
                'price': round(price, 2),
                'change_pct': round(change_pct, 2),
                'volume': random.randint(1000000, 10000000),
                'timestamp': datetime.now().isoformat()
            })
        return result

    async def place_order(self, symbol: str, action: str, quantity: int, price: float) -> dict:
        """下单"""
        # 如果是测试模式，模拟下单成功
        if is_test_mode():
            logger.info(f"[测试模式] 模拟下单: {action} {symbol} {quantity}股 @ ${price}")
            return {
                'order_id': f"TEST{datetime.now().strftime('%Y%m%d%H%M%S')}",
                'status': 'SUCCESS',
                'message': '测试模式：订单已模拟提交'
            }

        logger.info(f"下单: {action} {symbol} {quantity}股 @ ${price}")

        if self.use_real_sdk and self.trade_ctx:
            try:
                # 使用真实SDK下单
                order_side = OrderSide.Buy if action == 'BUY' else OrderSide.Sell

                # 提交订单
                order = self.trade_ctx.submit_order(
                    symbol=symbol,
                    order_type=OrderType.LO,  # 限价单
                    side=order_side,
                    submitted_quantity=quantity,
                    submitted_price=price,
                    time_in_force=TimeInForceType.Day
                )

                return {
                    'order_id': order.order_id,
                    'status': 'SUCCESS',
                    'message': '订单已提交'
                }
            except Exception as e:
                logger.error(f"下单失败: {str(e)}")
                return {
                    'order_id': f"ORD{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    'status': 'FAILED',
                    'message': f'下单失败: {str(e)}'
                }
        else:
            return {
                'order_id': f"ORD{datetime.now().strftime('%Y%m%d%H%M%S')}",
                'status': 'FAILED',
                'message': 'SDK未配置或未连接'
            }

    async def get_account_balance(self) -> dict:
        """获取账户余额"""
        # 如果是测试模式，计算实际的现金和持仓市值
        if is_test_mode():
            # 初始资金
            initial_cash = 500000.0

            # 从数据库查询持仓
            conn = get_db_connection()
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            cursor.execute("SELECT symbol, quantity, avg_cost FROM positions WHERE quantity > 0")
            positions = cursor.fetchall()

            # 计算持仓市值和持仓成本
            position_market_value = 0.0
            position_cost = 0.0

            if positions:
                symbols = [pos['symbol'] for pos in positions]
                try:
                    # 获取实时行情来计算市值
                    quotes = await self.get_realtime_quote(symbols)
                    quote_dict = {q['symbol']: q['price'] for q in quotes}

                    for pos in positions:
                        quantity = int(pos['quantity'])
                        avg_cost = float(pos['avg_cost'])
                        current_price = quote_dict.get(pos['symbol'], avg_cost)

                        position_market_value += current_price * quantity
                        position_cost += avg_cost * quantity
                except Exception as e:
                    logger.warning(f"获取测试模式持仓市值失败: {e}，使用成本价计算")
                    for pos in positions:
                        quantity = int(pos['quantity'])
                        avg_cost = float(pos['avg_cost'])
                        position_market_value += avg_cost * quantity
                        position_cost += avg_cost * quantity

            # 从交易记录计算实际现金余额
            # 买入金额 = SUM(amount) WHERE action = 'BUY'
            # 卖出金额 = SUM(amount) WHERE action = 'SELL'
            cursor.execute("""
                SELECT
                    SUM(CASE WHEN action = 'BUY' THEN amount ELSE 0 END) as total_buy,
                    SUM(CASE WHEN action = 'SELL' THEN amount ELSE 0 END) as total_sell
                FROM trades
            """)
            trade_summary = cursor.fetchone()

            total_buy = float(trade_summary['total_buy'] or 0)
            total_sell = float(trade_summary['total_sell'] or 0)

            cursor.close()
            conn.close()

            # 可用现金 = 初始资金 - 买入总额 + 卖出总额
            available_cash = max(0, initial_cash - total_buy + total_sell)

            # 总资产 = 可用现金 + 持仓市值
            total_assets = available_cash + position_market_value

            return {
                'cash': available_cash,
                'total_assets': total_assets,
                'available_cash': available_cash,
                'position_market_value': position_market_value,
                'currency': 'USD',
                'base_currency': 'USD',
                'base_net_assets': total_assets,
                'multi_currency': {
                    'USD': {
                        'cash': available_cash,
                        'total_assets': total_assets,
                        'available_cash': available_cash,
                        'withdraw_cash': available_cash
                    }
                }
            }

        if self.use_real_sdk and self.trade_ctx:
            try:
                # 使用真实SDK获取账户信息
                account = self.trade_ctx.account_balance()
                if account:
                    acc = account[0]
                    base_currency = acc.currency  # 账户基础货币
                    base_net_assets = float(getattr(acc, 'total_assets', acc.net_assets))  # 优先用总资产字段，缺失再用净资产
                    base_total_cash = float(getattr(acc, 'total_cash', 0.0))

                    # 从 cash_infos 中获取各币种的现金
                    cash_infos = getattr(acc, 'cash_infos', [])
                    multi_currency = {}

                    total_usd_equivalent = 0.0
                    total_usd_cash = 0.0

                    for cash_info in cash_infos:
                        currency = cash_info.currency
                        available_cash = float(cash_info.available_cash) if hasattr(cash_info,
                                                                                    'available_cash') else 0.0
                        withdraw_cash = float(cash_info.withdraw_cash) if hasattr(cash_info, 'withdraw_cash') else 0.0

                        # 计算该币种的现金美元等值
                        usd_equivalent = convert_currency(available_cash, currency, 'USD')
                        total_usd_cash += usd_equivalent

                        multi_currency[currency] = {
                            'cash': available_cash,
                            'total_assets': convert_currency(base_net_assets, base_currency, currency),
                            'available_cash': available_cash,
                            'withdraw_cash': withdraw_cash
                        }

                    # 如果 cash_infos 中没有 USD, 用基础货币的美元等值
                    if 'USD' not in multi_currency:
                        usd_equivalent = convert_currency(base_net_assets, base_currency, 'USD')
                        multi_currency['USD'] = {
                            'cash': usd_equivalent,
                            'total_assets': usd_equivalent,
                            'available_cash': usd_equivalent,
                            'withdraw_cash': usd_equivalent
                        }

                    # 添加其他币种（如果有）
                    if 'HKD' not in multi_currency:
                        multi_currency['HKD'] = {
                            'cash': convert_currency(base_net_assets, base_currency, 'HKD'),
                            'total_assets': base_net_assets if base_currency == 'HKD' else convert_currency(
                                base_net_assets, base_currency, 'HKD'),
                            'available_cash': convert_currency(base_net_assets, base_currency, 'HKD'),
                            'withdraw_cash': convert_currency(base_net_assets, base_currency, 'HKD')
                        }
                    if 'CNY' not in multi_currency:
                        multi_currency['CNY'] = {
                            'cash': convert_currency(base_net_assets, base_currency, 'CNY'),
                            'total_assets': convert_currency(base_net_assets, base_currency, 'CNY'),
                            'available_cash': convert_currency(base_net_assets, base_currency, 'CNY'),
                            'withdraw_cash': convert_currency(base_net_assets, base_currency, 'CNY')
                        }

                    # 以美元计算的总资产和持仓市值（用总资产 - 总现金，更贴近官方口径）
                    usd_total_assets = convert_currency(base_net_assets, base_currency, 'USD')
                    usd_total_cash = convert_currency(
                        base_total_cash if base_total_cash > 0 else multi_currency['USD']['available_cash'],
                        base_currency, 'USD')
                    position_market_value = max(usd_total_assets - usd_total_cash, 0)

                    return {
                        'cash': usd_total_cash,
                        'total_assets': usd_total_assets,
                        'available_cash': multi_currency['USD']['available_cash'],
                        'position_market_value': position_market_value,
                        'currency': 'USD',
                        'base_currency': base_currency,
                        'base_net_assets': base_net_assets,
                        'multi_currency': multi_currency
                    }
                else:
                    logger.warning("未获取到账户余额数据")
                    zero_balance = {
                        'cash': 0.00,
                        'total_assets': 0.00,
                        'available_cash': 0.00,
                        'position_market_value': 0.00,
                        'currency': 'USD',
                        'multi_currency': {
                            'USD': {'cash': 0.00, 'total_assets': 0.00, 'available_cash': 0.00,
                                    'position_market_value': 0.00},
                            'HKD': {'cash': 0.00, 'total_assets': 0.00, 'available_cash': 0.00,
                                    'position_market_value': 0.00},
                            'CNY': {'cash': 0.00, 'total_assets': 0.00, 'available_cash': 0.00,
                                    'position_market_value': 0.00}
                        }
                    }
                    return zero_balance
            except Exception as e:
                logger.error(f"获取账户余额失败: {str(e)}")
                zero_balance = {
                    'cash': 0.00,
                    'total_assets': 0.00,
                    'available_cash': 0.00,
                    'position_market_value': 0.00,
                    'currency': 'USD',
                    'multi_currency': {
                        'USD': {'cash': 0.00, 'total_assets': 0.00, 'available_cash': 0.00,
                                'position_market_value': 0.00},
                        'HKD': {'cash': 0.00, 'total_assets': 0.00, 'available_cash': 0.00,
                                'position_market_value': 0.00},
                        'CNY': {'cash': 0.00, 'total_assets': 0.00, 'available_cash': 0.00,
                                'position_market_value': 0.00}
                    }
                }
                return zero_balance
        else:
            zero_balance = {
                'cash': 0.00,
                'total_assets': 0.00,
                'available_cash': 0.00,
                'position_market_value': 0.00,
                'currency': 'USD',
                'multi_currency': {
                    'USD': {'cash': 0.00, 'total_assets': 0.00, 'available_cash': 0.00, 'position_market_value': 0.00},
                    'HKD': {'cash': 0.00, 'total_assets': 0.00, 'available_cash': 0.00, 'position_market_value': 0.00},
                    'CNY': {'cash': 0.00, 'total_assets': 0.00, 'available_cash': 0.00, 'position_market_value': 0.00}
                }
            }
            return zero_balance


print(LONGBRIDGE_CONFIG)
# 初始化长桥SDK（在startup中初始化）
longbridge_sdk = None


# 计算涨幅加速度
class AccelerationCalculator:
    def __init__(self):
        self.price_history = {}  # {symbol: [(timestamp, price, change_pct)]}

    def update_price(self, symbol: str, price: float, change_pct: float):
        """更新价格历史"""
        timestamp = datetime.now()
        if symbol not in self.price_history:
            self.price_history[symbol] = []

        self.price_history[symbol].append((timestamp, price, change_pct))

        # 只保留最近10个数据点
        if len(self.price_history[symbol]) > 10:
            self.price_history[symbol] = self.price_history[symbol][-10:]

    def calculate_acceleration(self, symbol: str) -> float:
        """计算涨幅加速度"""
        if symbol not in self.price_history or len(self.price_history[symbol]) < 3:
            return 0.0

        history = self.price_history[symbol]

        # 计算最近3个点的涨幅变化率
        recent_changes = [item[2] for item in history[-3:]]

        # 加速度 = (最新涨幅 - 前一涨幅) - (前一涨幅 - 前前涨幅)
        if len(recent_changes) >= 3:
            acceleration = (recent_changes[-1] - recent_changes[-2]) - (recent_changes[-2] - recent_changes[-3])
            return round(acceleration, 4)

        return 0.0


acceleration_calculator = AccelerationCalculator()


# 交易策略
class TradingStrategy:
    def __init__(self):
        self.profit_target = 1.0  # 1%止盈
        self.buy_amount = 200000.0  # 默认买入金额：20万美元
        self.max_concurrent_positions = 1  # 最大并发持仓数量，默认1
        self.positions_cache = {}  # 持仓缓存 {symbol: {quantity, avg_cost}}
        self.market_data_cache = {}  # 市场数据缓存

    async def update_positions_cache(self):
        """更新持仓缓存"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            cursor.execute("SELECT symbol, quantity, avg_cost FROM positions WHERE quantity > 0")
            positions = cursor.fetchall()
            cursor.close()
            conn.close()

            # 更新缓存
            self.positions_cache = {}
            for pos in positions:
                self.positions_cache[pos['symbol']] = {
                    'quantity': pos['quantity'],
                    'avg_cost': pos['avg_cost']
                }

            logger.debug(f"持仓缓存已更新，共{len(positions)}条持仓")
        except Exception as e:
            logger.error(f"更新持仓缓存失败: {str(e)}")

    async def _load_config(self, cursor):
        """加载交易策略配置"""
        try:
            # 从数据库加载配置
            cursor.execute(
                "SELECT config_key, config_value FROM system_config WHERE config_key IN ('profit_target', 'buy_amount', 'max_concurrent_positions')")
            configs = cursor.fetchall()

            config_dict = {item['config_key']: item['config_value'] for item in configs}

            # 更新配置
            if 'profit_target' in config_dict:
                self.profit_target = float(config_dict['profit_target'])
            if 'buy_amount' in config_dict:
                self.buy_amount = float(config_dict['buy_amount'])
            if 'max_concurrent_positions' in config_dict:
                self.max_concurrent_positions = int(config_dict['max_concurrent_positions'])

            logger.debug(
                f"配置已加载: profit_target={self.profit_target}%, buy_amount=${self.buy_amount:,.0f}, max_concurrent_positions={self.max_concurrent_positions}")
        except Exception as e:
            logger.warning(f"加载配置失败，使用默认值: {str(e)}")
            # 使用默认配置继续运行

    async def update_market_data_cache(self):
        """更新市场数据缓存"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            cursor.execute("SELECT symbol FROM stocks WHERE is_active = 1")
            stocks = cursor.fetchall()
            cursor.close()
            conn.close()

            if stocks:
                symbols = [stock['symbol'] for stock in stocks]
                quotes = await longbridge_sdk.get_realtime_quote(symbols)

                for quote in quotes:
                    self.market_data_cache[quote['symbol']] = quote

                logger.debug(f"市场数据缓存已更新，共{len(quotes)}条数据")
        except Exception as e:
            logger.error(f"更新市场数据缓存失败: {str(e)}")

    async def _check_and_execute_sell(self, symbol: str, quantity: int, entry_price: float):
        """检查并执行卖出操作（异步版本）"""
        try:
            # 获取当前价格
            if is_test_mode():
                current_price, _ = test_mode_price_manager.get_price(symbol)
            else:
                current_price = self.market_data_cache.get(symbol, {}).get('price', entry_price)

            profit_pct = ((current_price - entry_price) / entry_price) * 100

            if profit_pct >= self.profit_target:
                await self._execute_sell(symbol, quantity, entry_price, current_price, profit_pct)
        except Exception as e:
            logger.error(f"检查卖出条件失败: {str(e)}")

    async def handle_realtime_quote(self, symbol: str, quote: PushQuote):
        """处理实时行情推送（异步版本）"""
        try:
            # 如果不在持仓中，不处理
            if symbol not in self.positions_cache:
                return

            pos = self.positions_cache[symbol]
            quantity = int(pos['quantity'])
            entry_price = float(pos['avg_cost'])

            # 获取当前价格
            if is_test_mode():
                current_price, _ = test_mode_price_manager.get_price(symbol)
            else:
                current_price = float(quote.last_done)

            # 计算盈利
            profit_pct = ((current_price - entry_price) / entry_price) * 100

            logger.info(
                f"[实时推送] {symbol} 当前价格=${current_price:.2f}, 买入价=${entry_price:.2f}, 盈利={profit_pct:.2f}%, 目标={self.profit_target}%")

            # 检查是否达到止盈目标
            if profit_pct >= self.profit_target:
                await self._execute_sell(symbol, quantity, entry_price, current_price, profit_pct)

        except Exception as e:
            logger.error(f"处理实时行情失败: {str(e)}")

    async def _execute_sell(self, symbol: str, quantity: int, entry_price: float, current_price: float,
                            profit_pct: float):
        """执行卖出操作（异步版本）"""
        try:
            # 下单
            order_result = await longbridge_sdk.place_order(
                symbol,
                'SELL',
                quantity,
                current_price
            )

            # 记录交易
            conn = get_db_connection()
            cursor = conn.cursor(pymysql.cursors.DictCursor)

            cursor.execute("""
                INSERT INTO trades (symbol, action, price, quantity, amount, status, message)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                symbol,
                'SELL',
                current_price,
                quantity,
                current_price * quantity,
                order_result['status'],
                order_result['message']
            ))
            conn.commit()

            # 删除持仓
            cursor.execute("DELETE FROM positions WHERE symbol = %s", (symbol,))
            conn.commit()

            cursor.close()
            conn.close()

            # 更新缓存
            if symbol in self.positions_cache:
                del self.positions_cache[symbol]

            # 测试模式下重置价格
            if is_test_mode():
                test_mode_price_manager.reset_price(symbol)

            # 通知前端
            await notify_sse_clients('trade', {
                'type': 'SELL',
                'symbol': symbol,
                'quantity': quantity,
                'price': current_price,
                'amount': current_price * quantity,
                'profit_pct': profit_pct
            })

            logger.info(f"[实时卖出] {symbol} {quantity}股 @ ${current_price:.2f}, 盈利: {profit_pct:.2f}%")

        except Exception as e:
            logger.error(f"执行卖出失败: {str(e)}")

    async def check_and_trade(self):
        """检查并执行交易"""
        try:
            # 获取活跃正股列表（只选择正股，排除期权）
            conn = get_db_connection()
            cursor = conn.cursor(pymysql.cursors.DictCursor)

            # 加载配置
            await self._load_config(cursor)

            cursor.execute("SELECT symbol, name FROM stocks WHERE is_active = 1 AND stock_type = 'STOCK'")
            stocks = cursor.fetchall()

            if not stocks:
                logger.info("没有活跃的正股")
                return

            symbols = [stock['symbol'] for stock in stocks]

            # 获取实时行情
            quotes = await longbridge_sdk.get_realtime_quote(symbols)

            # 更新价格历史并计算加速度
            market_data = []
            for quote in quotes:
                symbol = quote['symbol']
                acceleration_calculator.update_price(symbol, quote['price'], quote['change_pct'])
                acceleration = acceleration_calculator.calculate_acceleration(symbol)

                market_data.append({
                    'symbol': symbol,
                    'price': quote['price'],
                    'change_pct': quote['change_pct'],
                    'acceleration': acceleration,
                    'volume': quote['volume'],
                    'timestamp': quote['timestamp']
                })

            # 获取当前持仓列表（排除已有持仓的股票）
            cursor.execute("SELECT symbol FROM positions WHERE quantity > 0")
            existing_positions = cursor.fetchall()
            existing_symbols = {pos['symbol'] for pos in existing_positions}
            current_position_count = len(existing_symbols)

            # 如果持仓数量小于最大并发数，可以买入
            if current_position_count < self.max_concurrent_positions:
                # 过滤掉已有持仓的股票
                available_stocks = [s for s in market_data if s['symbol'] not in existing_symbols]

                if available_stocks:
                    # 找出加速度最大的股票
                    best_stock = max(available_stocks, key=lambda x: x['acceleration'])

                    if best_stock['acceleration'] > 0:
                        # 使用固定金额购买
                        quantity = int(self.buy_amount / best_stock['price'])

                        if quantity > 0:
                            # 下单
                            order_result = await longbridge_sdk.place_order(
                                best_stock['symbol'],
                                'BUY',
                                quantity,
                                best_stock['price']
                            )

                            buy_amount = best_stock['price'] * quantity

                            # 记录交易
                            cursor.execute("""
                                INSERT INTO trades (symbol, action, price, quantity, amount, acceleration, status, message)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                            """, (
                                best_stock['symbol'],
                                'BUY',
                                best_stock['price'],
                                quantity,
                                buy_amount,
                                best_stock['acceleration'],
                                order_result['status'],
                                order_result['message']
                            ))
                            conn.commit()

                            # 更新持仓表（使用实际的表结构：avg_cost）
                            cursor.execute("""
                                INSERT INTO positions (symbol, quantity, avg_cost)
                                VALUES (%s, %s, %s)
                                ON DUPLICATE KEY UPDATE
                                quantity = VALUES(quantity),
                                avg_cost = VALUES(avg_cost)
                            """, (
                                best_stock['symbol'],
                                quantity,
                                best_stock['price']  # 使用买入价格作为平均成本
                            ))
                            conn.commit()

                            logger.info(
                                f"买入 {best_stock['symbol']} {quantity}股 @ ${best_stock['price']:.2f}, 金额: ${buy_amount:,.2f} (当前持仓: {current_position_count + 1}/{self.max_concurrent_positions})")

                            # 通知前端刷新账户总览
                            await notify_sse_clients('trade', {
                                'type': 'BUY',
                                'symbol': best_stock['symbol'],
                                'quantity': quantity,
                                'price': best_stock['price'],
                                'amount': buy_amount
                            })
                    else:
                        logger.info(
                            f"最佳股票 {best_stock['symbol']} 加速度为 {best_stock['acceleration']}，不满足买入条件")
                else:
                    logger.info(
                        f"没有可买入的股票（持仓数: {current_position_count}/{self.max_concurrent_positions}，或无可用股票）")
            else:
                logger.info(f"已达到最大持仓数量 ({current_position_count}/{self.max_concurrent_positions})，跳过买入")

            # 检查所有持仓是否达到止盈目标
            if existing_positions:
                # 获取所有持仓的详细信息
                cursor.execute("SELECT symbol, quantity, avg_cost FROM positions WHERE quantity > 0")
                all_positions = cursor.fetchall()

                for pos in all_positions:
                    symbol = pos['symbol']
                    quantity = int(pos['quantity'])
                    entry_price = float(pos['avg_cost'])

                    # 在测试模式下，从测试模式价格管理器获取当前价格
                    # 否则从市场数据中获取当前价格
                    if is_test_mode():
                        test_price, test_change_pct = test_mode_price_manager.get_price(symbol)
                        current_price = test_price
                    else:
                        # 从市场数据中获取当前价格
                        current_stock = next((s for s in market_data if s['symbol'] == symbol), None)
                        if not current_stock:
                            continue
                        current_price = current_stock['price']

                    profit_pct = ((current_price - entry_price) / entry_price) * 100

                    logger.info(
                        f"检查卖出条件: {symbol} 当前价格=${current_price:.2f}, 买入价格=${entry_price:.2f}, 盈利={profit_pct:.2f}%, 目标={self.profit_target}%")

                    if profit_pct >= self.profit_target:
                        # 卖出
                        order_result = await longbridge_sdk.place_order(
                            symbol,
                            'SELL',
                            quantity,
                            current_price
                        )

                        # 记录交易
                        cursor.execute("""
                                INSERT INTO trades (symbol, action, price, quantity, amount, status, message)
                                VALUES (%s, %s, %s, %s, %s, %s, %s)
                            """, (
                            symbol,
                            'SELL',
                            current_price,
                            quantity,
                            current_price * quantity,
                            order_result['status'],
                            order_result['message']
                        ))
                        conn.commit()

                        logger.info(f"卖出 {symbol} {quantity}股 @ ${current_price:.2f}, 盈利: {profit_pct:.2f}%")

                        # 删除持仓表中的记录
                        cursor.execute("DELETE FROM positions WHERE symbol = %s", (symbol,))
                        conn.commit()

                        # 重置测试模式价格（卖出后重置价格趋势）
                        if is_test_mode():
                            test_mode_price_manager.reset_price(symbol)

                        # 通知前端刷新账户总览
                        await notify_sse_clients('trade', {
                            'type': 'SELL',
                            'symbol': symbol,
                            'quantity': quantity,
                            'price': current_price,
                            'amount': current_price * quantity
                        })

                        # 只处理第一个达到止盈的持仓，避免一次循环中卖出多个
                        break

            cursor.close()
            conn.close()

        except Exception as e:
            logger.error(f"交易检查出错: {str(e)}")


trading_strategy = TradingStrategy()


# 应用性能监控到关键函数
@async_performance_monitor("监控循环")
async def monitoring_loop():
    """监控循环 - 使用异步任务队列优化性能"""
    global is_monitoring

    # 启动异步任务队列
    await task_queue.start()

    # 订阅实时行情回调（仅真实模式使用）
    def on_quote_update(symbol: str, quote: PushQuote):
        """实时行情回调"""
        # 将实时行情处理放入任务队列
        asyncio.create_task(task_queue.add_task(trading_strategy.handle_realtime_quote, symbol, quote))

    # 初始化检查时间
    last_buy_check_time = datetime.now()
    last_position_update_time = datetime.now()
    last_market_data_update = datetime.now()

    try:
        while is_monitoring:
            current_time = datetime.now()

            # 1. 更新持仓缓存（每60秒更新一次，避免频繁数据库查询）
            if (current_time - last_position_update_time).total_seconds() >= 60:
                # 将持仓更新放入任务队列
                await task_queue.add_task(trading_strategy.update_positions_cache)
                last_position_update_time = current_time

            # 2. 获取市场数据（每30秒更新一次）
            if (current_time - last_market_data_update).total_seconds() >= 30:
                # 将市场数据获取放入任务队列
                await task_queue.add_task(trading_strategy.update_market_data_cache)
                last_market_data_update = current_time

            # 获取所有持仓的股票代码
            position_symbols = list(trading_strategy.positions_cache.keys())

            if is_test_mode():
                # 测试模式：使用任务队列处理卖出检查
                for symbol in position_symbols:
                    if symbol not in trading_strategy.positions_cache:
                        continue

                    pos = trading_strategy.positions_cache[symbol]
                    quantity = int(pos['quantity'])
                    entry_price = float(pos['avg_cost'])

                    # 将卖出检查放入任务队列
                    await task_queue.add_task(
                        trading_strategy._check_and_execute_sell,
                        symbol, quantity, entry_price
                    )

                # 执行买入策略（每15秒检查一次）
                if (current_time - last_buy_check_time).total_seconds() >= 15:
                    await task_queue.add_task(trading_strategy.check_and_trade)
                    last_buy_check_time = current_time

                # 短暂等待，让出CPU时间
                await asyncio.sleep(0.5)
            else:
                # 真实模式：使用WebSocket实时推送
                # 订阅持仓股票的实时行情
                if position_symbols:
                    longbridge_sdk.subscribe_realtime_quotes(position_symbols, on_quote_update)

                # 执行买入策略（每45秒检查一次）
                if (current_time - last_buy_check_time).total_seconds() >= 45:
                    await task_queue.add_task(trading_strategy.check_and_trade)
                    last_buy_check_time = current_time

                # 等待一段时间再检查买入机会
                await asyncio.sleep(2)

    except Exception as e:
        logger.error(f"监控循环出错: {str(e)}")
    finally:
        # 取消订阅并停止任务队列
        if position_symbols and not is_test_mode():
            longbridge_sdk.unsubscribe_realtime_quotes(position_symbols)
        await task_queue.stop()


# 生命周期管理
try:
    from contextlib import asynccontextmanager
except ImportError:
    # Python 3.6 不支持 asynccontextmanager，使用老式方法
    asynccontextmanager = None

if asynccontextmanager:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # 确保系统配置存在默认值
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

        # 启动时初始化SDK
        global longbridge_sdk
        if longbridge_sdk is None:
            longbridge_sdk = LongBridgeSDK(LONGBRIDGE_CONFIG)
        await longbridge_sdk.connect()

        # 启动异步任务队列
        await task_queue.start()

        yield

        # 关闭时
        global is_monitoring
        is_monitoring = False

        # 停止任务队列
        await task_queue.stop()
else:
    # Python 3.6 使用 startup/shutdown 事件
    lifespan = None

async def lifespan_python36():
    # 确保系统配置存在默认值
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

    # 启动时初始化SDK
    global longbridge_sdk
    if longbridge_sdk is None:
        longbridge_sdk = LongBridgeSDK(LONGBRIDGE_CONFIG)
    await longbridge_sdk.connect()

    # 启动异步任务队列
    await task_queue.start()

async def lifespan_python36_shutdown():
    global is_monitoring
    is_monitoring = False
    await task_queue.stop()
    # 确保系统配置存在默认值
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

    # 启动时初始化SDK
    global longbridge_sdk
    if longbridge_sdk is None:
        longbridge_sdk = LongBridgeSDK(LONGBRIDGE_CONFIG)
    await longbridge_sdk.connect()

    # 启动异步任务队列
    await task_queue.start()

    yield

    # 关闭时
    global is_monitoring

    is_monitoring = False

    # 停止任务队列
    await task_queue.stop()


# 创建FastAPI应用
if lifespan:
    app = FastAPI(title="美股量化交易系统", lifespan=lifespan)
else:
    app = FastAPI(title="美股量化交易系统")
    # Python 3.6 使用启动/关闭事件
    @app.on_event("startup")
    async def startup_event():
        global longbridge_sdk
        if longbridge_sdk is None:
            longbridge_sdk = LongBridgeSDK(LONGBRIDGE_CONFIG)
        await longbridge_sdk.connect()
        await task_queue.start()

    @app.on_event("shutdown")
    async def shutdown_event():
        global is_monitoring
        is_monitoring = False
        await task_queue.stop()

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# API路由

@app.get("/")
async def root():
    """根路径重定向到静态页面"""
    return RedirectResponse(url="/static/index.html")


# ==================== 认证 API ====================

class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    username: str
    password: str
    email: Optional[str] = None


@app.post("/api/auth/register")
async def register(request: RegisterRequest):
    """用户注册"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        # 检查用户名是否已存在
        cursor.execute("SELECT id FROM users WHERE username = %s", (request.username,))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            raise HTTPException(status_code=400, detail="用户名已存在")

        # 检查邮箱是否已存在（如果提供了邮箱）
        if request.email:
            cursor.execute("SELECT id FROM users WHERE email = %s", (request.email,))
            if cursor.fetchone():
                cursor.close()
                conn.close()
                raise HTTPException(status_code=400, detail="邮箱已被使用")

        # 创建新用户
        hashed_password = get_password_hash(request.password)
        cursor.execute(
            "INSERT INTO users (username, password, email, is_active, created_at) VALUES (%s, %s, %s, %s, NOW())",
            (request.username, hashed_password, request.email, True)
        )
        user_id = cursor.lastrowid
        conn.commit()
        cursor.close()
        conn.close()

        return {
            "code": 0,
            "message": "注册成功",
            "data": {"user_id": user_id, "username": request.username}
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"注册失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/auth/login")
async def login(request: LoginRequest, response: Response):
    """用户登录"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        # 查找用户
        cursor.execute("SELECT * FROM users WHERE username = %s", (request.username,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if not user:
            raise HTTPException(status_code=401, detail="用户名或密码错误")

        # 验证密码
        if not verify_password(request.password, user['password']):
            raise HTTPException(status_code=401, detail="用户名或密码错误")

        # 检查用户是否激活
        if not user['is_active']:
            raise HTTPException(status_code=400, detail="用户已被禁用")

        # 创建访问令牌
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user['username'], "user_id": user['id']},
            expires_delta=access_token_expires
        )

        # 创建刷新令牌
        refresh_token = create_refresh_token()

        # 保存刷新令牌到数据库
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO refresh_tokens (user_id, token, expires_at) VALUES (%s, %s, DATE_ADD(NOW(), INTERVAL %s DAY))",
            (user['id'], refresh_token, REFRESH_TOKEN_EXPIRE_DAYS)
        )
        conn.commit()
        cursor.close()
        conn.close()

        # 设置Cookie
        response = JSONResponse(content={
            "code": 0,
            "message": "登录成功",
            "data": {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "Bearer",
                "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                "user": {
                    "id": user['id'],
                    "username": user['username'],
                    "email": user.get('email')
                }
            }
        })

        # 设置HTTP-only Cookie
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            path="/",
            samesite="lax"
        )

        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
            path="/",
            samesite="lax"
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"登录失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/auth/logout")
async def logout(response: Response, current_user: dict = Depends(get_current_user)):
    """用户登出"""
    try:
        # 清除刷新令牌
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM refresh_tokens WHERE user_id = %s",
            (current_user['id'],)
        )
        conn.commit()
        cursor.close()
        conn.close()

        # 清除Cookie
        response.delete_cookie(key="access_token", path="/")
        response.delete_cookie(key="refresh_token", path="/")

        return {"code": 0, "message": "登出成功"}
    except Exception as e:
        logger.error(f"登出失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/auth/refresh")
async def refresh_token(request: Request, response: Response):
    """刷新访问令牌"""
    try:
        # 从Cookie获取刷新令牌
        refresh_token = request.cookies.get("refresh_token")
        if not refresh_token:
            raise HTTPException(status_code=401, detail="未提供刷新令牌")

        # 验证刷新令牌
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute(
            """SELECT rt.*, u.id, u.username, u.is_active
               FROM refresh_tokens rt
               JOIN users u ON rt.user_id = u.id
               WHERE rt.token = %s AND rt.expires_at > NOW()""",
            (refresh_token,)
        )
        token_record = cursor.fetchone()
        cursor.close()
        conn.close()

        if not token_record:
            raise HTTPException(status_code=401, detail="刷新令牌无效或已过期")

        # 检查用户是否激活
        if not token_record['is_active']:
            raise HTTPException(status_code=400, detail="用户已被禁用")

        # 创建新的访问令牌
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": token_record['username'], "user_id": token_record['id']},
            expires_delta=access_token_expires
        )

        # 设置新的访问令牌Cookie
        response = JSONResponse(content={
            "code": 0,
            "message": "令牌刷新成功",
            "data": {
                "access_token": access_token,
                "token_type": "Bearer",
                "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60
            }
        })

        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            path="/",
            samesite="lax"
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"刷新令牌失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/auth/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    """获取当前用户信息"""
    return {
        "code": 0,
        "data": current_user
    }


class WeChatLoginRequest(BaseModel):
    """微信登录请求"""
    code: str  # 微信授权code


@app.post("/api/auth/wechat-login")
async def wechat_login(request: WeChatLoginRequest, response: Response):
    """微信登录"""
    try:
        if not WECHAT_CONFIG['enabled'] or not WECHAT_CONFIG['app_id'] or not WECHAT_CONFIG['app_secret']:
            raise HTTPException(status_code=400, detail="微信登录未配置或未启用")

        # TODO: 实现微信登录逻辑
        # 1. 使用code换取access_token
        # 2. 获取用户信息
        # 3. 查找或创建用户
        # 4. 返回登录令牌

        raise HTTPException(status_code=501, detail="微信登录功能待实现，请配置WECHAT_APP_ID和WECHAT_APP_SECRET")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"微信登录失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stocks")
async def get_stocks(current_user: dict = Depends(get_current_user)):
    """获取股票列表"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute("SELECT * FROM stocks ORDER BY group_order, id")
        stocks = cursor.fetchall()
        cursor.close()
        conn.close()
        return {"code": 0, "data": stocks}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/stocks")
async def add_stock(stock: Stock, current_user: dict = Depends(get_current_user)):
    """添加股票"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 获取或计算分组信息
        group_name = getattr(stock, 'group_name', '未分组') or '未分组'
        stock_type = getattr(stock, 'stock_type', 'STOCK') or 'STOCK'
        group_order = 0

        # 查询该分组是否已有股票，获取其order
        cursor.execute("SELECT group_order FROM stocks WHERE group_name = %s LIMIT 1", (group_name,))
        result = cursor.fetchone()
        if result:
            group_order = result[0]
        else:
            # 新分组，查找最大的group_order
            cursor.execute("SELECT MAX(group_order) FROM stocks")
            max_order = cursor.fetchone()
            group_order = (max_order[0] if max_order[0] else 0) + 1

        cursor.execute(
            "INSERT INTO stocks (symbol, name, group_name, group_order, stock_type, is_active) VALUES (%s, %s, %s, %s, %s, %s)",
            (stock.symbol, stock.name, group_name, group_order, stock_type, stock.is_active)
        )
        conn.commit()
        stock_id = cursor.lastrowid
        cursor.close()
        conn.close()
        return {"code": 0, "message": "添加成功", "data": {"id": stock_id}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/stocks/{stock_id}")
async def delete_stock(stock_id: int, current_user: dict = Depends(get_current_user)):
    """删除股票"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM stocks WHERE id = %s", (stock_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return {"code": 0, "message": "删除成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/stocks/{stock_id}/toggle")
async def toggle_stock(stock_id: int, current_user: dict = Depends(get_current_user)):
    """切换股票激活状态"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE stocks SET is_active = 1 - is_active WHERE id = %s", (stock_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return {"code": 0, "message": "状态已更新"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 为关键API添加性能监控
@async_performance_monitor("获取市场数据")
@app.get("/api/market-data")
async def get_market_data(current_user: dict = Depends(get_current_user)):
    """获取实时市场数据"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute("SELECT symbol FROM stocks WHERE is_active = 1")
        stocks = cursor.fetchall()
        cursor.close()
        conn.close()

        if not stocks:
            return {"code": 0, "data": []}

        symbols = [stock['symbol'] for stock in stocks]
        quotes = await longbridge_sdk.get_realtime_quote(symbols)

        market_data = []
        for quote in quotes:
            symbol = quote['symbol']
            acceleration_calculator.update_price(symbol, quote['price'], quote['change_pct'])
            acceleration = acceleration_calculator.calculate_acceleration(symbol)

            market_data.append({
                'symbol': symbol,
                'price': quote['price'],
                'change_pct': quote['change_pct'],
                'acceleration': acceleration,
                'volume': quote['volume'],
                'timestamp': quote['timestamp']
            })

        return {"code": 0, "data": market_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/trades")
async def get_trades(limit: int = 50, current_user: dict = Depends(get_current_user)):
    """获取交易记录"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute("SELECT * FROM trades ORDER BY trade_time DESC LIMIT %s", (limit,))
        trades = cursor.fetchall()
        cursor.close()
        conn.close()
        return {"code": 0, "data": trades}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/orders")
async def get_orders(
        symbol: Optional[str] = None,
        days: Optional[int] = 90,
        limit: int = 50,
        current_user: dict = Depends(get_current_user)
):
    """获取历史订单

    参数:
        symbol: 股票代码，可选
        days: 查询最近几天的订单，默认90天
        limit: 返回数量限制，默认50条
    """
    try:
        logger.info(f"获取历史订单: symbol={symbol}, days={days}, limit={limit}")
        orders = await longbridge_sdk.get_history_orders(symbol=symbol, days=days, limit=limit)
        return {
            "code": 0,
            "data": orders,
            "total": len(orders),
            "message": f"成功获取 {len(orders)} 条订单记录"
        }
    except Exception as e:
        logger.error(f"获取历史订单失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stock/history/{symbol}")
async def get_stock_history(symbol: str, period: str = '1d', count: int = 200, current_user: dict = Depends(get_current_user)):
    """获取股票历史K线数据

    参数:
        symbol: 股票代码（如 AAPL）
        period: 周期 (1d=日K, 1w=周K, 1M=月K)
        count: 返回条数
    """
    try:
        if not longbridge_sdk.use_real_sdk or not longbridge_sdk.quote_ctx:
            # 模拟数据
            from datetime import timedelta
            import random

            history = []
            base_date = datetime.now() - timedelta(days=count)
            base_price = 150.0

            for i in range(count):
                date = base_date + timedelta(days=i)
                # 模拟生成OHLCV数据
                open_price = base_price + random.uniform(-5, 5)
                high_price = max(open_price, base_price + random.uniform(0, 10))
                low_price = min(open_price, base_price - random.uniform(0, 10))
                close_price = base_price + random.uniform(-5, 5)
                volume = random.randint(1000000, 50000000)

                history.append({
                    'timestamp': date.isoformat(),
                    'open': round(open_price, 2),
                    'high': round(high_price, 2),
                    'low': round(low_price, 2),
                    'close': round(close_price, 2),
                    'volume': volume
                })

                base_price = close_price

            return {"code": 0, "data": history, "symbol": symbol, "period": period}

        # 使用真实SDK获取K线数据
        from longbridge.openapi import Period, AdjustType

        # 映射周期
        period_map = {
            '1d': Period.Day,
            '1w': Period.Week,
            '1M': Period.Month
        }

        lb_period = period_map.get(period, Period.Day)

        try:
            # 获取K线数据，兼容不同版本SDK
            candles = None
            symbol_with_market = f"{symbol}.US"

            if hasattr(longbridge_sdk.quote_ctx, 'candlesticks_by_date'):
                candles = longbridge_sdk.quote_ctx.candlesticks_by_date(
                    symbol=symbol_with_market,
                    period=lb_period,
                    adjust_type=AdjustType.NoAdjust,
                    count=count
                )
            elif hasattr(longbridge_sdk.quote_ctx, 'candlesticks'):
                candles = longbridge_sdk.quote_ctx.candlesticks(
                    symbol=symbol_with_market,
                    period=lb_period,
                    adjust_type=AdjustType.NoAdjust,
                    count=count
                )
            else:
                raise AttributeError('当前QuoteContext缺少K线查询方法')

            history = []
            for candle in candles or []:
                timestamp = getattr(candle, 'timestamp', None) or getattr(candle, 'time', None) or datetime.now()
                timestamp_str = timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp)

                history.append({
                    'timestamp': timestamp_str,
                    'open': float(getattr(candle, 'open', 0.0)),
                    'high': float(getattr(candle, 'high', 0.0)),
                    'low': float(getattr(candle, 'low', 0.0)),
                    'close': float(getattr(candle, 'close', 0.0)),
                    'volume': int(getattr(candle, 'volume', 0))
                })

            return {"code": 0, "data": history, "symbol": symbol, "period": period}

        except Exception as e:
            logger.warning(f"获取K线数据失败，使用模拟数据: {e}")
            # 降级到模拟数据
            from datetime import timedelta
            import random

            history = []
            base_date = datetime.now() - timedelta(days=count)
            base_price = 150.0

            for i in range(count):
                date = base_date + timedelta(days=i)
                open_price = base_price + random.uniform(-5, 5)
                high_price = max(open_price, base_price + random.uniform(0, 10))
                low_price = min(open_price, base_price - random.uniform(0, 10))
                close_price = base_price + random.uniform(-5, 5)
                volume = random.randint(1000000, 50000000)

                history.append({
                    'timestamp': date.isoformat(),
                    'open': round(open_price, 2),
                    'high': round(high_price, 2),
                    'low': round(low_price, 2),
                    'close': round(close_price, 2),
                    'volume': volume
                })

                base_price = close_price

            return {"code": 0, "data": history, "symbol": symbol, "period": period}

    except Exception as e:
        logger.error(f"获取股票历史数据失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


# 为关键API添加性能监控
@async_performance_monitor("获取持仓信息")
@app.get("/api/positions")
async def get_positions(current_user: dict = Depends(get_current_user)):
    """获取持仓信息"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute("SELECT * FROM positions WHERE quantity > 0")
        positions = cursor.fetchall()
        cursor.close()
        conn.close()
        return {"code": 0, "data": positions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/events")
async def events_stream(request: Request):
    """SSE 事件流 - 实时推送交易和持仓更新"""

    # 可选的token验证
    token = request.query_params.get("token")
    if token:
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username = payload.get("sub")
            if not username:
                return Response(status_code=401)
        except JWTError:
            return Response(status_code=401)

    async def event_generator():
        queue = asyncio.Queue()

        sse_clients.add(queue)

        try:
            # 发送初始连接消息
            yield f"event: connected\ndata: {json.dumps({'status': 'connected'})}\n\n"

            while True:
                message = await queue.get()
                yield message
        except asyncio.CancelledError:
            pass
        finally:
            sse_clients.remove(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# 为关键API添加性能监控
@async_performance_monitor("获取账户总览")
@app.get("/api/portfolio")
async def get_portfolio(current_user: dict = Depends(get_current_user)):
    """获取账户总览"""
    try:
        # 检查是否处于测试模式
        is_test = is_test_mode()

        # 获取账户余额
        balance = await longbridge_sdk.get_account_balance()
        available_cash = balance.get('available_cash', balance.get('cash', 0.00))
        sdk_total_assets = balance.get('total_assets')
        sdk_position_market_value = balance.get('position_market_value')
        multi_currency = balance.get('multi_currency', {})

        # 获取持仓列表（根据测试模式过滤）
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        if is_test:
            cursor.execute("SELECT * FROM positions WHERE quantity > 0 AND test_mode = 0")
        else:
            cursor.execute("SELECT * FROM positions WHERE quantity > 0 AND test_mode = 1")
        positions = cursor.fetchall()

        # 获取市场数据
        cursor.execute("SELECT symbol FROM stocks WHERE is_active = 1")
        active_stocks = cursor.fetchall()
        cursor.close()
        conn.close()

        # 获取实时行情
        symbols = [s['symbol'] for s in active_stocks]
        market_data = {}
        if symbols:
            quotes = await longbridge_sdk.get_realtime_quote(symbols)
            market_data = {q['symbol']: q for q in quotes}

        # 计算持仓市值和盈亏（遍历所有持仓，累计计算）
        position_market_value = 0
        position_profit_loss = 0
        position_details = []

        for pos in positions:
            symbol = pos['symbol']
            quantity = int(pos['quantity']) if pos['quantity'] else 0

            # 兼容旧表字段：优先 buy_price，其次 avg_cost，再退回 current_price
            buy_price = float(pos.get('buy_price') or pos.get('avg_cost') or 0)

            # 获取当前价格
            current_price = pos.get('current_price')
            if not current_price and symbol in market_data:
                current_price = market_data[symbol]['price']

            # 如果还拿不到当前价，退回买入价，避免 None 导致盈亏为 0
            if not current_price:
                current_price = buy_price

            # 成本：表里有 cost 用 cost，否则用买入价 * 数量
            cost = pos.get('cost')
            if cost is None:
                cost = buy_price * quantity
            else:
                cost = float(cost)

            # 市值与盈亏计算
            current_price = float(current_price) if current_price else 0.0
            market_value = current_price * quantity if current_price else cost
            ref_buy_price = buy_price or current_price or 0
            profit_loss = (current_price - ref_buy_price) * quantity if ref_buy_price and quantity > 0 else 0
            profit_loss_pct = ((
                                           current_price - ref_buy_price) / ref_buy_price) * 100 if ref_buy_price and ref_buy_price > 0 else 0

            # 累计所有持仓的市值和盈亏
            position_market_value += market_value
            position_profit_loss += profit_loss

            position_details.append({
                'symbol': symbol,
                'quantity': quantity,
                'cost': cost,
                'buy_price': ref_buy_price,
                'current_price': current_price,
                'market_value': market_value,
                'profit_loss': profit_loss,
                'profit_loss_pct': profit_loss_pct
            })

        # 计算当日盈亏
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        today = datetime.now().date()

        # 获取今日交易汇总（根据测试模式过滤）
        if is_test:
            cursor.execute("""
                SELECT action, SUM(amount) as total_amount, COUNT(*) as count
                FROM trades
                WHERE DATE(trade_time) = %s AND test_mode = 0
                GROUP BY action
            """, (today,))
        else:
            cursor.execute("""
                SELECT action, SUM(amount) as total_amount, COUNT(*) as count
                FROM trades
                WHERE DATE(trade_time) = %s AND test_mode = 1
                GROUP BY action
            """, (today,))
        today_trades = cursor.fetchall()

        # 计算当日已实现的盈亏（卖出时的盈利）
        # 查询当日所有卖出交易，计算卖出盈亏（根据测试模式过滤）
        if is_test:
            cursor.execute("""
                SELECT 
                    t.symbol,
                    t.price as sell_price,
                    t.quantity as sell_quantity,
                    t.amount as sell_amount,
                    COALESCE(p.avg_cost, 
                        (SELECT AVG(price) FROM trades WHERE symbol = t.symbol AND action = 'BUY' AND DATE(trade_time) <= %s AND test_mode = 0)
                    ) as buy_price
                FROM trades t
                LEFT JOIN positions p ON t.symbol = p.symbol
                WHERE DATE(t.trade_time) = %s AND t.action = 'SELL' AND t.test_mode = 0
            """, (today, today))
        else:
            cursor.execute("""
                SELECT 
                    t.symbol,
                    t.price as sell_price,
                    t.quantity as sell_quantity,
                    t.amount as sell_amount,
                    COALESCE(p.avg_cost, 
                        (SELECT AVG(price) FROM trades WHERE symbol = t.symbol AND action = 'BUY' AND DATE(trade_time) <= %s AND test_mode = 1)
                    ) as buy_price
                FROM trades t
                LEFT JOIN positions p ON t.symbol = p.symbol
                WHERE DATE(t.trade_time) = %s AND t.action = 'SELL' AND t.test_mode = 1
            """, (today, today))
        sell_trades = cursor.fetchall()

        daily_realized_profit = 0.0
        for sell_trade in sell_trades:
            sell_price = float(sell_trade['sell_price'])
            sell_quantity = int(sell_trade['sell_quantity'])
            buy_price = float(sell_trade['buy_price']) if sell_trade['buy_price'] else sell_price

            # 计算该笔卖出的盈亏
            profit = (sell_price - buy_price) * sell_quantity
            daily_realized_profit += profit

        cursor.close()
        conn.close()

        # 当日盈亏 = 当日已实现的盈亏（卖出时的盈利）
        # 持仓盈亏 = 所有持仓的浮盈（已单独计算）
        daily_profit_loss = daily_realized_profit
        denominator = available_cash + position_market_value
        daily_profit_loss_pct = (daily_profit_loss / denominator) * 100 if denominator > 0 else 0

        # 汇总今日交易
        today_trade_count = sum(t['count'] for t in today_trades)
        today_buy_count = sum(t['count'] for t in today_trades if t['action'] == 'BUY')
        today_sell_count = sum(t['count'] for t in today_trades if t['action'] == 'SELL')
        today_trade_volume = sum(t['total_amount'] for t in today_trades)

        final_total_assets = available_cash + position_market_value
        final_position_market_value = position_market_value

        # 如果拿到了长桥返回的总资产，则优先使用官方口径，避免本地持仓数据偏差
        if sdk_total_assets is not None and longbridge_sdk.use_real_sdk:
            final_total_assets = sdk_total_assets
            if sdk_position_market_value is not None:
                final_position_market_value = sdk_position_market_value
            else:
                final_position_market_value = max(final_total_assets - available_cash, 0)
        else:
            # 测试模式或无SDK数据时，直接使用get_account_balance返回的值
            # 因为get_account_balance已经通过交易记录正确计算了现金
            if sdk_total_assets is not None:
                final_total_assets = sdk_total_assets
            else:
                final_total_assets = available_cash + position_market_value
            if sdk_position_market_value is not None:
                final_position_market_value = sdk_position_market_value
            else:
                final_position_market_value = position_market_value

        total_profit_loss = position_profit_loss
        total_profit_loss_pct = (total_profit_loss / final_total_assets) * 100 if final_total_assets > 0 else 0

        # 计算多币种资产
        multi_currency_assets = {}
        for currency, currency_data in multi_currency.items():
            mc_cash = currency_data.get('available_cash', 0)
            # 使用本地计算的最终市值和总资产，而不是直接使用 multi_currency 中的数据
            mc_total = convert_currency(final_total_assets, 'USD', currency)
            mc_position_mv = convert_currency(final_position_market_value, 'USD', currency)
            mc_profit = convert_currency(position_profit_loss, 'USD', currency)

            multi_currency_assets[currency] = {
                'total_assets': mc_total,
                'available_cash': mc_cash,
                'position_market_value': mc_position_mv,
                'position_profit_loss': mc_profit,
                'position_profit_loss_pct': total_profit_loss_pct,
                'daily_profit_loss': mc_profit,
                'daily_profit_loss_pct': daily_profit_loss_pct
            }

        return {
            "code": 0,
            "data": {
                'currency': 'USD',
                'total_assets': final_total_assets,
                'available_cash': available_cash,
                'position_market_value': final_position_market_value,
                'position_profit_loss': position_profit_loss,
                'position_profit_loss_pct': total_profit_loss_pct,
                'daily_profit_loss': daily_profit_loss,
                'daily_profit_loss_pct': daily_profit_loss_pct,
                'positions': position_details,
                'today_trades': {
                    'count': today_trade_count,
                    'buy_count': today_buy_count,
                    'sell_count': today_sell_count,
                    'volume': today_trade_volume
                },
                'multi_currency': multi_currency_assets
            }
        }
    except Exception as e:
        logger.error(f"获取账户总览失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/config")
async def get_config(current_user: dict = Depends(get_current_user)):
    """获取系统配置（包含默认值和字段定义）"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute("SELECT config_key, config_value, description FROM system_config")
        configs = cursor.fetchall()

        existing_keys = [item['config_key'] for item in configs]
        if ensure_default_system_configs(cursor, existing_keys):
            conn.commit()
            cursor.execute("SELECT config_key, config_value, description FROM system_config")
            configs = cursor.fetchall()

        cursor.close()
        conn.close()

        config_dict = {item['config_key']: item['config_value'] for item in configs}
        return {
            "code": 0,
            "data": {
                "values": config_dict,
                "definitions": CONFIG_DEFINITIONS,
                "defaults": {key: meta['value'] for key, meta in DEFAULT_SYSTEM_CONFIGS.items()}
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/config")
async def update_config(config: SystemConfig, current_user: dict = Depends(get_current_user)):
    """更新系统配置"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE system_config SET config_value = %s WHERE config_key = %s",
            (config.config_value, config.config_key)
        )

        # 如果配置不存在则创建（便于在前端新增入口时直接提交）
        if cursor.rowcount == 0:
            cursor.execute(
                "INSERT INTO system_config (config_key, config_value, description) VALUES (%s, %s, %s)",
                (config.config_key, config.config_value, config.description or '')
            )

        conn.commit()
        cursor.close()
        conn.close()

        # 更新交易策略的配置（金额默认以美元计）
        if config.config_key == 'profit_target':
            trading_strategy.profit_target = float(config.config_value)
        elif config.config_key == 'buy_amount':
            trading_strategy.buy_amount = float(config.config_value)
        elif config.config_key == 'max_concurrent_positions':
            trading_strategy.max_concurrent_positions = int(config.config_value)

        return {"code": 0, "message": "配置已更新"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/monitoring/start")
async def start_monitoring(request: dict = None):
    """启动监控"""
    global is_monitoring, monitoring_task

    if is_monitoring:
        return {"code": 1, "message": "监控已在运行中"}

    is_monitoring = True

    # 如果传入了buy_amount参数，更新配置
    if request and 'buy_amount' in request:
        try:
            buy_amount_value = float(request['buy_amount'])

            # 验证买入金额范围
            if buy_amount_value < 1000:
                return {"code": 1, "message": "买入金额必须大于等于1000美元"}
            if buy_amount_value > 1000000:
                return {"code": 1, "message": "买入金额不能超过100万美元"}

            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE system_config SET config_value = %s WHERE config_key = 'buy_amount'",
                (str(buy_amount_value),)
            )
            conn.commit()
            cursor.close()
            conn.close()

            # 更新交易策略的配置
            trading_strategy.buy_amount = buy_amount_value
            logger.info(f"启动监控时更新单笔买入金额为: ${buy_amount_value:,.0f}")
        except Exception as e:
            logger.error(f"更新买入金额失败: {str(e)}")
            return {"code": 1, "message": f"更新买入金额失败: {str(e)}"}

    # 使用任务队列启动监控循环
    monitoring_task = asyncio.create_task(monitoring_loop())

    return {"code": 0, "message": "监控已启动"}


@app.post("/api/monitoring/stop")
async def stop_monitoring(current_user: dict = Depends(get_current_user)):
    """停止监控"""
    global is_monitoring

    if not is_monitoring:
        return {"code": 1, "message": "监控未运行"}

    is_monitoring = False

    return {"code": 0, "message": "监控已停止"}


@app.get("/api/monitoring/status")
async def get_monitoring_status():
    """获取监控状态"""
    test_mode = is_test_mode()
    mode_text = "测试模式" if test_mode else ("真实模式" if longbridge_sdk.use_real_sdk else "模拟模式")

    # 获取当前持仓数量
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as cnt FROM positions WHERE quantity > 0")
    position_count_result = cursor.fetchone()
    cursor.close()
    conn.close()
    current_position_count = position_count_result[0] if position_count_result else 0

    return {
        "code": 0,
        "data": {
            "is_monitoring": is_monitoring,
            "current_position_count": current_position_count,
            "max_concurrent_positions": trading_strategy.max_concurrent_positions,
            "sdk_mode": mode_text,
            "sdk_connected": longbridge_sdk.is_connected,
            "test_mode": test_mode,
            "task_queue_running": task_queue.is_running,
            "task_queue_size": task_queue.queue.qsize() if task_queue.is_running else 0
        }
    }


@app.get("/api/longbridge/config")
async def get_longbridge_config(current_user: dict = Depends(get_current_user)):
    """获取长桥配置（隐藏敏感信息）"""
    return {
        "code": 0,
        "data": {
            "app_key": LONGBRIDGE_CONFIG['app_key'][:8] + "..." if LONGBRIDGE_CONFIG['app_key'] else "",
            "app_secret": "***" if LONGBRIDGE_CONFIG['app_secret'] else "",
            "access_token": "***" if LONGBRIDGE_CONFIG['access_token'] else "",
            "http_url": LONGBRIDGE_CONFIG.get('http_url', ''),
            "quote_ws_url": LONGBRIDGE_CONFIG.get('quote_ws_url', ''),
            "trade_ws_url": LONGBRIDGE_CONFIG.get('trade_ws_url', ''),
            "is_configured": bool
            (LONGBRIDGE_CONFIG['app_key'] and LONGBRIDGE_CONFIG['app_secret'] and LONGBRIDGE_CONFIG['access_token']),
            "sdk_available": LONGBRIDGE_AVAILABLE,
            "use_real_sdk": longbridge_sdk.use_real_sdk
        }
    }


class LongBridgeConfigUpdate(BaseModel):
    app_key: str
    app_secret: str
    access_token: str
    http_url: Optional[str] = "https://openapi.longbridgeapp.com"
    quote_ws_url: Optional[str] = "wss://openapi-quote.longbridgeapp.com"
    trade_ws_url: Optional[str] = "wss://openapi-trade.longbridgeapp.com"


@app.post("/api/longbridge/config")
async def update_longbridge_config(config: LongBridgeConfigUpdate, current_user: dict = Depends(get_current_user)):
    """更新长桥配置并重新连接"""
    global longbridge_sdk, LONGBRIDGE_CONFIG

    try:
        # 更新配置
        LONGBRIDGE_CONFIG['app_key'] = config.app_key
        LONGBRIDGE_CONFIG['app_secret'] = config.app_secret
        LONGBRIDGE_CONFIG['access_token'] = config.access_token
        LONGBRIDGE_CONFIG['http_url'] = config.http_url
        LONGBRIDGE_CONFIG['quote_ws_url'] = config.quote_ws_url
        LONGBRIDGE_CONFIG['trade_ws_url'] = config.trade_ws_url

        # 保存到数据库
        conn = get_db_connection()
        cursor = conn.cursor()
        configs = [
            ('longbridge_app_key', config.app_key, '长桥App Key'),
            ('longbridge_app_secret', config.app_secret, '长桥App Secret'),
            ('longbridge_access_token', config.access_token, '长桥Access Token'),
            ('longbridge_http_url', config.http_url, '长桥HTTP URL'),
            ('longbridge_quote_ws_url', config.quote_ws_url, '长桥行情WebSocket URL'),
            ('longbridge_trade_ws_url', config.trade_ws_url, '长桥交易WebSocket URL')
        ]
        for key, value, desc in configs:
            cursor.execute("""
                INSERT INTO system_config (config_key, config_value, description)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE config_value = %s, description = %s
            """, (key, value, desc, value, desc))
        conn.commit()
        cursor.close()
        conn.close()

        # 重新初始化SDK并更新全局变量
        global longbridge_sdk
        longbridge_sdk = LongBridgeSDK(LONGBRIDGE_CONFIG)
        await longbridge_sdk.connect()

        # 如果监控正在运行，需要重新订阅
        if is_monitoring and longbridge_sdk.use_real_sdk:
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT symbol FROM stocks WHERE is_active = 1")
                active_symbols = [row[0] for row in cursor.fetchall()]
                cursor.close()
                conn.close()

                if active_symbols:
                    longbridge_sdk.subscribe_realtime_quotes(
                        active_symbols,
                        lambda quote: handle_quote_event(quote)
                    )
                    logger.info(f"已重新订阅实时行情: {len(active_symbols)}只股票")
            except Exception as e:
                logger.error(f"重新订阅行情失败: {str(e)}")

        return {
            "code": 0,
            "message": "配置已更新并重新连接",
            "data": {
                "use_real_sdk": longbridge_sdk.use_real_sdk,
                "is_connected": longbridge_sdk.is_connected
            }
        }
    except Exception as e:
        logger.error(f"更新长桥配置失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/longbridge/sync-watchlist")
async def sync_longbridge_watchlist():
    """从长桥账号同步自选股"""
    global longbridge_sdk

    try:
        if not longbridge_sdk.use_real_sdk or not longbridge_sdk.quote_ctx:
            return {
                "code": 1,
                "message": "SDK未配置或未连接"
            }

        # 从长桥获取自选股
        watchlist_groups = longbridge_sdk.quote_ctx.watchlist()

        if not watchlist_groups:
            return {
                "code": 1,
                "message": "长桥账号中没有自选股"
            }

        # 先收集所有股票代码，用于后续一次性拉静态信息
        all_symbols_raw = []
        stocks_with_group = []
        group_order = 0

        for group in watchlist_groups:
            group_name = group.name if hasattr(group, 'name') and group.name else f"分组{group_order + 1}"
            group_order += 1

            for security in group.securities:
                symbol = security.symbol
                # 转换符号格式：AAPL.US -> AAPL
                clean_symbol = symbol.replace('.US', '').replace('.HK', '').replace('.SH', '').replace('.SZ', '')

                all_symbols_raw.append(clean_symbol)

        # 调用长桥静态信息接口尝试获取真实类型
        static_type_map = await longbridge_sdk.get_static_info(list(set(all_symbols_raw)))

        # 重新遍历并分类
        group_order = 0
        stocks_with_group = []
        for group in watchlist_groups:
            group_name = group.name if hasattr(group, 'name') and group.name else f"分组{group_order + 1}"
            group_order += 1

            for security in group.securities:
                symbol = security.symbol
                clean_symbol = symbol.replace('.US', '').replace('.HK', '').replace('.SH', '').replace('.SZ', '')

                # 判断股票类型：优先用静态信息，其次用代码规则
                security_type_hint = static_type_map.get(clean_symbol)
                stock_type = classify_symbol_type(clean_symbol, security_type_hint)

                # 只保留美股
                if symbol.endswith('.US') or (not '.' in symbol and symbol.isalpha()) or stock_type == 'OPTION':
                    stocks_with_group.append({
                        'symbol': clean_symbol,
                        'name': clean_symbol,  # 后续会获取真实名称
                        'group_name': group_name,
                        'group_order': group_order,
                        'stock_type': stock_type
                    })

        if not stocks_with_group:
            return {
                "code": 1,
                "message": "自选股中没有美股"
            }

        # 获取股票名称
        try:
            # 只查询正股的名称（期权可能无法获取行情）
            stock_symbols = [s['symbol'] for s in stocks_with_group if s['stock_type'] == 'STOCK']
            if stock_symbols:
                quotes = await longbridge_sdk.get_realtime_quote(stock_symbols)
                stock_names = {q['symbol']: q.get('name', q['symbol']) for q in quotes}
                for stock in stocks_with_group:
                    if stock['stock_type'] == 'STOCK':
                        stock['name'] = stock_names.get(stock['symbol'], stock['symbol'])
        except Exception as e:
            logger.warning(f"获取股票名称失败: {e}，使用代码作为名称")

        # 添加到数据库
        conn = get_db_connection()
        cursor = conn.cursor()

        added_count = 0
        skipped_count = 0

        for stock in stocks_with_group:
            try:
                cursor.execute("""
                    INSERT INTO stocks (symbol, name, group_name, group_order, stock_type, is_active)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                    name = VALUES(name),
                    group_name = VALUES(group_name),
                    group_order = VALUES(group_order),
                    stock_type = VALUES(stock_type),
                    is_active = VALUES(is_active)
                """, (
                stock['symbol'], stock['name'], stock['group_name'], stock['group_order'], stock['stock_type'], 1))
                if cursor.rowcount > 0:
                    added_count += 1
                else:
                    skipped_count += 1
            except Exception as e:
                logger.error(f"添加股票 {stock['symbol']} 失败: {e}")

        conn.commit()
        cursor.close()
        conn.close()

        logger.info(f"同步完成: 新增 {added_count} 只, 跳过 {skipped_count} 只")

        return {
            "code": 0,
            "message": f"同步完成: 新增 {added_count} 只, 跳过 {skipped_count} 只",
            "data": {
                "total": len(stocks_with_group),
                "added": added_count,
                "skipped": skipped_count,
                "stocks": [s['symbol'] for s in stocks_with_group]
            }
        }

    except Exception as e:
        logger.error(f"同步自选股失败: {str(e)}")
        return {
            "code": 1,
            "message": f"同步失败: {str(e)}"
        }


# 挂载静态文件（必须在最后）
app.mount("/static", StaticFiles(directory="static", html=True), name="static")

# 启动入口
if __name__ == "__main__":
    import uvicorn

    # 从数据库加载长桥配置
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute("SELECT config_key, config_value FROM system_config WHERE config_key IN ('longbridge_app_key', 'longbridge_app_secret', 'longbridge_access_token', 'longbridge_http_url', 'longbridge_quote_ws_url', 'longbridge_trade_ws_url')")
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
            elif key == 'longbridge_http_url':
                LONGBRIDGE_CONFIG['http_url'] = value
            elif key == 'longbridge_quote_ws_url':
                LONGBRIDGE_CONFIG['quote_ws_url'] = value
            elif key == 'longbridge_trade_ws_url':
                LONGBRIDGE_CONFIG['trade_ws_url'] = value

        logger.info(f"从数据库加载长桥配置: app_key={LONGBRIDGE_CONFIG['app_key'][:8] if LONGBRIDGE_CONFIG['app_key'] else 'N/A'}...")
    except Exception as e:
        logger.warning(f"从数据库加载长桥配置失败: {str(e)}")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
