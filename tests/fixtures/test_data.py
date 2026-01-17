"""
测试数据生成工厂
"""
import random
import factory
from faker import Faker
from datetime import datetime, timedelta
from typing import List, Dict, Any

fake = Faker('zh_CN')


class StockFactory(factory.Factory):
    """股票数据工厂"""
    class Meta:
        model = dict
    
    symbol = factory.Sequence(lambda n: f"TEST{n:03d}")
    name = factory.LazyAttribute(lambda obj: f"测试股票 {obj.symbol}")
    stock_type = "STOCK"
    group_name = factory.Faker('random_element', elements=['Tech', 'Finance', 'Healthcare', 'Energy'])
    is_active = True


class TradeFactory(factory.Factory):
    """交易记录工厂"""
    class Meta:
        model = dict
    
    symbol = factory.Faker('random_element', elements=['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'NVDA'])
    action = factory.Faker('random_element', elements=['BUY', 'SELL'])
    price = factory.Faker('pyfloat', left_digits=3, right_digits=2, positive=True, min_value=10, max_value=1000)
    quantity = factory.Faker('random_int', min=1, max=1000)
    acceleration = factory.Faker('pyfloat', left_digits=1, right_digits=4, positive=False, min_value=-0.1, max_value=0.1)
    test_mode = 0  # 默认测试模式
    
    @factory.lazy_attribute
    def amount(self):
        return self.price * self.quantity


class PositionFactory(factory.Factory):
    """持仓数据工厂"""
    class Meta:
        model = dict
    
    symbol = factory.Faker('random_element', elements=['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'NVDA'])
    quantity = factory.Faker('random_int', min=10, max=1000)
    avg_cost = factory.Faker('pyfloat', left_digits=3, right_digits=2, positive=True, min_value=50, max_value=500)
    current_price = factory.LazyAttribute(lambda obj: obj.avg_cost * random.uniform(0.9, 1.1))
    test_mode = 0
    
    @factory.lazy_attribute
    def profit_loss(self):
        return (self.current_price - self.avg_cost) * self.quantity
    
    @factory.lazy_attribute
    def profit_loss_pct(self):
        return ((self.current_price - self.avg_cost) / self.avg_cost) * 100


class UserFactory(factory.Factory):
    """用户数据工厂"""
    class Meta:
        model = dict
    
    username = factory.Sequence(lambda n: f"test_user_{n}")
    email = factory.LazyAttribute(lambda obj: f"{obj.username}@test.com")
    password_hash = "$2b$12$test_hash_for_testing_only"
    is_active = True


class PredictionFactory(factory.Factory):
    """预测数据工厂"""
    class Meta:
        model = dict
    
    symbol = factory.Faker('random_element', elements=['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'NVDA'])
    prediction_date = factory.LazyFunction(lambda: datetime.now().date())
    predicted_return = factory.Faker('pyfloat', left_digits=1, right_digits=2, positive=False, min_value=-5, max_value=5)
    confidence_score = factory.Faker('pyfloat', left_digits=0, right_digits=2, positive=True, min_value=0.1, max_value=1.0)
    technical_score = factory.Faker('pyfloat', left_digits=2, right_digits=1, positive=True, min_value=0, max_value=100)
    llm_score = factory.Faker('pyfloat', left_digits=2, right_digits=1, positive=True, min_value=0, max_value=100)
    llm_recommendation = factory.Faker('random_element', elements=['buy', 'sell', 'hold'])


class TestDataGenerator:
    """测试数据生成器"""
    
    @staticmethod
    def create_stock_list(count: int = 10) -> List[Dict[str, Any]]:
        """创建股票列表"""
        return [StockFactory() for _ in range(count)]
    
    @staticmethod
    def create_trade_history(symbol: str, days: int = 30, trades_per_day: int = 3) -> List[Dict[str, Any]]:
        """创建交易历史"""
        trades = []
        for i in range(days):
            date = datetime.now() - timedelta(days=days-i)
            for _ in range(random.randint(1, trades_per_day)):
                trade = TradeFactory(symbol=symbol)
                trade['trade_time'] = date + timedelta(
                    hours=random.randint(9, 16),
                    minutes=random.randint(0, 59)
                )
                trades.append(trade)
        return trades
    
    @staticmethod
    def create_market_data(symbol: str, days: int = 30) -> List[Dict[str, Any]]:
        """创建市场数据"""
        base_price = random.uniform(50, 500)
        data = []
        
        for i in range(days):
            # 模拟价格波动
            if i == 0:
                price = base_price
            else:
                change = random.uniform(-0.05, 0.05)  # ±5%波动
                price = data[i-1]['price'] * (1 + change)
            
            change_pct = ((price - base_price) / base_price) * 100 if i > 0 else 0
            
            data.append({
                'symbol': symbol,
                'date': datetime.now().date() - timedelta(days=days-i-1),
                'open': price * random.uniform(0.98, 1.02),
                'high': price * random.uniform(1.0, 1.05),
                'low': price * random.uniform(0.95, 1.0),
                'close': price,
                'volume': random.randint(1000000, 10000000),
                'change_pct': change_pct
            })
        
        return data
    
    @staticmethod
    def create_acceleration_data(symbol: str, points: int = 10) -> List[Dict[str, Any]]:
        """创建加速度数据"""
        data = []
        base_change = 0.0
        
        for i in range(points):
            # 模拟加速度变化
            if i < 3:
                change_pct = base_change + random.uniform(0.1, 0.5)
            elif i < 6:
                change_pct = base_change + random.uniform(0.3, 0.8)
            else:
                change_pct = base_change + random.uniform(0.5, 1.5)
            
            acceleration = (change_pct - base_change) / max(i, 1) if i > 0 else 0
            
            data.append({
                'symbol': symbol,
                'timestamp': datetime.now() - timedelta(minutes=points-i),
                'price': 100 * (1 + change_pct / 100),
                'change_pct': change_pct,
                'acceleration': acceleration
            })
            
            base_change = change_pct
        
        return data
    
    @staticmethod
    def create_longbridge_positions() -> List[Dict[str, Any]]:
        """创建长桥持仓数据"""
        symbols = ['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'NVDA']
        positions = []
        
        for symbol in symbols:
            if random.choice([True, False]):  # 随机是否持有
                position = {
                    'symbol': symbol,
                    'quantity': random.randint(10, 500),
                    'market_value': random.uniform(1000, 50000),
                    'cost_price': random.uniform(50, 300),
                    'current_price': random.uniform(50, 300),
                    'unrealized_pnl': random.uniform(-1000, 2000),
                    'realized_pnl': random.uniform(-500, 1500),
                    'side': 'Long'
                }
                positions.append(position)
        
        return positions
    
    @staticmethod
    def create_system_config() -> Dict[str, Any]:
        """创建系统配置"""
        return {
            'max_positions': 10,
            'buy_amount': 20000.0,
            'profit_target': 1.0,
            'stop_loss': -2.0,
            'min_acceleration': 0.001,
            'min_change_pct': 0.5,
            'llm_enabled': True,
            'llm_weight': 0.3,
            'max_daily_trades': 5,
            'trading_enabled': True,
            'test_mode': True
        }
    
    @staticmethod
    def create_user_config(user_id: int) -> Dict[str, Any]:
        """创建用户配置"""
        return {
            'user_id': user_id,
            'longbridge_app_key': 'test_app_key',
            'longbridge_app_secret': 'test_app_secret',
            'longbridge_access_token': 'test_access_token',
            'openai_api_key': 'test_openai_key',
            'preferred_model': 'gpt-3.5-turbo',
            'risk_level': 'medium',
            'max_single_trade': 10000.0,
            'notification_enabled': True
        }


class ScenarioDataGenerator:
    """场景化测试数据生成器"""
    
    @staticmethod
    def create_bull_market_scenario() -> Dict[str, Any]:
        """创建牛市场景数据"""
        symbols = ['AAPL', 'GOOGL', 'MSFT']
        scenario_data = {
            'name': '牛市场景',
            'description': '所有股票都在上涨',
            'stocks': [],
            'market_data': [],
            'expected_trades': []
        }
        
        for symbol in symbols:
            # 创建上涨趋势的市场数据
            market_data = TestDataGenerator.create_market_data(symbol, 30)
            # 调整为上涨趋势
            for i, data in enumerate(market_data):
                if i > 0:
                    data['close'] = market_data[0]['close'] * (1 + (i * 0.02))  # 每天2%涨幅
                    data['change_pct'] = 2.0
            
            scenario_data['market_data'].extend(market_data)
            scenario_data['expected_trades'].append({
                'symbol': symbol,
                'action': 'BUY',
                'expected': True
            })
        
        return scenario_data
    
    @staticmethod
    def create_bear_market_scenario() -> Dict[str, Any]:
        """创建熊市场景数据"""
        symbols = ['AAPL', 'GOOGL', 'MSFT']
        scenario_data = {
            'name': '熊市场景',
            'description': '所有股票都在下跌',
            'stocks': [],
            'market_data': [],
            'expected_trades': []
        }
        
        for symbol in symbols:
            # 创建下跌趋势的市场数据
            market_data = TestDataGenerator.create_market_data(symbol, 30)
            # 调整为下跌趋势
            for i, data in enumerate(market_data):
                if i > 0:
                    data['close'] = market_data[0]['close'] * (1 - (i * 0.015))  # 每天-1.5%跌幅
                    data['change_pct'] = -1.5
            
            scenario_data['market_data'].extend(market_data)
            scenario_data['expected_trades'].append({
                'symbol': symbol,
                'action': 'SELL',
                'expected': True
            })
        
        return scenario_data
    
    @staticmethod
    def create_volatile_market_scenario() -> Dict[str, Any]:
        """创建震荡市场景数据"""
        symbols = ['AAPL', 'GOOGL']
        scenario_data = {
            'name': '震荡市场景',
            'description': '股票价格剧烈波动',
            'stocks': [],
            'market_data': [],
            'expected_trades': []
        }
        
        for symbol in symbols:
            market_data = []
            base_price = 100.0
            
            for i in range(30):
                # 创建高波动性数据
                if i % 2 == 0:
                    change = random.uniform(3, 8)  # 大涨
                else:
                    change = random.uniform(-8, -3)  # 大跌
                
                price = base_price * (1 + change / 100)
                
                market_data.append({
                    'symbol': symbol,
                    'date': datetime.now().date() - timedelta(days=30-i),
                    'close': price,
                    'change_pct': change,
                    'volume': random.randint(5000000, 20000000)  # 高成交量
                })
                
                base_price = price
            
            scenario_data['market_data'].extend(market_data)
            scenario_data['expected_trades'].append({
                'symbol': symbol,
                'action': 'MIXED',
                'expected': True
            })
        
        return scenario_data