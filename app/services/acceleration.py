"""
涨幅加速度计算器
"""
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class AccelerationCalculator:
    """涨幅加速度计算器"""
    
    def __init__(self):
        self.history = {}  # {symbol: [(timestamp, price, change_pct), ...]}
        self.max_history = 60  # 保留最近60条记录
    
    def update(self, symbol: str, price: float, change_pct: float) -> float:
        """更新价格记录并计算加速度"""
        now = datetime.now()
        
        if symbol not in self.history:
            self.history[symbol] = []
        
        self.history[symbol].append((now, price, change_pct))
        
        # 保持历史记录长度
        if len(self.history[symbol]) > self.max_history:
            self.history[symbol] = self.history[symbol][-self.max_history:]
        
        return self.calculate_acceleration(symbol)
    
    def calculate_acceleration(self, symbol: str) -> float:
        """计算加速度（涨幅变化率）"""
        if symbol not in self.history or len(self.history[symbol]) < 2:
            return 0.0
        
        history = self.history[symbol]
        
        # 使用最近的数据计算加速度
        if len(history) >= 3:
            recent = history[-3:]
            time_diff = (recent[-1][0] - recent[0][0]).total_seconds()
            if time_diff > 0:
                change_diff = recent[-1][2] - recent[0][2]
                acceleration = (change_diff / time_diff) * 60  # 转换为每分钟
                return round(acceleration, 4)
        
        return 0.0
    
    def get_top_accelerating(self, n: int = 5) -> list:
        """获取加速度最高的股票"""
        accelerations = []
        for symbol in self.history:
            acc = self.calculate_acceleration(symbol)
            if self.history[symbol]:
                last_data = self.history[symbol][-1]
                accelerations.append({
                    'symbol': symbol,
                    'acceleration': acc,
                    'price': last_data[1],
                    'change_pct': last_data[2]
                })
        
        accelerations.sort(key=lambda x: x['acceleration'], reverse=True)
        return accelerations[:n]


# 全局实例
acceleration_calculator = AccelerationCalculator()
