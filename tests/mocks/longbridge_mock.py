"""
长桥SDK模拟器
"""
import asyncio
import random
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from unittest.mock import AsyncMock, MagicMock


class MockLongBridgeSDK:
    """长桥SDK模拟器"""
    
    def __init__(self, simulate_errors: bool = False):
        self.simulate_errors = simulate_errors
        self.is_connected = True
        self.orders = []
        self.positions = []
        self.account_balance = 100000.0  # 模拟账户余额
        self.market_data = {}
        self.subscriptions = set()
        
        # 模拟配置
        self.config = {
            'app_key': 'mock_app_key',
            'app_secret': 'mock_app_secret',
            'access_token': 'mock_access_token'
        }
        
        # 初始化一些默认持仓
        self._init_default_positions()
    
    def _init_default_positions(self):
        """初始化默认持仓"""
        default_positions = [
            {
                'symbol': 'AAPL',
                'quantity': 100,
                'market_value': 15000.0,
                'cost_price': 145.0,
                'current_price': 150.0,
                'unrealized_pnl': 500.0,
                'realized_pnl': 0.0,
                'side': 'Long'
            },
            {
                'symbol': 'GOOGL',
                'quantity': 10,
                'market_value': 28000.0,
                'cost_price': 2750.0,
                'current_price': 2800.0,
                'unrealized_pnl': 500.0,
                'realized_pnl': 0.0,
                'side': 'Long'
            }
        ]
        self.positions = default_positions
    
    async def connect(self) -> bool:
        """连接到长桥"""
        if self.simulate_errors and random.random() < 0.1:
            raise ConnectionError("模拟连接失败")
        
        await asyncio.sleep(0.1)  # 模拟网络延迟
        self.is_connected = True
        return True
    
    async def disconnect(self):
        """断开连接"""
        self.is_connected = False
        self.subscriptions.clear()
    
    async def submit_order(self, symbol: str, action: str, quantity: int, 
                          order_type: str = "MO", price: Optional[float] = None) -> Dict[str, Any]:
        """提交订单"""
        if not self.is_connected:
            raise ConnectionError("SDK未连接")
        
        if self.simulate_errors and random.random() < 0.05:
            raise Exception("模拟下单失败")
        
        # 检查余额
        if action.upper() == 'BUY':
            estimated_cost = quantity * (price or self._get_current_price(symbol))
            if estimated_cost > self.account_balance:
                return {
                    'success': False,
                    'error': '余额不足',
                    'order_id': None
                }
        
        # 生成订单ID
        order_id = f"MOCK_{datetime.now().strftime('%Y%m%d%H%M%S')}_{random.randint(1000, 9999)}"
        
        # 模拟订单执行
        await asyncio.sleep(0.2)  # 模拟执行延迟
        
        current_price = price or self._get_current_price(symbol)
        
        order = {
            'order_id': order_id,
            'symbol': symbol,
            'action': action.upper(),
            'quantity': quantity,
            'order_type': order_type,
            'price': current_price,
            'status': 'FILLED',
            'filled_quantity': quantity,
            'filled_price': current_price,
            'submit_time': datetime.now(),
            'success': True
        }
        
        self.orders.append(order)
        
        # 更新持仓
        self._update_positions(order)
        
        # 更新余额
        if action.upper() == 'BUY':
            self.account_balance -= quantity * current_price
        else:
            self.account_balance += quantity * current_price
        
        return order
    
    async def get_orders(self, symbol: Optional[str] = None, 
                        start_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """获取订单历史"""
        if not self.is_connected:
            raise ConnectionError("SDK未连接")
        
        orders = self.orders.copy()
        
        if symbol:
            orders = [o for o in orders if o['symbol'] == symbol]
        
        if start_date:
            orders = [o for o in orders if o['submit_time'] >= start_date]
        
        return orders
    
    async def get_positions(self) -> List[Dict[str, Any]]:
        """获取持仓"""
        if not self.is_connected:
            raise ConnectionError("SDK未连接")
        
        if self.simulate_errors and random.random() < 0.02:
            raise Exception("模拟获取持仓失败")
        
        # 更新当前价格
        for position in self.positions:
            current_price = self._get_current_price(position['symbol'])
            position['current_price'] = current_price
            position['market_value'] = position['quantity'] * current_price
            position['unrealized_pnl'] = (current_price - position['cost_price']) * position['quantity']
        
        return self.positions.copy()
    
    async def get_account_balance(self) -> Dict[str, float]:
        """获取账户余额"""
        if not self.is_connected:
            raise ConnectionError("SDK未连接")
        
        return {
            'cash': self.account_balance,
            'market_value': sum(p['market_value'] for p in self.positions),
            'total_assets': self.account_balance + sum(p['market_value'] for p in self.positions),
            'unrealized_pnl': sum(p['unrealized_pnl'] for p in self.positions),
            'realized_pnl': sum(p.get('realized_pnl', 0) for p in self.positions)
        }
    
    async def get_stock_quote(self, symbol: str) -> Dict[str, Any]:
        """获取股票报价"""
        if not self.is_connected:
            raise ConnectionError("SDK未连接")
        
        if self.simulate_errors and random.random() < 0.02:
            raise Exception("模拟获取报价失败")
        
        base_price = self._get_base_price(symbol)
        current_price = base_price * random.uniform(0.95, 1.05)
        change_pct = random.uniform(-5, 5)
        
        quote = {
            'symbol': symbol,
            'price': round(current_price, 2),
            'change': round(current_price * change_pct / 100, 2),
            'change_pct': round(change_pct, 2),
            'volume': random.randint(1000000, 10000000),
            'high': round(current_price * 1.02, 2),
            'low': round(current_price * 0.98, 2),
            'open': round(current_price * random.uniform(0.99, 1.01), 2),
            'timestamp': datetime.now()
        }
        
        self.market_data[symbol] = quote
        return quote
    
    async def subscribe_quote(self, symbols: List[str], callback=None):
        """订阅实时报价"""
        if not self.is_connected:
            raise ConnectionError("SDK未连接")
        
        for symbol in symbols:
            self.subscriptions.add(symbol)
        
        # 模拟实时数据推送
        if callback:
            asyncio.create_task(self._simulate_real_time_data(symbols, callback))
    
    async def unsubscribe_quote(self, symbols: List[str]):
        """取消订阅"""
        for symbol in symbols:
            self.subscriptions.discard(symbol)
    
    async def get_watchlist(self) -> List[str]:
        """获取自选股列表"""
        if not self.is_connected:
            raise ConnectionError("SDK未连接")
        
        # 返回模拟自选股
        return ['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'NVDA', 'AMZN', 'META']
    
    def _get_base_price(self, symbol: str) -> float:
        """获取股票基础价格"""
        base_prices = {
            'AAPL': 150.0,
            'GOOGL': 2800.0,
            'MSFT': 300.0,
            'TSLA': 200.0,
            'NVDA': 500.0,
            'AMZN': 3000.0,
            'META': 250.0
        }
        return base_prices.get(symbol, 100.0)
    
    def _get_current_price(self, symbol: str) -> float:
        """获取当前价格"""
        if symbol in self.market_data:
            return self.market_data[symbol]['price']
        
        base_price = self._get_base_price(symbol)
        return base_price * random.uniform(0.98, 1.02)
    
    def _update_positions(self, order: Dict[str, Any]):
        """更新持仓"""
        symbol = order['symbol']
        action = order['action']
        quantity = order['filled_quantity']
        price = order['filled_price']
        
        # 查找现有持仓
        existing_position = None
        for i, position in enumerate(self.positions):
            if position['symbol'] == symbol:
                existing_position = i
                break
        
        if action == 'BUY':
            if existing_position is not None:
                # 增加持仓
                pos = self.positions[existing_position]
                total_cost = pos['cost_price'] * pos['quantity'] + price * quantity
                total_quantity = pos['quantity'] + quantity
                pos['cost_price'] = total_cost / total_quantity
                pos['quantity'] = total_quantity
                pos['market_value'] = total_quantity * self._get_current_price(symbol)
            else:
                # 新建持仓
                self.positions.append({
                    'symbol': symbol,
                    'quantity': quantity,
                    'cost_price': price,
                    'current_price': price,
                    'market_value': quantity * price,
                    'unrealized_pnl': 0.0,
                    'realized_pnl': 0.0,
                    'side': 'Long'
                })
        
        elif action == 'SELL' and existing_position is not None:
            # 减少持仓
            pos = self.positions[existing_position]
            if pos['quantity'] >= quantity:
                pos['quantity'] -= quantity
                pos['market_value'] = pos['quantity'] * self._get_current_price(symbol)
                
                # 计算已实现盈亏
                realized_pnl = (price - pos['cost_price']) * quantity
                pos['realized_pnl'] = pos.get('realized_pnl', 0) + realized_pnl
                
                # 如果持仓为0，移除
                if pos['quantity'] == 0:
                    self.positions.pop(existing_position)
    
    async def _simulate_real_time_data(self, symbols: List[str], callback):
        """模拟实时数据推送"""
        while any(symbol in self.subscriptions for symbol in symbols):
            for symbol in symbols:
                if symbol in self.subscriptions:
                    quote = await self.get_stock_quote(symbol)
                    if callback:
                        try:
                            await callback(quote)
                        except Exception:
                            pass  # 忽略回调错误
            
            await asyncio.sleep(1)  # 每秒推送一次


class MockLongBridgeConfig:
    """长桥配置模拟器"""
    
    def __init__(self, app_key: str = "mock_key", app_secret: str = "mock_secret", 
                 access_token: str = "mock_token"):
        self.app_key = app_key
        self.app_secret = app_secret
        self.access_token = access_token
        self.http_url = "https://mock-api.longbridge.com"
        self.quote_ws_url = "wss://mock-quote.longbridge.com"
        self.trade_ws_url = "wss://mock-trade.longbridge.com"


def create_mock_longbridge_sdk(simulate_errors: bool = False) -> MockLongBridgeSDK:
    """创建长桥SDK模拟器实例"""
    return MockLongBridgeSDK(simulate_errors=simulate_errors)


def patch_longbridge_sdk(monkeypatch, simulate_errors: bool = False):
    """使用pytest monkeypatch替换长桥SDK"""
    mock_sdk = create_mock_longbridge_sdk(simulate_errors)
    
    # 替换SDK相关的导入
    monkeypatch.setattr("app.services.longbridge_sdk.LongBridgeSDK", lambda *args, **kwargs: mock_sdk)
    monkeypatch.setattr("longbridge.Config", MockLongBridgeConfig)
    
    return mock_sdk