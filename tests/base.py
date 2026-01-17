"""
测试基类和通用工具
"""
import pytest
import pymysql
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from tests.test_config import TestConfig, TestEnvironment
from tests.fixtures.test_data import TestDataGenerator
from tests.mocks import patch_longbridge_sdk, patch_llm_client


class BaseTestCase:
    """测试基类，提供通用测试工具和断言方法"""
    
    @pytest.fixture(autouse=True)
    async def setup_test_environment(self, clean_db, monkeypatch):
        """自动设置测试环境"""
        self.db = clean_db
        self.config = TestConfig()
        self.data_generator = TestDataGenerator()
        
        # 设置Mock
        self.mock_longbridge = patch_longbridge_sdk(monkeypatch, simulate_errors=False)
        self.mock_llm = patch_llm_client(monkeypatch, simulate_errors=False)
        
        # 初始化测试数据
        await self.setup_test_data()
    
    async def setup_test_data(self):
        """设置测试数据 - 子类可重写"""
        pass
    
    def get_cursor(self, dict_cursor: bool = True) -> pymysql.cursors.Cursor:
        """获取数据库游标"""
        if dict_cursor:
            return self.db.cursor(pymysql.cursors.DictCursor)
        return self.db.cursor()
    
    def insert_test_stocks(self, stocks: List[Dict[str, Any]]):
        """插入测试股票数据"""
        cursor = self.get_cursor()
        for stock in stocks:
            cursor.execute("""
                INSERT INTO stocks (symbol, name, stock_type, group_name, is_active)
                VALUES (%(symbol)s, %(name)s, %(stock_type)s, %(group_name)s, %(is_active)s)
            """, stock)
        self.db.commit()
        cursor.close()
    
    def insert_test_trades(self, trades: List[Dict[str, Any]]):
        """插入测试交易数据"""
        cursor = self.get_cursor()
        for trade in trades:
            cursor.execute("""
                INSERT INTO trades (symbol, action, price, quantity, amount, acceleration, test_mode, trade_time)
                VALUES (%(symbol)s, %(action)s, %(price)s, %(quantity)s, %(amount)s, %(acceleration)s, %(test_mode)s, NOW())
            """, trade)
        self.db.commit()
        cursor.close()
    
    def insert_test_positions(self, positions: List[Dict[str, Any]]):
        """插入测试持仓数据"""
        cursor = self.get_cursor()
        for position in positions:
            cursor.execute("""
                INSERT INTO positions (symbol, quantity, avg_cost, current_price, profit_loss, profit_loss_pct, test_mode)
                VALUES (%(symbol)s, %(quantity)s, %(avg_cost)s, %(current_price)s, %(profit_loss)s, %(profit_loss_pct)s, %(test_mode)s)
            """, position)
        self.db.commit()
        cursor.close()
    
    def insert_test_user(self, user_data: Dict[str, Any]) -> int:
        """插入测试用户并返回用户ID"""
        cursor = self.get_cursor()
        cursor.execute("""
            INSERT INTO users (username, email, password_hash, is_active)
            VALUES (%(username)s, %(email)s, %(password_hash)s, %(is_active)s)
        """, user_data)
        user_id = cursor.lastrowid
        self.db.commit()
        cursor.close()
        return user_id
    
    def insert_test_predictions(self, predictions: List[Dict[str, Any]]):
        """插入测试预测数据"""
        cursor = self.get_cursor()
        for prediction in predictions:
            cursor.execute("""
                INSERT INTO stock_predictions 
                (symbol, prediction_date, predicted_return, confidence_score, technical_score, llm_score, llm_recommendation)
                VALUES (%(symbol)s, %(prediction_date)s, %(predicted_return)s, %(confidence_score)s, 
                        %(technical_score)s, %(llm_score)s, %(llm_recommendation)s)
            """, prediction)
        self.db.commit()
        cursor.close()
    
    # 断言方法
    def assert_trade_executed(self, symbol: str, action: str, expected_quantity: int, test_mode: int = 0):
        """断言交易已执行"""
        cursor = self.get_cursor()
        cursor.execute("""
            SELECT * FROM trades 
            WHERE symbol=%s AND action=%s AND test_mode=%s 
            ORDER BY trade_time DESC LIMIT 1
        """, (symbol, action, test_mode))
        trade = cursor.fetchone()
        cursor.close()
        
        assert trade is not None, f"未找到 {symbol} 的 {action} 交易记录"
        assert trade['quantity'] == expected_quantity, f"交易数量不匹配: 期望 {expected_quantity}, 实际 {trade['quantity']}"
    
    def assert_position_exists(self, symbol: str, expected_quantity: int, test_mode: int = 0):
        """断言持仓存在"""
        cursor = self.get_cursor()
        cursor.execute("""
            SELECT * FROM positions 
            WHERE symbol=%s AND test_mode=%s
        """, (symbol, test_mode))
        position = cursor.fetchone()
        cursor.close()
        
        assert position is not None, f"未找到 {symbol} 的持仓记录"
        assert position['quantity'] == expected_quantity, f"持仓数量不匹配: 期望 {expected_quantity}, 实际 {position['quantity']}"
    
    def assert_no_position(self, symbol: str, test_mode: int = 0):
        """断言不存在持仓"""
        cursor = self.get_cursor()
        cursor.execute("""
            SELECT * FROM positions 
            WHERE symbol=%s AND test_mode=%s
        """, (symbol, test_mode))
        position = cursor.fetchone()
        cursor.close()
        
        assert position is None, f"不应该存在 {symbol} 的持仓记录"
    
    def assert_data_isolation(self, test_mode: int):
        """断言数据隔离正确"""
        cursor = self.get_cursor()
        
        # 检查交易记录隔离
        cursor.execute("SELECT COUNT(*) as count FROM trades WHERE test_mode != %s", (test_mode,))
        other_trades = cursor.fetchone()['count']
        
        # 检查持仓记录隔离
        cursor.execute("SELECT COUNT(*) as count FROM positions WHERE test_mode != %s", (test_mode,))
        other_positions = cursor.fetchone()['count']
        
        cursor.close()
        
        assert other_trades == 0, f"发现其他模式的交易记录: {other_trades} 条"
        assert other_positions == 0, f"发现其他模式的持仓记录: {other_positions} 条"
    
    def assert_prediction_created(self, symbol: str, prediction_date: Optional[datetime] = None):
        """断言预测记录已创建"""
        cursor = self.get_cursor()
        
        if prediction_date:
            cursor.execute("""
                SELECT * FROM stock_predictions 
                WHERE symbol=%s AND prediction_date=%s
            """, (symbol, prediction_date.date()))
        else:
            cursor.execute("""
                SELECT * FROM stock_predictions 
                WHERE symbol=%s ORDER BY created_at DESC LIMIT 1
            """, (symbol,))
        
        prediction = cursor.fetchone()
        cursor.close()
        
        assert prediction is not None, f"未找到 {symbol} 的预测记录"
        return prediction
    
    def assert_system_config_updated(self, key: str, expected_value: Any):
        """断言系统配置已更新"""
        cursor = self.get_cursor()
        cursor.execute("SELECT config_value FROM system_config WHERE config_key=%s", (key,))
        result = cursor.fetchone()
        cursor.close()
        
        assert result is not None, f"未找到配置项: {key}"
        
        # 尝试解析JSON值
        import json
        try:
            actual_value = json.loads(result['config_value'])
        except:
            actual_value = result['config_value']
        
        assert actual_value == expected_value, f"配置值不匹配: 期望 {expected_value}, 实际 {actual_value}"
    
    # 工具方法
    def get_trade_count(self, symbol: Optional[str] = None, test_mode: int = 0) -> int:
        """获取交易记录数量"""
        cursor = self.get_cursor()
        
        if symbol:
            cursor.execute("SELECT COUNT(*) as count FROM trades WHERE symbol=%s AND test_mode=%s", (symbol, test_mode))
        else:
            cursor.execute("SELECT COUNT(*) as count FROM trades WHERE test_mode=%s", (test_mode,))
        
        count = cursor.fetchone()['count']
        cursor.close()
        return count
    
    def get_position_count(self, test_mode: int = 0) -> int:
        """获取持仓记录数量"""
        cursor = self.get_cursor()
        cursor.execute("SELECT COUNT(*) as count FROM positions WHERE test_mode=%s", (test_mode,))
        count = cursor.fetchone()['count']
        cursor.close()
        return count
    
    def get_latest_trade(self, symbol: str, test_mode: int = 0) -> Optional[Dict[str, Any]]:
        """获取最新交易记录"""
        cursor = self.get_cursor()
        cursor.execute("""
            SELECT * FROM trades 
            WHERE symbol=%s AND test_mode=%s 
            ORDER BY trade_time DESC LIMIT 1
        """, (symbol, test_mode))
        trade = cursor.fetchone()
        cursor.close()
        return trade
    
    def get_position(self, symbol: str, test_mode: int = 0) -> Optional[Dict[str, Any]]:
        """获取持仓记录"""
        cursor = self.get_cursor()
        cursor.execute("""
            SELECT * FROM positions 
            WHERE symbol=%s AND test_mode=%s
        """, (symbol, test_mode))
        position = cursor.fetchone()
        cursor.close()
        return position
    
    def clear_test_data(self, test_mode: int = 0):
        """清理指定模式的测试数据"""
        cursor = self.get_cursor()
        
        # 清理交易记录
        cursor.execute("DELETE FROM trades WHERE test_mode=%s", (test_mode,))
        
        # 清理持仓记录
        cursor.execute("DELETE FROM positions WHERE test_mode=%s", (test_mode,))
        
        # 清理预测记录
        cursor.execute("DELETE FROM stock_predictions WHERE DATE(prediction_date) = CURDATE()")
        
        self.db.commit()
        cursor.close()
    
    def simulate_market_movement(self, symbol: str, price_change_pct: float):
        """模拟市场价格变动"""
        # 更新Mock中的价格数据
        if hasattr(self.mock_longbridge, 'market_data') and symbol in self.mock_longbridge.market_data:
            current_data = self.mock_longbridge.market_data[symbol]
            new_price = current_data['price'] * (1 + price_change_pct / 100)
            current_data['price'] = round(new_price, 2)
            current_data['change_pct'] = price_change_pct
            current_data['change'] = round(new_price - current_data.get('open', new_price), 2)
    
    async def wait_for_async_task(self, timeout: float = 5.0):
        """等待异步任务完成"""
        await asyncio.sleep(0.1)  # 给异步任务一些执行时间
    
    def create_test_scenario(self, scenario_name: str) -> Dict[str, Any]:
        """创建测试场景"""
        scenarios = {
            'bull_market': {
                'stocks': self.data_generator.create_stock_list(5),
                'market_trend': 'up',
                'expected_actions': ['BUY'] * 5
            },
            'bear_market': {
                'stocks': self.data_generator.create_stock_list(5),
                'market_trend': 'down', 
                'expected_actions': ['SELL'] * 5
            },
            'volatile_market': {
                'stocks': self.data_generator.create_stock_list(3),
                'market_trend': 'volatile',
                'expected_actions': ['BUY', 'SELL', 'HOLD']
            }
        }
        
        return scenarios.get(scenario_name, {})


