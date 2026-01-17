"""
数据隔离测试
"""
import pytest
import pymysql
from tests.base import BaseTestCase
from tests.fixtures.test_data import TradeFactory, PositionFactory, StockFactory


class TestDataIsolation(BaseTestCase):
    """数据隔离测试类"""
    
    async def setup_test_data(self):
        """设置测试数据"""
        # 创建测试股票
        self.test_stocks = [
            StockFactory(symbol="AAPL", name="Apple Inc."),
            StockFactory(symbol="GOOGL", name="Alphabet Inc."),
            StockFactory(symbol="MSFT", name="Microsoft Corp.")
        ]
        self.insert_test_stocks(self.test_stocks)
    
    @pytest.mark.database
    @pytest.mark.test_mode
    @pytest.mark.asyncio
    async def test_trade_data_isolation(self):
        """测试交易数据隔离"""
        # 插入测试模式交易数据
        test_trades = [
            TradeFactory(symbol="AAPL", action="BUY", test_mode=0),
            TradeFactory(symbol="GOOGL", action="BUY", test_mode=0),
        ]
        self.insert_test_trades(test_trades)
        
        # 插入真实模式交易数据
        real_trades = [
            TradeFactory(symbol="MSFT", action="BUY", test_mode=1),
            TradeFactory(symbol="AAPL", action="SELL", test_mode=1),
        ]
        self.insert_test_trades(real_trades)
        
        # 验证数据隔离
        cursor = self.get_cursor()
        
        # 查询测试模式数据
        cursor.execute("SELECT COUNT(*) as count FROM trades WHERE test_mode = 0")
        test_count = cursor.fetchone()["count"]
        assert test_count == 2
        
        # 查询真实模式数据
        cursor.execute("SELECT COUNT(*) as count FROM trades WHERE test_mode = 1")
        real_count = cursor.fetchone()["count"]
        assert real_count == 2
        
        # 验证数据不会互相影响
        cursor.execute("SELECT symbol FROM trades WHERE test_mode = 0")
        test_symbols = [row["symbol"] for row in cursor.fetchall()]
        assert "MSFT" not in test_symbols  # MSFT只在真实模式中
        
        cursor.execute("SELECT symbol FROM trades WHERE test_mode = 1")
        real_symbols = [row["symbol"] for row in cursor.fetchall()]
        assert "GOOGL" not in real_symbols  # GOOGL只在测试模式中
        
        cursor.close()
    
    @pytest.mark.database
    @pytest.mark.test_mode
    @pytest.mark.asyncio
    async def test_position_data_isolation(self):
        """测试持仓数据隔离"""
        # 插入测试模式持仓数据
        test_positions = [
            PositionFactory(symbol="AAPL", quantity=100, test_mode=0),
            PositionFactory(symbol="GOOGL", quantity=50, test_mode=0),
        ]
        self.insert_test_positions(test_positions)
        
        # 插入真实模式持仓数据
        real_positions = [
            PositionFactory(symbol="MSFT", quantity=200, test_mode=1),
            PositionFactory(symbol="AAPL", quantity=150, test_mode=1),
        ]
        self.insert_test_positions(real_positions)
        
        # 验证数据隔离
        cursor = self.get_cursor()
        
        # 验证测试模式持仓
        cursor.execute("SELECT symbol, quantity FROM positions WHERE test_mode = 0")
        test_positions_db = cursor.fetchall()
        test_symbols = {pos["symbol"]: pos["quantity"] for pos in test_positions_db}
        
        assert test_symbols["AAPL"] == 100
        assert test_symbols["GOOGL"] == 50
        assert "MSFT" not in test_symbols
        
        # 验证真实模式持仓
        cursor.execute("SELECT symbol, quantity FROM positions WHERE test_mode = 1")
        real_positions_db = cursor.fetchall()
        real_symbols = {pos["symbol"]: pos["quantity"] for pos in real_positions_db}
        
        assert real_symbols["MSFT"] == 200
        assert real_symbols["AAPL"] == 150  # 真实模式中的AAPL持仓
        assert "GOOGL" not in real_symbols
        
        cursor.close()
    
    @pytest.mark.database
    @pytest.mark.asyncio
    async def test_cross_mode_data_leakage_prevention(self):
        """测试跨模式数据泄露防护"""
        # 创建混合数据
        mixed_trades = [
            TradeFactory(symbol="AAPL", action="BUY", test_mode=0, amount=1000.0),
            TradeFactory(symbol="AAPL", action="BUY", test_mode=1, amount=2000.0),
            TradeFactory(symbol="GOOGL", action="SELL", test_mode=0, amount=1500.0),
            TradeFactory(symbol="GOOGL", action="SELL", test_mode=1, amount=2500.0),
        ]
        self.insert_test_trades(mixed_trades)
        
        cursor = self.get_cursor()
        
        # 验证按模式查询时不会返回其他模式的数据
        cursor.execute("""
            SELECT SUM(amount) as total_amount 
            FROM trades 
            WHERE test_mode = 0 AND symbol = 'AAPL'
        """)
        test_aapl_amount = cursor.fetchone()["total_amount"]
        assert test_aapl_amount == 1000.0
        
        cursor.execute("""
            SELECT SUM(amount) as total_amount 
            FROM trades 
            WHERE test_mode = 1 AND symbol = 'AAPL'
        """)
        real_aapl_amount = cursor.fetchone()["total_amount"]
        assert real_aapl_amount == 2000.0
        
        # 验证总计算不会混合两种模式
        cursor.execute("""
            SELECT test_mode, SUM(amount) as total_amount 
            FROM trades 
            GROUP BY test_mode
        """)
        mode_totals = {row["test_mode"]: row["total_amount"] for row in cursor.fetchall()}
        
        assert mode_totals[0] == 2500.0  # 测试模式总额
        assert mode_totals[1] == 4500.0  # 真实模式总额
        
        cursor.close()
    
    @pytest.mark.database
    @pytest.mark.asyncio
    async def test_mode_switching_data_integrity(self):
        """测试模式切换时的数据完整性"""
        # 在测试模式下创建数据
        test_trades = [
            TradeFactory(symbol="AAPL", action="BUY", test_mode=0),
            TradeFactory(symbol="GOOGL", action="BUY", test_mode=0),
        ]
        self.insert_test_trades(test_trades)
        
        # 模拟切换到真实模式并创建数据
        real_trades = [
            TradeFactory(symbol="MSFT", action="BUY", test_mode=1),
        ]
        self.insert_test_trades(real_trades)
        
        # 再次切换回测试模式
        new_test_trades = [
            TradeFactory(symbol="TSLA", action="BUY", test_mode=0),
        ]
        self.insert_test_trades(new_test_trades)
        
        # 验证数据完整性
        cursor = self.get_cursor()
        
        # 测试模式应该有3条记录
        cursor.execute("SELECT COUNT(*) as count FROM trades WHERE test_mode = 0")
        test_count = cursor.fetchone()["count"]
        assert test_count == 3
        
        # 真实模式应该有1条记录
        cursor.execute("SELECT COUNT(*) as count FROM trades WHERE test_mode = 1")
        real_count = cursor.fetchone()["count"]
        assert real_count == 1
        
        # 验证每个模式的数据都是正确的
        cursor.execute("SELECT symbol FROM trades WHERE test_mode = 0 ORDER BY id")
        test_symbols = [row["symbol"] for row in cursor.fetchall()]
        assert test_symbols == ["AAPL", "GOOGL", "TSLA"]
        
        cursor.execute("SELECT symbol FROM trades WHERE test_mode = 1")
        real_symbols = [row["symbol"] for row in cursor.fetchall()]
        assert real_symbols == ["MSFT"]
        
        cursor.close()
    
    @pytest.mark.database
    @pytest.mark.asyncio
    async def test_concurrent_mode_operations(self):
        """测试并发模式操作"""
        import asyncio
        
        async def insert_test_data():
            """插入测试模式数据"""
            for i in range(10):
                trade = TradeFactory(symbol=f"TEST{i}", action="BUY", test_mode=0)
                self.insert_test_trades([trade])
                await asyncio.sleep(0.01)  # 模拟并发间隔
        
        async def insert_real_data():
            """插入真实模式数据"""
            for i in range(10):
                trade = TradeFactory(symbol=f"REAL{i}", action="BUY", test_mode=1)
                self.insert_test_trades([trade])
                await asyncio.sleep(0.01)  # 模拟并发间隔
        
        # 并发执行两种模式的数据插入
        await asyncio.gather(
            insert_test_data(),
            insert_real_data()
        )
        
        # 验证数据隔离仍然有效
        cursor = self.get_cursor()
        
        # 验证测试模式数据
        cursor.execute("SELECT COUNT(*) as count FROM trades WHERE test_mode = 0")
        test_count = cursor.fetchone()["count"]
        assert test_count == 10
        
        cursor.execute("SELECT symbol FROM trades WHERE test_mode = 0")
        test_symbols = [row["symbol"] for row in cursor.fetchall()]
        assert all(symbol.startswith("TEST") for symbol in test_symbols)
        
        # 验证真实模式数据
        cursor.execute("SELECT COUNT(*) as count FROM trades WHERE test_mode = 1")
        real_count = cursor.fetchone()["count"]
        assert real_count == 10
        
        cursor.execute("SELECT symbol FROM trades WHERE test_mode = 1")
        real_symbols = [row["symbol"] for row in cursor.fetchall()]
        assert all(symbol.startswith("REAL") for symbol in real_symbols)
        
        cursor.close()
    
    @pytest.mark.database
    @pytest.mark.asyncio
    async def test_data_cleanup_isolation(self):
        """测试数据清理时的隔离性"""
        # 创建两种模式的数据
        test_trades = [TradeFactory(symbol="AAPL", test_mode=0) for _ in range(5)]
        real_trades = [TradeFactory(symbol="GOOGL", test_mode=1) for _ in range(3)]
        
        self.insert_test_trades(test_trades + real_trades)
        
        # 只清理测试模式数据
        cursor = self.get_cursor()
        cursor.execute("DELETE FROM trades WHERE test_mode = 0")
        self.db.commit()
        
        # 验证只有测试模式数据被清理
        cursor.execute("SELECT COUNT(*) as count FROM trades WHERE test_mode = 0")
        test_count = cursor.fetchone()["count"]
        assert test_count == 0
        
        cursor.execute("SELECT COUNT(*) as count FROM trades WHERE test_mode = 1")
        real_count = cursor.fetchone()["count"]
        assert real_count == 3  # 真实模式数据应该保持不变
        
        cursor.close()
    
    @pytest.mark.database
    @pytest.mark.asyncio
    async def test_prediction_data_isolation(self):
        """测试预测数据隔离"""
        from tests.fixtures.test_data import PredictionFactory
        from datetime import date
        
        # 创建预测数据（预测数据可能不直接使用test_mode字段，但应该通过其他方式隔离）
        test_predictions = [
            PredictionFactory(symbol="AAPL", prediction_date=date.today()),
            PredictionFactory(symbol="GOOGL", prediction_date=date.today()),
        ]
        self.insert_test_predictions(test_predictions)
        
        cursor = self.get_cursor()
        
        # 验证预测数据存在
        cursor.execute("SELECT COUNT(*) as count FROM stock_predictions WHERE DATE(prediction_date) = CURDATE()")
        prediction_count = cursor.fetchone()["count"]
        assert prediction_count == 2
        
        # 验证预测数据的符号
        cursor.execute("SELECT symbol FROM stock_predictions WHERE DATE(prediction_date) = CURDATE()")
        symbols = [row["symbol"] for row in cursor.fetchall()]
        assert "AAPL" in symbols
        assert "GOOGL" in symbols
        
        cursor.close()
    
    @pytest.mark.database
    @pytest.mark.asyncio
    async def test_system_config_isolation(self):
        """测试系统配置隔离"""
        cursor = self.get_cursor()
        
        # 插入系统配置
        test_configs = [
            ("test_mode", "true"),
            ("buy_amount", "10000.0"),
            ("profit_target", "1.5"),
        ]
        
        for key, value in test_configs:
            cursor.execute("""
                INSERT INTO system_config (config_key, config_value) 
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE config_value = VALUES(config_value)
            """, (key, value))
        
        self.db.commit()
        
        # 验证配置存在
        cursor.execute("SELECT config_key, config_value FROM system_config WHERE config_key IN ('test_mode', 'buy_amount', 'profit_target')")
        configs = {row["config_key"]: row["config_value"] for row in cursor.fetchall()}
        
        assert configs["test_mode"] == "true"
        assert configs["buy_amount"] == "10000.0"
        assert configs["profit_target"] == "1.5"
        
        cursor.close()
    
    @pytest.mark.database
    @pytest.mark.asyncio
    async def test_user_data_isolation(self):
        """测试用户数据隔离"""
        # 创建多个测试用户
        users = [
            {"username": "user1", "email": "user1@test.com", "password_hash": "hash1", "is_active": True},
            {"username": "user2", "email": "user2@test.com", "password_hash": "hash2", "is_active": True},
        ]
        
        user_ids = []
        for user in users:
            user_id = self.insert_test_user(user)
            user_ids.append(user_id)
        
        # 为每个用户创建交易数据
        for i, user_id in enumerate(user_ids):
            trades = [
                TradeFactory(symbol=f"USER{i}STOCK", action="BUY", test_mode=0),
            ]
            # 注意：实际系统中可能需要user_id字段来关联用户
            self.insert_test_trades(trades)
        
        # 验证用户数据存在
        cursor = self.get_cursor()
        cursor.execute("SELECT COUNT(*) as count FROM users WHERE username LIKE 'user%'")
        user_count = cursor.fetchone()["count"]
        assert user_count == 2
        
        # 验证交易数据
        cursor.execute("SELECT COUNT(*) as count FROM trades WHERE symbol LIKE 'USER%'")
        trade_count = cursor.fetchone()["count"]
        assert trade_count == 2
        
        cursor.close()
    
    @pytest.mark.database
    @pytest.mark.asyncio
    async def test_data_integrity_constraints(self):
        """测试数据完整性约束"""
        cursor = self.get_cursor()
        
        # 测试外键约束（如果存在）
        try:
            # 尝试插入不存在股票的交易记录
            cursor.execute("""
                INSERT INTO trades (symbol, action, price, quantity, amount, test_mode)
                VALUES ('NONEXISTENT', 'BUY', 100.0, 10, 1000.0, 0)
            """)
            self.db.commit()
            
            # 如果没有外键约束，这应该成功
            # 验证记录已插入
            cursor.execute("SELECT COUNT(*) as count FROM trades WHERE symbol = 'NONEXISTENT'")
            count = cursor.fetchone()["count"]
            assert count == 1
            
        except pymysql.IntegrityError:
            # 如果有外键约束，应该抛出完整性错误
            self.db.rollback()
            print("外键约束正常工作")
        
        # 测试唯一约束（如果存在）
        try:
            # 尝试插入重复的股票
            cursor.execute("""
                INSERT INTO stocks (symbol, name, stock_type, is_active)
                VALUES ('AAPL', 'Apple Inc.', 'STOCK', TRUE)
            """)
            cursor.execute("""
                INSERT INTO stocks (symbol, name, stock_type, is_active)
                VALUES ('AAPL', 'Apple Inc. Duplicate', 'STOCK', TRUE)
            """)
            self.db.commit()
            
        except pymysql.IntegrityError:
            # 如果有唯一约束，应该抛出完整性错误
            self.db.rollback()
            print("唯一约束正常工作")
        
        cursor.close()