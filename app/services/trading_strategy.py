"""
交易策略服务
"""
import logging
import pymysql
from datetime import datetime
from typing import Optional

from app.config.database import get_db_connection
from app.config.settings import ensure_default_system_configs
from app.auth.utils import is_test_mode

logger = logging.getLogger(__name__)


class TradingStrategy:
    """交易策略类"""
    
    def __init__(self):
        self.profit_target = 1.0
        self.buy_amount = 200000.0
        self.max_concurrent_positions = 1
        self.positions_cache = {}
        self.market_data_cache = {}

    async def load_config(self):
        """从数据库加载配置"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            
            ensure_default_system_configs(cursor)
            conn.commit()
            
            cursor.execute(
                "SELECT config_key, config_value FROM system_config WHERE config_key IN (%s, %s, %s)",
                ('profit_target', 'buy_amount', 'max_concurrent_positions')
            )
            configs = {row['config_key']: row['config_value'] for row in cursor.fetchall()}
            
            self.profit_target = float(configs.get('profit_target', '1.0'))
            self.buy_amount = float(configs.get('buy_amount', '200000'))
            self.max_concurrent_positions = int(configs.get('max_concurrent_positions', '1'))
            
            cursor.close()
            conn.close()
            
            logger.info(f"交易策略配置已加载: profit_target={self.profit_target}%, buy_amount=${self.buy_amount}")
        except Exception as e:
            logger.warning(f"加载交易策略配置失败: {e}")

    async def check_buy_signal(self, symbol: str, price: float, change_pct: float, acceleration: float) -> bool:
        """检查买入信号"""
        # 检查当前持仓数量
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        test_mode = 1 if is_test_mode() else 0
        cursor.execute("SELECT COUNT(*) as cnt FROM positions WHERE quantity > 0 AND test_mode = %s", (test_mode,))
        current_positions = cursor.fetchone()['cnt']
        
        if current_positions >= self.max_concurrent_positions:
            cursor.close()
            conn.close()
            return False
        
        # 检查是否已持有该股票
        cursor.execute("SELECT quantity FROM positions WHERE symbol = %s AND test_mode = %s", (symbol, test_mode))
        position = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if position and position['quantity'] > 0:
            return False
        
        # 买入条件：加速度 > 0.5 且涨幅 > 1%
        if acceleration > 0.5 and change_pct > 1.0:
            return True
        
        return False

    async def check_sell_signal(self, symbol: str, current_price: float, position: dict) -> bool:
        """检查卖出信号"""
        if not position or position.get('quantity', 0) <= 0:
            return False
        
        buy_price = float(position.get('buy_price', 0))
        if buy_price <= 0:
            return False
        
        profit_pct = ((current_price - buy_price) / buy_price) * 100
        
        # 达到止盈目标
        if profit_pct >= self.profit_target:
            logger.info(f"{symbol} 达到止盈目标: {profit_pct:.2f}% >= {self.profit_target}%")
            return True
        
        return False

    async def execute_buy(self, symbol: str, price: float, acceleration: float = 0) -> dict:
        """执行买入"""
        from .longbridge_sdk import longbridge_sdk
        from .test_mode import test_mode_price_manager
        
        try:
            quantity = int(self.buy_amount / price)
            if quantity <= 0:
                return {'success': False, 'message': '买入数量不足'}
            
            cost = price * quantity
            test_mode = 1 if is_test_mode() else 0
            
            if is_test_mode():
                test_mode_price_manager.set_price(symbol, price)
                order_result = {'success': True, 'order_id': f'TEST_{datetime.now().strftime("%Y%m%d%H%M%S")}'}
            else:
                order_result = await longbridge_sdk.submit_order(symbol, 'BUY', quantity, 'MARKET')
            
            if order_result.get('success'):
                conn = get_db_connection()
                cursor = conn.cursor(pymysql.cursors.DictCursor)
                
                # 记录交易
                cursor.execute("""
                    INSERT INTO trades (symbol, action, price, quantity, amount, acceleration, status, test_mode)
                    VALUES (%s, 'BUY', %s, %s, %s, %s, 'FILLED', %s)
                """, (symbol, price, quantity, cost, acceleration, test_mode))
                
                # 查询现有持仓计算新的平均价
                cursor.execute(
                    "SELECT quantity, cost, buy_price FROM positions WHERE symbol = %s AND test_mode = %s",
                    (symbol, test_mode)
                )
                existing = cursor.fetchone()
                
                if existing and existing['quantity'] > 0:
                    # 加仓：计算新的平均买入价
                    old_qty = existing['quantity']
                    old_cost = float(existing['cost'])
                    new_total_qty = old_qty + quantity
                    new_total_cost = old_cost + cost
                    new_avg_price = new_total_cost / new_total_qty
                    
                    cursor.execute("""
                        UPDATE positions SET 
                            quantity = %s, cost = %s, buy_price = %s, 
                            buy_acceleration = %s, status = 'HOLDING'
                        WHERE symbol = %s AND test_mode = %s
                    """, (new_total_qty, new_total_cost, new_avg_price, acceleration, symbol, test_mode))
                else:
                    # 新建持仓
                    cursor.execute("""
                        INSERT INTO positions (symbol, quantity, buy_price, cost, buy_acceleration, status, test_mode)
                        VALUES (%s, %s, %s, %s, %s, 'HOLDING', %s)
                    """, (symbol, quantity, price, cost, acceleration, test_mode))
                
                conn.commit()
                cursor.close()
                conn.close()
                
                logger.info(f"买入成功: {symbol} x {quantity} @ ${price:.2f}")
                return {'success': True, 'quantity': quantity, 'price': price, 'cost': cost}
            
            return {'success': False, 'message': order_result.get('message', '订单提交失败')}
        except Exception as e:
            logger.error(f"执行买入失败 {symbol}: {e}")
            return {'success': False, 'message': str(e)}

    async def execute_sell(self, symbol: str, price: float, position: dict) -> dict:
        """执行卖出"""
        from .longbridge_sdk import longbridge_sdk
        
        try:
            quantity = position.get('quantity', 0)
            if quantity <= 0:
                return {'success': False, 'message': '无持仓可卖'}
            
            amount = price * quantity
            buy_price = float(position.get('buy_price', price))
            profit_loss = (price - buy_price) * quantity
            profit_pct = ((price - buy_price) / buy_price) * 100 if buy_price > 0 else 0
            test_mode = 1 if is_test_mode() else 0
            
            if is_test_mode():
                order_result = {'success': True, 'order_id': f'TEST_{datetime.now().strftime("%Y%m%d%H%M%S")}'}
            else:
                order_result = await longbridge_sdk.submit_order(symbol, 'SELL', quantity, 'MARKET')
            
            if order_result.get('success'):
                conn = get_db_connection()
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO trades (symbol, action, price, quantity, amount, status, message, test_mode)
                    VALUES (%s, 'SELL', %s, %s, %s, 'FILLED', %s, %s)
                """, (symbol, price, quantity, amount, f'盈亏: ${profit_loss:.2f} ({profit_pct:.2f}%)', test_mode))
                
                cursor.execute("""
                    UPDATE positions SET quantity = 0, status = 'SOLD', 
                    current_price = %s, profit_loss = %s, profit_loss_pct = %s
                    WHERE symbol = %s AND test_mode = %s
                """, (price, profit_loss, profit_pct, symbol, test_mode))
                
                conn.commit()
                cursor.close()
                conn.close()
                
                logger.info(f"卖出成功: {symbol} x {quantity} @ ${price:.2f}, 盈亏: ${profit_loss:.2f}")
                return {'success': True, 'quantity': quantity, 'price': price, 'profit_loss': profit_loss}
            
            return {'success': False, 'message': order_result.get('message', '订单提交失败')}
        except Exception as e:
            logger.error(f"执行卖出失败 {symbol}: {e}")
            return {'success': False, 'message': str(e)}

    def get_positions(self) -> list:
        """获取当前持仓"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            
            test_mode = 1 if is_test_mode() else 0
            cursor.execute("""
                SELECT * FROM positions WHERE quantity > 0 AND test_mode = %s
            """, (test_mode,))
            positions = cursor.fetchall()
            
            cursor.close()
            conn.close()
            
            return positions
        except Exception as e:
            logger.error(f"获取持仓失败: {e}")
            return []


# 全局实例
trading_strategy = TradingStrategy()