class APITestCase(BaseTestCase):
    """API测试基类"""
    
    @pytest.fixture(autouse=True)
    async def setup_api_client(self, api_client):
        """设置API客户端"""
        self.client = api_client
    
    async def login_test_user(self, username: str = "test_user", password: str = "test_password") -> Dict[str, str]:
        """登录测试用户并返回认证头"""
        # 首先注册用户
        register_data = {
            "username": username,
            "email": f"{username}@test.com",
            "password": password
        }
        
        register_response = await self.client.post("/api/auth/register", json=register_data)
        assert register_response.status_code == 200
        
        # 然后登录
        login_data = {
            "username": username,
            "password": password
        }
        
        login_response = await self.client.post("/api/auth/login", json=login_data)
        assert login_response.status_code == 200
        
        # 从响应中获取token或cookie
        token = login_response.json().get("access_token")
        if token:
            return {"Authorization": f"Bearer {token}"}
        else:
            # 如果使用cookie认证，返回空头部
            return {}
    
    async def assert_api_response(self, response, expected_status: int = 200, 
                                 expected_keys: Optional[List[str]] = None):
        """断言API响应"""
        assert response.status_code == expected_status, f"状态码不匹配: 期望 {expected_status}, 实际 {response.status_code}"
        
        if expected_keys and response.status_code == 200:
            response_data = response.json()
            for key in expected_keys:
                assert key in response_data, f"响应中缺少字段: {key}"
    
    async def assert_api_error(self, response, expected_status: int, expected_error: Optional[str] = None):
        """断言API错误响应"""
        assert response.status_code == expected_status
        
        if expected_error:
            response_data = response.json()
            error_message = response_data.get('detail', response_data.get('message', ''))
            assert expected_error in error_message, f"错误信息不匹配: 期望包含 '{expected_error}', 实际 '{error_message}'"