"""
长桥SDK封装服务
"""
import random
import logging
import asyncio
import time
from datetime import datetime, timedelta
from typing import List, Optional
from threading import Lock

from app.config.settings import LONGBRIDGE_CONFIG
from app.auth.utils import is_test_mode

logger = logging.getLogger(__name__)


class RateLimiter:
    """请求限流器，防止触发API频率限制"""
    
    def __init__(self, max_requests: int = 10, time_window: float = 1.0):
        """
        初始化限流器
        :param max_requests: 时间窗口内最大请求数
        :param time_window: 时间窗口（秒）
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []
        self.lock = Lock()
    
    def acquire(self) -> float:
        """
        获取请求许可，返回需要等待的时间（秒）
        """
        with self.lock:
            now = time.time()
            # 清理过期的请求记录
            self.requests = [t for t in self.requests if now - t < self.time_window]
            
            if len(self.requests) < self.max_requests:
                self.requests.append(now)
                return 0
            
            # 需要等待，计算等待时间
            oldest = self.requests[0]
            wait_time = self.time_window - (now - oldest) + 0.1  # 额外等待0.1秒
            return max(0, wait_time)
    
    async def wait(self):
        """异步等待直到可以发送请求"""
        wait_time = self.acquire()
        if wait_time > 0:
            logger.debug(f"限流等待 {wait_time:.2f} 秒")
            await asyncio.sleep(wait_time)
            # 重新获取许可
            with self.lock:
                self.requests.append(time.time())


# 全局限流器：长桥API限制约为每秒10次请求，我们保守设置为每秒5次
quote_rate_limiter = RateLimiter(max_requests=5, time_window=1.0)

# 长桥SDK导入
try:
    from longbridge.openapi import (
        QuoteContext, TradeContext, Config as LBConfig, 
        Market, OrderSide, OrderType, TimeInForceType, SubType, PushQuote
    )
    LONGBRIDGE_AVAILABLE = True
    logger.info("长桥SDK已加载")
except ImportError as e:
    LONGBRIDGE_AVAILABLE = False
    logger.warning(f"长桥SDK未安装: {e}")
    
    class PushQuote:
        """模拟PushQuote类型"""
        pass


class LongBridgeSDK:
    """长桥SDK封装类，支持真实SDK和模拟模式"""

    def __init__(self, config):
        self.config = config
        self.is_connected = False
        self.quote_ctx = None
        self.trade_ctx = None
        self.use_real_sdk = (
            LONGBRIDGE_AVAILABLE and 
            config.get('app_key') and 
            config.get('app_secret') and 
            config.get('access_token')
        )

        if self.use_real_sdk:
            logger.info("使用真实长桥SDK")
        else:
            logger.info("使用模拟模式（长桥SDK未配置或未安装）")

    async def connect(self):
        """连接到长桥"""
        logger.info("正在连接长桥SDK...")

        if self.use_real_sdk:
            try:
                lb_config = LBConfig(
                    app_key=self.config['app_key'],
                    app_secret=self.config['app_secret'],
                    access_token=self.config['access_token'],
                    http_url=self.config.get('http_url', 'https://openapi.longbridgeapp.com'),
                    quote_ws_url=self.config.get('quote_ws_url', 'wss://openapi-quote.longbridgeapp.com'),
                    trade_ws_url=self.config.get('trade_ws_url', 'wss://openapi-trade.longbridgeapp.com')
                )

                self.quote_ctx = QuoteContext(lb_config)
                self.trade_ctx = TradeContext(lb_config)
                self.is_connected = True
                logger.info("长桥SDK连接成功（真实模式）")
            except Exception as e:
                logger.error(f"长桥SDK连接失败: {str(e)}")
                logger.info("切换到模拟模式")
                self.use_real_sdk = False
                self.is_connected = True
        else:
            self.is_connected = True
            logger.info("长桥SDK连接成功（模拟模式）")

    def subscribe_realtime_quotes(self, symbols: List[str], callback):
        """订阅实时行情推送"""
        if self.use_real_sdk and self.quote_ctx:
            try:
                self.quote_ctx.set_on_quote(callback)
                self.quote_ctx.subscribe(symbols, [SubType.Quote], is_first_push=False)
                logger.info(f"已订阅实时行情: {symbols}")
                return True
            except Exception as e:
                logger.error(f"订阅实时行情失败: {str(e)}")
                return False
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
        """获取实时行情（带限流）"""
        from .test_mode import test_mode_price_manager
        
        if is_test_mode():
            return self._get_mock_quotes(symbols)

        if self.use_real_sdk and self.quote_ctx:
            try:
                batch_size = 20
                all_results = []
                
                # 标准化所有symbol
                normalized_symbols = [self._normalize_symbol(s) for s in symbols]
                # 建立标准化symbol到原始symbol的映射
                # 注意：标准化后可能出现重复（如 700 和 00700 都变成 00700.HK）
                symbol_map = {self._normalize_symbol(s): s for s in symbols}

                logger.info(f"请求实时行情: {normalized_symbols}")
                for i in range(0, len(normalized_symbols), batch_size):
                    batch_symbols = normalized_symbols[i:i + batch_size]
                    
                    # 等待限流器许可
                    await quote_rate_limiter.wait()
                    
                    quotes = self.quote_ctx.quote(batch_symbols)

                    if not quotes:
                        logger.warning(f"SDK返回空行情数据: {batch_symbols}")

                    for quote in quotes:
                        current_price = float(quote.last_done)
                        prev_close = float(quote.prev_close) if hasattr(quote, 'prev_close') and quote.prev_close else current_price
                        change_pct = ((current_price - prev_close) / prev_close) * 100 if prev_close > 0 else 0.0
                        
                        # 返回原始symbol格式
                        original_symbol = symbol_map.get(quote.symbol, quote.symbol)

                        all_results.append({
                            'symbol': original_symbol,
                            'price': current_price,
                            'change_pct': change_pct,
                            'volume': int(quote.volume),
                            'timestamp': datetime.now().isoformat()
                        })

                return all_results
            except Exception as e:
                error_msg = str(e)
                logger.error(f"获取行情失败: {error_msg}")
                
                # 如果是频率限制错误，等待后重试一次
                if 'rate limit' in error_msg.lower() or '301606' in error_msg:
                    logger.warning("触发API频率限制，等待2秒后重试...")
                    await asyncio.sleep(2)
                    try:
                        # 使用更小的批次重试
                        return await self._get_quotes_with_retry(symbols, symbol_map, batch_size=10)
                    except Exception as retry_e:
                        logger.error(f"重试仍失败: {str(retry_e)}")
                
                # 真实模式下，如果失败了，我们记录错误但尝试返回已有的部分数据
                if 'all_results' in locals() and all_results:
                    return all_results
                return self._get_mock_quotes(symbols)
        
        logger.warning("SDK未连接或未配置，无法获取真实行情")
        return self._get_mock_quotes(symbols)
    
    async def _get_quotes_with_retry(self, symbols: List[str], symbol_map: dict, batch_size: int = 10) -> List[dict]:
        """带重试机制的行情获取"""
        all_results = []
        normalized_symbols = [self._normalize_symbol(s) for s in symbols]
        
        for i in range(0, len(normalized_symbols), batch_size):
            batch_symbols = normalized_symbols[i:i + batch_size]
            
            # 更保守的限流：每批次之间等待更长时间
            await asyncio.sleep(0.5)
            await quote_rate_limiter.wait()
            
            try:
                quotes = self.quote_ctx.quote(batch_symbols)
                
                for quote in quotes:
                    current_price = float(quote.last_done)
                    prev_close = float(quote.prev_close) if hasattr(quote, 'prev_close') and quote.prev_close else current_price
                    change_pct = ((current_price - prev_close) / prev_close) * 100 if prev_close > 0 else 0.0
                    original_symbol = symbol_map.get(quote.symbol, quote.symbol)
                    
                    all_results.append({
                        'symbol': original_symbol,
                        'price': current_price,
                        'change_pct': change_pct,
                        'volume': int(quote.volume),
                        'timestamp': datetime.now().isoformat()
                    })
            except Exception as e:
                logger.error(f"批次获取行情失败: {batch_symbols}, 错误: {str(e)}")
                # 继续处理下一批次
                continue
        
        return all_results

    async def get_history_orders(self, symbol: Optional[str] = None, status_filter: Optional[List] = None,
                                 days: int = 90, limit: int = 1000) -> List[dict]:
        """获取历史订单"""
        if self.use_real_sdk and self.trade_ctx:
            try:
                from longbridge.openapi import OrderStatus

                end_at = datetime.now()
                start_at = end_at - timedelta(days=days)

                if status_filter is None:
                    status_filter = [
                        OrderStatus.Filled, OrderStatus.Canceled, OrderStatus.Rejected,
                        OrderStatus.PartialFilled, OrderStatus.Expired,
                        OrderStatus.PendingCancel, OrderStatus.Replaced
                    ]
                
                # 标准化symbol
                normalized_symbol = self._normalize_symbol(symbol) if symbol else None

                orders = self.trade_ctx.history_orders(
                    symbol=normalized_symbol, status=status_filter,
                    start_at=start_at, end_at=end_at
                )

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
                    except:
                        return 0.0

                def safe_int(val):
                    try:
                        return int(val)
                    except:
                        return 0

                result = []
                for order in orders:
                    result.append({
                        'order_id': getattr(order, 'order_id', ''),
                        'symbol': getattr(order, 'symbol', ''),
                        'side': enum_to_str(getattr(order, 'side', None)),
                        'order_type': enum_to_str(getattr(order, 'order_type', None)),
                        'status': enum_to_str(getattr(order, 'status', None)),
                        'submitted_price': safe_float(getattr(order, 'submitted_price', None)),
                        'executed_price': safe_float(getattr(order, 'executed_price', None)),
                        'submitted_quantity': safe_int(getattr(order, 'submitted_quantity', None)),
                        'executed_quantity': safe_int(getattr(order, 'executed_quantity', None)),
                        'updated_at': getattr(order, 'updated_at', datetime.now()).isoformat(),
                        'currency': enum_to_str(getattr(order, 'currency', 'USD'), default='USD'),
                    })

                result.sort(key=lambda x: x['updated_at'], reverse=True)
                return result[:limit]
            except Exception as e:
                logger.error(f"获取历史订单失败: {str(e)}")
                return []
        return []

    def _normalize_symbol(self, symbol: str) -> str:
        """标准化股票代码为长桥API格式，优先处理A股/港股数字代码"""
        if not symbol:
            return symbol
        
        symbol = symbol.strip().upper()
        
        # 已经包含有效的市场后缀，直接返回
        valid_suffixes = ['.US', '.HK', '.SH', '.SZ', '.SG']
        for suffix in valid_suffixes:
            if symbol.endswith(suffix):
                return symbol
        
        # 移除可能存在的无效后缀（如 .NASDAQ, .NYSE 等）
        if '.' in symbol:
            symbol = symbol.split('.')[0]
        
        # 先判断A股 6 位数字
        if len(symbol) == 6 and symbol.isdigit():
            if symbol.startswith('6'):
                return f"{symbol}.SH"
            if symbol.startswith(('0', '3')):
                return f"{symbol}.SZ"
            # 其他 6 位数字视为港股（少见）
            return f"{symbol}.HK"
        
        # 纯数字 -> 港股，左侧补零到 5 位（长桥常用 5 位格式）
        if symbol.isdigit():
            hk_code = symbol.zfill(5)
            return f"{hk_code}.HK"
        
        # 其他情况默认为美股
        return f"{symbol}.US"

    async def get_stock_history(self, symbol: str, period: str = 'day', count: int = 30) -> List[dict]:
        """获取股票历史K线（带限流）"""
        if self.use_real_sdk and self.quote_ctx:
            try:
                from longbridge.openapi import Period, AdjustType
                
                # 等待限流器许可
                await quote_rate_limiter.wait()
                
                # 标准化symbol格式
                normalized_symbol = self._normalize_symbol(symbol)
                logger.info(f"获取K线: 原始symbol={symbol}, 标准化后={normalized_symbol}")
                
                period_map = {
                    'min1': Period.Min_1, '1m': Period.Min_1,
                    'min5': Period.Min_5, '5m': Period.Min_5,
                    'min15': Period.Min_15, '15m': Period.Min_15,
                    'min30': Period.Min_30, '30m': Period.Min_30,
                    'min60': Period.Min_60, '60m': Period.Min_60, '1h': Period.Min_60,
                    'day': Period.Day, '1d': Period.Day, 'd': Period.Day,
                    'week': Period.Week, '1w': Period.Week, 'w': Period.Week,
                    'month': Period.Month, '1M': Period.Month, 'M': Period.Month
                }
                lb_period = period_map.get(period, Period.Day)

                candlesticks = self.quote_ctx.candlesticks(
                    normalized_symbol, lb_period, count, AdjustType.NoAdjust
                )

                result = []
                for candle in candlesticks:
                    result.append({
                        'date': candle.timestamp.strftime('%Y-%m-%d') if hasattr(candle.timestamp, 'strftime') else str(candle.timestamp),
                        'open': float(candle.open),
                        'high': float(candle.high),
                        'low': float(candle.low),
                        'close': float(candle.close),
                        'volume': int(candle.volume),
                        'turnover': float(candle.turnover) if hasattr(candle, 'turnover') else 0,
                        'change_pct': 0
                    })
                
                # 计算涨跌幅
                for i in range(1, len(result)):
                    prev_close = result[i-1]['close']
                    if prev_close > 0:
                        result[i]['change_pct'] = ((result[i]['close'] - prev_close) / prev_close) * 100
                
                return result
            except Exception as e:
                logger.error(f"获取K线数据失败: {str(e)}")
                
                # 如果是 invalid symbol，尝试港股补零后缀重试一次
                try:
                    if '.HK' in normalized_symbol:
                        alt_symbol = normalized_symbol.replace('.HK', '').zfill(5) + '.HK'
                        if alt_symbol != normalized_symbol:
                            logger.info(f"尝试使用补零后的港股代码重试: {alt_symbol}")
                            candlesticks = self.quote_ctx.candlesticks(
                                alt_symbol, lb_period, count, AdjustType.NoAdjust
                            )
                            result = []
                            for candle in candlesticks:
                                result.append({
                                    'date': candle.timestamp.strftime('%Y-%m-%d') if hasattr(candle.timestamp, 'strftime') else str(candle.timestamp),
                                    'open': float(candle.open),
                                    'high': float(candle.high),
                                    'low': float(candle.low),
                                    'close': float(candle.close),
                                    'volume': int(candle.volume),
                                    'turnover': float(candle.turnover) if hasattr(candle, 'turnover') else 0,
                                    'change_pct': 0
                                })
                            for i in range(1, len(result)):
                                prev_close = result[i-1]['close']
                                if prev_close > 0:
                                    result[i]['change_pct'] = ((result[i]['close'] - prev_close) / prev_close) * 100
                            return result
                except Exception as e2:
                    logger.error(f"补零后仍失败: {str(e2)}")
                
                return self._get_mock_klines(symbol, count)
        
        return self._get_mock_klines(symbol, count)

    async def submit_order(self, symbol: str, side: str, quantity: int, 
                          order_type: str = 'MARKET', price: float = None) -> dict:
        """提交订单"""
        if self.use_real_sdk and self.trade_ctx:
            try:
                lb_side = OrderSide.Buy if side.upper() == 'BUY' else OrderSide.Sell
                lb_order_type = OrderType.MO if order_type.upper() == 'MARKET' else OrderType.LO
                
                # 标准化symbol
                normalized_symbol = self._normalize_symbol(symbol)
                
                order_params = {
                    'symbol': normalized_symbol,
                    'order_type': lb_order_type,
                    'side': lb_side,
                    'submitted_quantity': quantity,
                    'time_in_force': TimeInForceType.Day,
                }
                
                if lb_order_type == OrderType.LO and price:
                    order_params['submitted_price'] = price

                response = self.trade_ctx.submit_order(**order_params)
                
                return {
                    'success': True,
                    'order_id': response.order_id,
                    'message': '订单提交成功'
                }
            except Exception as e:
                logger.error(f"提交订单失败: {str(e)}")
                return {'success': False, 'message': str(e)}
        
        # 模拟订单
        return {
            'success': True,
            'order_id': f'MOCK_{datetime.now().strftime("%Y%m%d%H%M%S")}',
            'message': '模拟订单提交成功'
        }

    async def get_account_balance(self) -> dict:
        """获取账户余额，支持多币种汇总"""
        if self.use_real_sdk and self.trade_ctx:
            try:
                balances = self.trade_ctx.account_balance()
                logger.info(f"获取到账户余额数据: {balances}")
                
                # 汇总所有币种的资产
                # 注意：这里简单累加可能不准确（如果存在不同币种），但通常 net_assets 会在主币种中体现总额
                # 或者我们需要根据汇率进行转换。长桥SDK通常会返回各个币种的余额。
                
                total_net_assets = 0
                total_available = 0
                main_currency = "USD"
                
                for balance in balances:
                    currency = getattr(balance, 'currency', 'USD')
                    net_assets = float(getattr(balance, 'net_assets', 0))
                    available = float(getattr(balance, 'available_cash', getattr(balance, 'total_cash', 0)))
                    
                    # 如果有 net_assets 且不为 0，累加（假设SDK已经处理了汇率或者我们后续处理）
                    # 实际上，长桥通常会有一个汇总账户或者我们需要按汇率换算。
                    # 为了简单起见，如果发现有多个币种，我们记录下来
                    total_net_assets += net_assets
                    total_available += available
                    if net_assets > 0:
                        main_currency = currency

                # 如果累加后的总资产仍为0，尝试取第一个余额对象的 total_cash
                if total_net_assets == 0 and balances:
                    total_net_assets = float(getattr(balances[0], 'total_cash', 0))
                    total_available = float(getattr(balances[0], 'total_cash', 0))
                    main_currency = getattr(balances[0], 'currency', 'USD')

                return {
                    'total_cash': total_available, # 暂时用 available 代替 total_cash
                    'available_cash': total_available,
                    'net_assets': total_net_assets,
                    'currency': main_currency
                }
            except Exception as e:
                logger.error(f"获取账户余额失败: {str(e)}")
                return {'total_cash': 1000000, 'available_cash': 1000000, 'net_assets': 1000000, 'currency': 'USD'}
        
        return {'total_cash': 1000000, 'available_cash': 1000000, 'net_assets': 1000000, 'currency': 'USD'}

    async def get_stock_positions(self) -> List[dict]:
        """获取股票持仓"""
        if self.use_real_sdk and self.trade_ctx:
            try:
                positions = self.trade_ctx.stock_positions()
                result = []
                
                for channel in positions.channels if hasattr(positions, 'channels') else [positions]:
                    for pos in channel.positions if hasattr(channel, 'positions') else [channel]:
                        result.append({
                            'symbol': pos.symbol,
                            'quantity': int(pos.quantity),
                            'available_quantity': int(pos.available_quantity) if hasattr(pos, 'available_quantity') else int(pos.quantity),
                            'cost_price': float(pos.cost_price) if hasattr(pos, 'cost_price') else 0,
                            'market_value': float(pos.market_value) if hasattr(pos, 'market_value') else 0,
                        })
                
                return result
            except Exception as e:
                logger.error(f"获取持仓失败: {str(e)}")
                return []
        return []

    async def get_watchlist(self) -> List[dict]:
        """获取自选股列表"""
        if self.use_real_sdk and self.quote_ctx:
            try:
                watchlist = self.quote_ctx.watchlist()
                logger.info(f"长桥SDK获取到自选股原始数据: {watchlist}")
                result = []
                
                if not watchlist:
                    logger.warning("长桥SDK返回自选股列表为空")
                    return []

                for group in watchlist:
                    group_name = getattr(group, 'name', '默认分组')
                    # 严谨获取证券列表
                    securities = getattr(group, 'securities', [])
                    if securities is None:
                        securities = []
                    
                    if not securities and hasattr(group, 'items'):
                        securities = getattr(group, 'items', [])
                        if securities is None:
                            securities = []
                    
                    # 确保 securities 是可迭代的
                    if not isinstance(securities, (list, tuple)):
                        logger.warning(f"分组 {group_name} 的证券数据格式不正确: {type(securities)}")
                        continue

                    logger.info(f"处理自选股分组: {group_name}, 证券数量: {len(securities)}")
                    
                    for security in securities:
                        if security is None:
                            continue
                        
                        # 同时支持对象属性和字典键访问
                        if isinstance(security, dict):
                            symbol = security.get('symbol', '')
                            name = security.get('name_cn') or security.get('name') or symbol
                        else:
                            symbol = getattr(security, 'symbol', '')
                            name = (getattr(security, 'name_cn', '') or 
                                    getattr(security, 'name', '') or 
                                    getattr(security, 'symbol', ''))
                        
                        if symbol:
                            # 统一标准化symbol
                            normalized_symbol = self._normalize_symbol(symbol)
                            # 限制长度避免数据库报错
                            safe_name = str(name)[:90]
                            safe_group = str(group_name)[:90]
                            
                            result.append({
                                'symbol': normalized_symbol,
                                'name': safe_name,
                                'group': safe_group
                            })
                
                logger.info(f"自选股同步处理完成，共计: {len(result)} 条")
                return result
            except Exception as e:
                logger.error(f"获取自选股失败: {str(e)}", exc_info=True)
                return []
        
        logger.warning("SDK未连接或模拟模式，无法获取真实自选股")
        return []

    def _get_mock_quotes(self, symbols: List[str]) -> List[dict]:
        """生成模拟行情数据"""
        from .test_mode import test_mode_price_manager
        
        result = []
        is_test = is_test_mode()
        
        for symbol in symbols:
            if is_test:
                price, change_pct = test_mode_price_manager.get_price(symbol)
            else:
                # 真实模式下，如果SDK未连接或失败，不应该返回随机数据
                # 这里返回0表示数据不可用，或者可以从数据库获取最后一次成交价
                price = 0
                change_pct = 0

            result.append({
                'symbol': symbol,
                'price': round(price, 2),
                'change_pct': round(change_pct, 2),
                'volume': random.randint(1000000, 10000000) if is_test else 0,
                'timestamp': datetime.now().isoformat()
            })
        return result

    def _get_mock_klines(self, symbol: str, count: int) -> List[dict]:
        """生成模拟K线数据"""
        from .test_mode import test_mode_price_manager
        
        result = []
        base_price, _ = test_mode_price_manager.get_price(symbol)
        
        for i in range(count):
            date = datetime.now() - timedelta(days=count - i - 1)
            daily_change = random.uniform(-0.03, 0.03)
            base_price = base_price * (1 + daily_change)
            
            high = base_price * (1 + random.uniform(0, 0.02))
            low = base_price * (1 - random.uniform(0, 0.02))
            open_price = random.uniform(low, high)
            close = random.uniform(low, high)
            
            result.append({
                'date': date.strftime('%Y-%m-%d'),
                'open': round(open_price, 2),
                'high': round(high, 2),
                'low': round(low, 2),
                'close': round(close, 2),
                'volume': random.randint(1000000, 50000000),
                'change_pct': round(daily_change * 100, 2)
            })
        
        return result


# 全局实例
longbridge_sdk = LongBridgeSDK(LONGBRIDGE_CONFIG)
