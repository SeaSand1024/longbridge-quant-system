"""
CRUD操作测试
"""
import pytest
import pymysql
from datetime import datetime, date
from tests.base import BaseTestCase
from tests.fixtures.test_data import StockFactory, TradeFactory, PositionFactory, UserFactory


class TestCRUDOperations(BaseTestCase):
    """CRUD操作测试类"""
    
    @pytest.mark.database
    @pytest.mark.asyncio
    async def test_stock_crud_operations(self):
        """测试股票CRUD操作"""
        cursor = self.get_cursor()
        
        # Create - 创建股票
        stock_data = {
            "symbol": "CRUD_TEST",
            "name": "CRUD Test Stock",
            "stock_type": "STOCK",
            "group_name": "Test",
            "is_active": True
        }
        
        cursor.execute("""
            INSERT INTO stocks (symbol, name, stock_type, group_name, is_active)
            VALUES (%(symbol)s, %(name)s, %(stock_type)s, %(group_name)s, %(is_active)s)
        """, stock_data)
        stock_id = cursor.lastrowid
        self.db.commit()
        
        # Read - 读取股票
        cursor.execute("SELECT * FROM stocks WHERE id = %s", (stock_id,))
        created_stock = cursor.fetchone()
        
        assert created_stock is not None
        assert created_stock["symbol"] == stock_data["symbol"]
        assert created_stock["name"] == stock_data["name"]
        assert created_stock["is_active"] == stock_data["is_active"]
        
        # Update - 更新股票
        updated_name = "Updated CRUD Test Stock"
        cursor.execute("""
            UPDATE stocks SET name = %s, is_active = FALSE 
            WHERE id = %s
        """, (updated_name, stock_id))
        self.db.commit()
        
        # 验证更新
        cursor.execute("SELECT * FROM stocks WHERE id = %s", (stock_id,))
        updated_stock = cursor.fetchone()
        
        assert updated_stock["name"] == updated_name
        assert updated_stock["is_active"] is False
        
        # Delete - 删除股票
        cursor.execute("DELETE FROM stocks WHERE id = %s", (stock_id,))
        self.db.commit()
        
        # 验证删除
        cursor.execute("SELECT * FROM stocks WHERE id = %s", (stock_id,))
        deleted_stock = cursor.fetchone()
        
        assert deleted_stock is None
        
        cursor.close()
    
    @pytest.mark.database
    @pytest.mark.asyncio
    async def test_trade_crud_operations(self):
        """测试交易记录CRUD操作"""
        # 先创建股票
        stock = StockFactory(symbol="TRADE_TEST")
        self.insert_test_stocks([stock])
        
        cursor = self.get_cursor()
        
        # Create - 创建交易记录
        trade_data = {
            "symbol": "TRADE_TEST",
            "action": "BUY",
            "price": 150.50,
            "quantity": 100,
            "amount": 15050.0,
            "acceleration": 0.001,
            "test_mode": 0
        }
        
        cursor.execute("""
            INSERT INTO trades (symbol, action, price, quantity, amount, acceleration, test_mode, trade_time)
            VALUES (%(symbol)s, %(action)s, %(price)s, %(quantity)s, %(amount)s, %(acceleration)s, %(test_mode)s, NOW())
        """, trade_data)
        trade_id = cursor.lastrowid
        self.db.commit()
        
        # Read - 读取交易记录
        cursor.execute("SELECT * FROM trades WHERE id = %s", (trade_id,))
        created_trade = cursor.fetchone()
        
        assert created_trade is not None
        assert created_trade["symbol"] == trade_data["symbol"]
        assert created_trade["action"] == trade_data["action"]
        assert float(created_trade["price"]) == trade_data["price"]
        assert created_trade["quantity"] == trade_data["quantity"]
        
        # Update - 更新交易记录（通常交易记录不允许修改，但测试CRUD功能）
        updated_price = 155.75
        cursor.execute("""
            UPDATE trades SET price = %s, amount = %s 
            WHERE id = %s
        """, (updated_price, updated_price * trade_data["quantity"], trade_id))
        self.db.commit()
        
        # 验证更新
        cursor.execute("SELECT * FROM trades WHERE id = %s", (trade_id,))
        updated_trade = cursor.fetchone()
        
        assert float(updated_trade["price"]) == updated_price
        assert float(updated_trade["amount"]) == updated_price * trade_data["quantity"]
        
        # Delete - 删除交易记录
        cursor.execute("DELETE FROM trades WHERE id = %s", (trade_id,))
        self.db.commit()
        
        # 验证删除
        cursor.execute("SELECT * FROM trades WHERE id = %s", (trade_id,))
        deleted_trade = cursor.fetchone()
        
        assert deleted_trade is None
        
        cursor.close()
    
    @pytest.mark.database
    @pytest.mark.asyncio
    async def test_position_crud_operations(self):
        """测试持仓CRUD操作"""
        # 先创建股票
        stock = StockFactory(symbol="POS_TEST")
        self.insert_test_stocks([stock])
        
        cursor = self.get_cursor()
        
        # Create - 创建持仓
        position_data = {
            "symbol": "POS_TEST",
            "quantity": 200,
            "avg_cost": 120.0,
            "current_price": 125.0,
            "profit_loss": 1000.0,
            "profit_loss_pct": 4.17,
            "test_mode": 0
        }
        
        cursor.execute("""
            INSERT INTO positions (symbol, quantity, avg_cost, current_price, profit_loss, profit_loss_pct, test_mode)
            VALUES (%(symbol)s, %(quantity)s, %(avg_cost)s, %(current_price)s, %(profit_loss)s, %(profit_loss_pct)s, %(test_mode)s)
        """, position_data)
        position_id = cursor.lastrowid
        self.db.commit()
        
        # Read - 读取持仓
        cursor.execute("SELECT * FROM positions WHERE id = %s", (position_id,))
        created_position = cursor.fetchone()
        
        assert created_position is not None
        assert created_position["symbol"] == position_data["symbol"]
        assert created_position["quantity"] == position_data["quantity"]
        assert float(created_position["avg_cost"]) == position_data["avg_cost"]
        
        # Update - 更新持仓
        new_quantity = 250
        new_current_price = 130.0
        new_profit_loss = (new_current_price - position_data["avg_cost"]) * new_quantity
        
        cursor.execute("""
            UPDATE positions 
            SET quantity = %s, current_price = %s, profit_loss = %s
            WHERE id = %s
        """, (new_quantity, new_current_price, new_profit_loss, position_id))
        self.db.commit()
        
        # 验证更新
        cursor.execute("SELECT * FROM positions WHERE id = %s", (position_id,))
        updated_position = cursor.fetchone()
        
        assert updated_position["quantity"] == new_quantity
        assert float(updated_position["current_price"]) == new_current_price
        assert float(updated_position["profit_loss"]) == new_profit_loss
        
        # Delete - 删除持仓
        cursor.execute("DELETE FROM positions WHERE id = %s", (position_id,))
        self.db.commit()
        
        # 验证删除
        cursor.execute("SELECT * FROM positions WHERE id = %s", (position_id,))
        deleted_position = cursor.fetchone()
        
        assert deleted_position is None
        
        cursor.close()
    
    @pytest.mark.database
    @pytest.mark.asyncio
    async def test_user_crud_operations(self):
        """测试用户CRUD操作"""
        cursor = self.get_cursor()
        
        # Create - 创建用户
        user_data = {
            "username": "crud_test_user",
            "email": "crud@test.com",
            "password_hash": "$2b$12$test_hash_for_crud_testing",
            "is_active": True
        }
        
        cursor.execute("""
            INSERT INTO users (username, email, password_hash, is_active)
            VALUES (%(username)s, %(email)s, %(password_hash)s, %(is_active)s)
        """, user_data)
        user_id = cursor.lastrowid
        self.db.commit()
        
        # Read - 读取用户
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        created_user = cursor.fetchone()
        
        assert created_user is not None
        assert created_user["username"] == user_data["username"]
        assert created_user["email"] == user_data["email"]
        assert created_user["is_active"] == user_data["is_active"]
        
        # Update - 更新用户
        updated_email = "updated_crud@test.com"
        cursor.execute("""
            UPDATE users SET email = %s, is_active = FALSE 
            WHERE id = %s
        """, (updated_email, user_id))
        self.db.commit()
        
        # 验证更新
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        updated_user = cursor.fetchone()
        
        assert updated_user["email"] == updated_email
        assert updated_user["is_active"] is False
        
        # Delete - 删除用户
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        self.db.commit()
        
        # 验证删除
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        deleted_user = cursor.fetchone()
        
        assert deleted_user is None
        
        cursor.close()
    
    @pytest.mark.database
    @pytest.mark.asyncio
    async def test_prediction_crud_operations(self):
        """测试预测数据CRUD操作"""
        # 先创建股票
        stock = StockFactory(symbol="PRED_TEST")
        self.insert_test_stocks([stock])
        
        cursor = self.get_cursor()
        
        # Create - 创建预测记录
        prediction_data = {
            "symbol": "PRED_TEST",
            "prediction_date": date.today(),
            "predicted_return": 2.5,
            "confidence_score": 0.85,
            "technical_score": 75.5,
            "llm_score": 80.0,
            "llm_recommendation": "buy"
        }
        
        cursor.execute("""
            INSERT INTO stock_predictions 
            (symbol, prediction_date, predicted_return, confidence_score, technical_score, llm_score, llm_recommendation)
            VALUES (%(symbol)s, %(prediction_date)s, %(predicted_return)s, %(confidence_score)s, 
                    %(technical_score)s, %(llm_score)s, %(llm_recommendation)s)
        """, prediction_data)
        prediction_id = cursor.lastrowid
        self.db.commit()
        
        # Read - 读取预测记录
        cursor.execute("SELECT * FROM stock_predictions WHERE id = %s", (prediction_id,))
        created_prediction = cursor.fetchone()
        
        assert created_prediction is not None
        assert created_prediction["symbol"] == prediction_data["symbol"]
        assert float(created_prediction["predicted_return"]) == prediction_data["predicted_return"]
        assert float(created_prediction["confidence_score"]) == prediction_data["confidence_score"]
        
        # Update - 更新预测记录
        updated_return = 3.0
        updated_confidence = 0.90
        
        cursor.execute("""
            UPDATE stock_predictions 
            SET predicted_return = %s, confidence_score = %s
            WHERE id = %s
        """, (updated_return, updated_confidence, prediction_id))
        self.db.commit()
        
        # 验证更新
        cursor.execute("SELECT * FROM stock_predictions WHERE id = %s", (prediction_id,))
        updated_prediction = cursor.fetchone()
        
        assert float(updated_prediction["predicted_return"]) == updated_return
        assert float(updated_prediction["confidence_score"]) == updated_confidence
        
        # Delete - 删除预测记录
        cursor.execute("DELETE FROM stock_predictions WHERE id = %s", (prediction_id,))
        self.db.commit()
        
        # 验证删除
        cursor.execute("SELECT * FROM stock_predictions WHERE id = %s", (prediction_id,))
        deleted_prediction = cursor.fetchone()
        
        assert deleted_prediction is None
        
        cursor.close()
    
    @pytest.mark.database
    @pytest.mark.asyncio
    async def test_batch_operations(self):
        """测试批量操作"""
        cursor = self.get_cursor()
        
        # 批量插入股票
        stocks_data = [
            ("BATCH1", "Batch Stock 1", "STOCK", "Batch", True),
            ("BATCH2", "Batch Stock 2", "STOCK", "Batch", True),
            ("BATCH3", "Batch Stock 3", "STOCK", "Batch", True),
        ]
        
        cursor.executemany("""
            INSERT INTO stocks (symbol, name, stock_type, group_name, is_active)
            VALUES (%s, %s, %s, %s, %s)
        """, stocks_data)
        self.db.commit()
        
        # 验证批量插入
        cursor.execute("SELECT COUNT(*) as count FROM stocks WHERE symbol LIKE 'BATCH%'")
        count = cursor.fetchone()["count"]
        assert count == 3
        
        # 批量更新
        cursor.execute("UPDATE stocks SET is_active = FALSE WHERE symbol LIKE 'BATCH%'")
        affected_rows = cursor.rowcount
        self.db.commit()
        
        assert affected_rows == 3
        
        # 验证批量更新
        cursor.execute("SELECT COUNT(*) as count FROM stocks WHERE symbol LIKE 'BATCH%' AND is_active = FALSE")
        count = cursor.fetchone()["count"]
        assert count == 3
        
        # 批量删除
        cursor.execute("DELETE FROM stocks WHERE symbol LIKE 'BATCH%'")
        deleted_rows = cursor.rowcount
        self.db.commit()
        
        assert deleted_rows == 3
        
        # 验证批量删除
        cursor.execute("SELECT COUNT(*) as count FROM stocks WHERE symbol LIKE 'BATCH%'")
        count = cursor.fetchone()["count"]
        assert count == 0
        
        cursor.close()
    
    @pytest.mark.database
    @pytest.mark.asyncio
    async def test_transaction_operations(self):
        """测试事务操作"""
        cursor = self.get_cursor()
        
        try:
            # 开始事务
            cursor.execute("START TRANSACTION")
            
            # 插入股票
            cursor.execute("""
                INSERT INTO stocks (symbol, name, stock_type, is_active)
                VALUES ('TRANS_TEST', 'Transaction Test Stock', 'STOCK', TRUE)
            """)
            
            # 插入交易记录
            cursor.execute("""
                INSERT INTO trades (symbol, action, price, quantity, amount, test_mode, trade_time)
                VALUES ('TRANS_TEST', 'BUY', 100.0, 10, 1000.0, 0, NOW())
            """)
            
            # 提交事务
            cursor.execute("COMMIT")
            
            # 验证数据已提交
            cursor.execute("SELECT COUNT(*) as count FROM stocks WHERE symbol = 'TRANS_TEST'")
            stock_count = cursor.fetchone()["count"]
            assert stock_count == 1
            
            cursor.execute("SELECT COUNT(*) as count FROM trades WHERE symbol = 'TRANS_TEST'")
            trade_count = cursor.fetchone()["count"]
            assert trade_count == 1
            
        except Exception as e:
            # 如果出错，回滚事务
            cursor.execute("ROLLBACK")
            raise e
        
        # 测试事务回滚
        try:
            cursor.execute("START TRANSACTION")
            
            # 插入数据
            cursor.execute("""
                INSERT INTO stocks (symbol, name, stock_type, is_active)
                VALUES ('ROLLBACK_TEST', 'Rollback Test Stock', 'STOCK', TRUE)
            """)
            
            # 故意制造错误（插入重复的股票）
            cursor.execute("""
                INSERT INTO stocks (symbol, name, stock_type, is_active)
                VALUES ('ROLLBACK_TEST', 'Duplicate Stock', 'STOCK', TRUE)
            """)
            
            cursor.execute("COMMIT")
            
        except pymysql.IntegrityError:
            # 回滚事务
            cursor.execute("ROLLBACK")
            
            # 验证数据已回滚
            cursor.execute("SELECT COUNT(*) as count FROM stocks WHERE symbol = 'ROLLBACK_TEST'")
            count = cursor.fetchone()["count"]
            assert count == 0
        
        cursor.close()
    
    @pytest.mark.database
    @pytest.mark.asyncio
    async def test_complex_queries(self):
        """测试复杂查询操作"""
        # 创建测试数据
        stocks = [
            StockFactory(symbol="COMPLEX1", group_name="Tech"),
            StockFactory(symbol="COMPLEX2", group_name="Finance"),
            StockFactory(symbol="COMPLEX3", group_name="Tech"),
        ]
        self.insert_test_stocks(stocks)
        
        trades = [
            TradeFactory(symbol="COMPLEX1", action="BUY", amount=1000.0, test_mode=0),
            TradeFactory(symbol="COMPLEX1", action="SELL", amount=1100.0, test_mode=0),
            TradeFactory(symbol="COMPLEX2", action="BUY", amount=2000.0, test_mode=0),
            TradeFactory(symbol="COMPLEX3", action="BUY", amount=1500.0, test_mode=1),
        ]
        self.insert_test_trades(trades)
        
        cursor = self.get_cursor()
        
        # 复杂查询1：按分组统计交易金额
        cursor.execute("""
            SELECT s.group_name, SUM(t.amount) as total_amount, COUNT(t.id) as trade_count
            FROM stocks s
            LEFT JOIN trades t ON s.symbol = t.symbol AND t.test_mode = 0
            GROUP BY s.group_name
            ORDER BY total_amount DESC
        """)
        group_stats = cursor.fetchall()
        
        assert len(group_stats) >= 2
        
        # 验证Tech分组的统计
        tech_stats = next((stat for stat in group_stats if stat["group_name"] == "Tech"), None)
        assert tech_stats is not None
        assert float(tech_stats["total_amount"]) == 2100.0  # COMPLEX1的买入+卖出
        
        # 复杂查询2：查找盈利的交易对
        cursor.execute("""
            SELECT 
                buy.symbol,
                buy.price as buy_price,
                sell.price as sell_price,
                (sell.price - buy.price) * buy.quantity as profit
            FROM trades buy
            JOIN trades sell ON buy.symbol = sell.symbol 
                AND buy.action = 'BUY' 
                AND sell.action = 'SELL'
                AND buy.test_mode = sell.test_mode
                AND sell.trade_time > buy.trade_time
            WHERE buy.test_mode = 0
        """)
        profitable_trades = cursor.fetchall()
        
        # 应该找到COMPLEX1的买卖对
        if profitable_trades:
            complex1_trade = next((trade for trade in profitable_trades if trade["symbol"] == "COMPLEX1"), None)
            if complex1_trade:
                assert float(complex1_trade["profit"]) > 0
        
        # 复杂查询3：使用窗口函数（如果MySQL版本支持）
        try:
            cursor.execute("""
                SELECT 
                    symbol,
                    action,
                    price,
                    trade_time,
                    ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY trade_time) as trade_sequence
                FROM trades
                WHERE test_mode = 0
                ORDER BY symbol, trade_time
            """)
            windowed_results = cursor.fetchall()
            
            # 验证窗口函数结果
            if windowed_results:
                # 每个股票的第一笔交易序号应该是1
                first_trades = [trade for trade in windowed_results if trade["trade_sequence"] == 1]
                assert len(first_trades) >= 1
                
        except pymysql.OperationalError:
            # 如果MySQL版本不支持窗口函数，跳过此测试
            print("MySQL版本不支持窗口函数，跳过窗口函数测试")
        
        cursor.close()
    
    @pytest.mark.database
    @pytest.mark.asyncio
    async def test_data_type_handling(self):
        """测试数据类型处理"""
        cursor = self.get_cursor()
        
        # 测试各种数据类型
        test_data = {
            "symbol": "TYPE_TEST",
            "name": "Data Type Test Stock",
            "stock_type": "STOCK",
            "is_active": True
        }
        
        cursor.execute("""
            INSERT INTO stocks (symbol, name, stock_type, is_active)
            VALUES (%(symbol)s, %(name)s, %(stock_type)s, %(is_active)s)
        """, test_data)
        self.db.commit()
        
        # 测试DECIMAL类型
        trade_data = {
            "symbol": "TYPE_TEST",
            "action": "BUY",
            "price": 123.456789,  # 高精度小数
            "quantity": 100,
            "amount": 12345.6789,
            "acceleration": 0.001234,
            "test_mode": 0
        }
        
        cursor.execute("""
            INSERT INTO trades (symbol, action, price, quantity, amount, acceleration, test_mode, trade_time)
            VALUES (%(symbol)s, %(action)s, %(price)s, %(quantity)s, %(amount)s, %(acceleration)s, %(test_mode)s, NOW())
        """, trade_data)
        self.db.commit()
        
        # 验证数据精度
        cursor.execute("SELECT price, amount, acceleration FROM trades WHERE symbol = 'TYPE_TEST'")
        result = cursor.fetchone()
        
        # 验证DECIMAL精度保持
        assert abs(float(result["price"]) - trade_data["price"]) < 0.01
        assert abs(float(result["amount"]) - trade_data["amount"]) < 0.01
        assert abs(float(result["acceleration"]) - trade_data["acceleration"]) < 0.000001
        
        # 测试DATETIME类型
        cursor.execute("SELECT trade_time FROM trades WHERE symbol = 'TYPE_TEST'")
        result = cursor.fetchone()
        
        assert result["trade_time"] is not None
        assert isinstance(result["trade_time"], datetime)
        
        # 测试BOOLEAN类型
        cursor.execute("SELECT is_active FROM stocks WHERE symbol = 'TYPE_TEST'")
        result = cursor.fetchone()
        
        assert result["is_active"] is True
        
        cursor.close()
    
    @pytest.mark.database
    @pytest.mark.asyncio
    async def test_null_value_handling(self):
        """测试NULL值处理"""
        cursor = self.get_cursor()
        
        # 插入包含NULL值的数据
        cursor.execute("""
            INSERT INTO stocks (symbol, name, stock_type, group_name, is_active)
            VALUES ('NULL_TEST', 'Null Test Stock', 'STOCK', NULL, TRUE)
        """)
        self.db.commit()
        
        # 验证NULL值
        cursor.execute("SELECT group_name FROM stocks WHERE symbol = 'NULL_TEST'")
        result = cursor.fetchone()
        
        assert result["group_name"] is None
        
        # 测试NULL值查询
        cursor.execute("SELECT COUNT(*) as count FROM stocks WHERE group_name IS NULL")
        null_count = cursor.fetchone()["count"]
        assert null_count >= 1
        
        cursor.execute("SELECT COUNT(*) as count FROM stocks WHERE group_name IS NOT NULL")
        not_null_count = cursor.fetchone()["count"]
        
        cursor.execute("SELECT COUNT(*) as total_count FROM stocks")
        total_count = cursor.fetchone()["total_count"]
        
        assert null_count + not_null_count == total_count
        
        cursor.close()