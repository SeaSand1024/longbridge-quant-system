"""
测试模式价格管理器
"""
import random
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class TestModePriceManager:
    """测试模式下模拟价格的管理器，提供价格持续性"""
    
    def __init__(self):
        self.prices = {}  # {symbol: {'price': float, 'base_price': float, 'last_update': datetime}}
        
        # 默认基础价格
        self.default_prices = {
            'AAPL': 175.0, 'GOOGL': 140.0, 'MSFT': 380.0, 'AMZN': 180.0,
            'NVDA': 880.0, 'META': 500.0, 'TSLA': 250.0, 'AMD': 160.0,
            'NFLX': 600.0, 'INTC': 45.0, 'CRM': 280.0, 'ORCL': 120.0,
            'ADBE': 580.0, 'PYPL': 65.0, 'UBER': 75.0, 'SPOT': 280.0,
            'SQ': 80.0, 'SHOP': 70.0, 'SNAP': 15.0, 'PINS': 35.0,
            'ZM': 70.0, 'DOCU': 55.0, 'OKTA': 95.0, 'CRWD': 320.0,
            'DDOG': 120.0, 'NET': 85.0, 'MDB': 380.0, 'SNOW': 170.0,
            'PLTR': 22.0, 'COIN': 230.0, 'HOOD': 18.0, 'RBLX': 45.0,
            'U': 28.0, 'ABNB': 150.0, 'DASH': 130.0, 'LYFT': 15.0
        }
    
    def get_price(self, symbol: str) -> tuple:
        """获取模拟价格，返回 (price, change_pct)"""
        now = datetime.now()
        
        if symbol not in self.prices:
            base_price = self.default_prices.get(symbol, random.uniform(50, 500))
            self.prices[symbol] = {
                'price': base_price,
                'base_price': base_price,
                'last_update': now,
                'trend': random.choice([-1, 1])
            }
        
        data = self.prices[symbol]
        time_diff = (now - data['last_update']).total_seconds()
        
        # 每5秒更新一次价格
        if time_diff >= 5:
            # 模拟价格波动 (±0.5%)
            change = random.uniform(-0.005, 0.005)
            
            # 添加趋势因素
            trend_factor = data['trend'] * random.uniform(0, 0.002)
            change += trend_factor
            
            new_price = data['price'] * (1 + change)
            
            # 限制价格范围
            max_deviation = 0.1
            min_price = data['base_price'] * (1 - max_deviation)
            max_price = data['base_price'] * (1 + max_deviation)
            new_price = max(min_price, min(max_price, new_price))
            
            data['price'] = new_price
            data['last_update'] = now
            
            # 随机改变趋势
            if random.random() < 0.1:
                data['trend'] *= -1
        
        change_pct = ((data['price'] - data['base_price']) / data['base_price']) * 100
        return round(data['price'], 2), round(change_pct, 2)
    
    def set_price(self, symbol: str, price: float):
        """设置价格（用于买入时锁定）"""
        if symbol not in self.prices:
            self.prices[symbol] = {
                'price': price,
                'base_price': price,
                'last_update': datetime.now(),
                'trend': random.choice([-1, 1])
            }
        else:
            self.prices[symbol]['price'] = price
            self.prices[symbol]['last_update'] = datetime.now()


# 全局实例
test_mode_price_manager = TestModePriceManager()
