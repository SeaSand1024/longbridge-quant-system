"""
Bug 验证测试 - 测试系统中发现的潜在问题
"""
import pytest
import requests
import sys
import time
import pymysql
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

BASE_URL = "http://localhost:8000"


class TestBugVerification:
    """验证已发现的Bug"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """设置测试环境"""
        self.session = requests.Session()
        # 登录获取认证
        username = f"bugtest_{int(time.time())}"
        self.session.post(
            f"{BASE_URL}/api/auth/register",
            json={"username": username, "email": f"{username}@test.com", "password": "TestPass123"}
        )
        self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": username, "password": "TestPass123"}
        )
    
    def test_bug7_positions_symbol_unique_constraint(self):
        """
        Bug 7: positions 表 symbol 唯一约束问题
        修复后：同一股票可以同时在测试模式和真实模式下存在持仓
        """
        from app.config.database import get_db_connection
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            # 清理测试数据
            cursor.execute("DELETE FROM positions WHERE symbol = 'BUGTEST'")
            conn.commit()
            
            # 插入测试模式持仓
            cursor.execute("""
                INSERT INTO positions (symbol, quantity, buy_price, cost, test_mode)
                VALUES ('BUGTEST', 100, 150.0, 15000.0, 1)
            """)
            conn.commit()
            
            # 插入真实模式持仓（修复后应该成功）
            cursor.execute("""
                INSERT INTO positions (symbol, quantity, buy_price, cost, test_mode)
                VALUES ('BUGTEST', 100, 150.0, 15000.0, 0)
            """)
            conn.commit()
            
            # 验证两条记录都存在
            cursor.execute("SELECT COUNT(*) FROM positions WHERE symbol = 'BUGTEST'")
            count = cursor.fetchone()[0]
            assert count == 2, f"应该有2条记录，实际有{count}条"
            print(f"\n✅ Bug 7 已修复: 同一股票可以在不同模式下各有一条持仓记录")
            
        finally:
            cursor.execute("DELETE FROM positions WHERE symbol = 'BUGTEST'")
            conn.commit()
            cursor.close()
            conn.close()
    
    def test_bug6_check_buy_signal_missing_test_mode(self):
        """
        Bug 6: check_buy_signal 查询持仓数量时没有加 test_mode 条件
        """
        from app.services.trading_strategy import TradingStrategy
        from app.config.database import get_db_connection
        import inspect
        
        strategy = TradingStrategy()
        
        # 检查源代码中是否包含 test_mode 条件
        source = inspect.getsource(strategy.check_buy_signal)
        
        if "test_mode" not in source:
            print("\n❌ Bug 6 确认: check_buy_signal 方法中没有 test_mode 条件")
            pytest.fail("Bug 6: check_buy_signal 缺少 test_mode 条件")
        else:
            print("\n✅ Bug 6 可能已修复: check_buy_signal 包含 test_mode")
    
    def test_bug9_sell_missing_test_mode(self):
        """
        Bug 9: 卖出时未区分 test_mode
        """
        from app.services.trading_strategy import TradingStrategy
        import inspect
        
        strategy = TradingStrategy()
        
        # 检查 execute_sell 方法
        source = inspect.getsource(strategy.execute_sell)
        
        # 检查 UPDATE positions 语句是否包含 test_mode
        if "UPDATE positions" in source:
            # 查找 UPDATE 语句后是否有 test_mode 条件
            update_idx = source.find("UPDATE positions")
            where_part = source[update_idx:update_idx+500]  # 取后面一段检查
            
            if "test_mode" not in where_part.split("WHERE")[1] if "WHERE" in where_part else "":
                print("\n❌ Bug 9 确认: execute_sell UPDATE 语句缺少 test_mode 条件")
                pytest.fail("Bug 9: execute_sell 缺少 test_mode 条件")
    
    def test_bug4_logout_refresh_token_not_deleted(self):
        """
        Bug 4: 登出时未清理数据库中的 refresh_token
        """
        from app.routers.auth import logout
        import inspect
        
        source = inspect.getsource(logout)
        
        if "DELETE" not in source and "refresh_token" not in source.lower():
            print("\n❌ Bug 4 确认: logout 没有清理数据库中的 refresh_token")
            # 不标记为失败，只是警告
    
    def test_bug13_secret_key_dynamic(self):
        """
        Bug 13: SECRET_KEY 每次启动可能变化
        """
        import os
        from app.config.settings import SECRET_KEY
        
        env_key = os.getenv('SECRET_KEY')
        
        if env_key is None:
            print("\n⚠️ Bug 13 警告: SECRET_KEY 未在环境变量中设置")
            print("   每次重启应用会生成新密钥，导致所有token失效")
    
    def test_bug22_test_mode_frequent_db_query(self):
        """
        Bug 22: is_test_mode() 每次调用都查询数据库
        """
        from app.auth.utils import is_test_mode
        import time
        
        # 测量多次调用的时间
        start = time.time()
        for _ in range(100):
            is_test_mode()
        elapsed = time.time() - start
        
        # 如果100次调用超过1秒，说明每次都在查询数据库
        if elapsed > 1.0:
            print(f"\n⚠️ Bug 22 警告: 100次 is_test_mode() 调用耗时 {elapsed:.2f}s")
            print("   建议添加缓存机制")
    
    def test_bug15_execute_buy_empty_implementation(self):
        """
        Bug 15: 智能交易买入接口是空实现
        """
        response = self.session.post(f"{BASE_URL}/api/smart-trade/execute-buy")
        
        if response.status_code == 200:
            data = response.json()
            # 检查是否真的执行了买入
            print(f"\n⚠️ Bug 15 警告: execute-buy 返回成功但可能是空实现")
            print(f"   响应: {data}")
    
    def test_bug3_weak_password_allowed(self):
        """
        Bug 3: 注册时缺少密码强度验证
        """
        # 尝试使用弱密码注册
        weak_passwords = ["1", "123", "abc", ""]
        
        for pwd in weak_passwords:
            username = f"weakpwd_{int(time.time())}_{len(pwd)}"
            response = requests.post(
                f"{BASE_URL}/api/auth/register",
                json={"username": username, "email": f"{username}@test.com", "password": pwd}
            )
            
            if response.status_code == 200:
                print(f"\n❌ Bug 3 确认: 弱密码 '{pwd}' 注册成功")
    
    def test_bug18_symbol_length_limit(self):
        """
        Bug 18: 股票代码长度限制（VARCHAR(10)）
        """
        from app.config.database import get_db_connection
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 期权代码通常很长
        long_symbol = "AAPL240119C00180000"  # 19字符
        
        try:
            cursor.execute("""
                INSERT INTO stocks (symbol, name, is_active)
                VALUES (%s, 'Test Option', 1)
            """, (long_symbol,))
            conn.commit()
            print(f"\n✅ 股票代码 '{long_symbol}' 插入成功")
        except pymysql.err.DataError as e:
            print(f"\n❌ Bug 18 确认: 长股票代码插入失败 - {e}")
        finally:
            cursor.execute("DELETE FROM stocks WHERE symbol = %s", (long_symbol,))
            conn.commit()
            cursor.close()
            conn.close()
    
    def test_bug21_created_at_default_zero(self):
        """
        Bug 21: created_at DEFAULT 0 导致默认值为 1970-01-01
        """
        from app.config.database import get_db_connection
        
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        try:
            # 插入一条记录，不指定 created_at
            cursor.execute("""
                INSERT INTO stocks (symbol, name, is_active)
                VALUES ('BUG21TEST', 'Test Stock', 1)
            """)
            conn.commit()
            
            cursor.execute("SELECT created_at FROM stocks WHERE symbol = 'BUG21TEST'")
            result = cursor.fetchone()
            
            if result:
                created_at = result['created_at']
                if created_at and created_at.year == 1970:
                    print(f"\n❌ Bug 21 确认: created_at 默认值为 {created_at}")
                else:
                    print(f"\n✅ created_at 正常: {created_at}")
        finally:
            cursor.execute("DELETE FROM stocks WHERE symbol = 'BUG21TEST'")
            conn.commit()
            cursor.close()
            conn.close()


class TestBugCalculations:
    """测试计算相关的Bug"""
    
    def test_bug8_buy_price_calculation(self):
        """
        Bug 8: 买入时持仓平均价计算公式错误
        """
        from app.services.trading_strategy import TradingStrategy
        import inspect
        
        strategy = TradingStrategy()
        
        source = inspect.getsource(strategy.execute_buy)
        
        # 检查是否有 ON DUPLICATE KEY UPDATE
        if "ON DUPLICATE KEY UPDATE" in source:
            # 检查 buy_price 的计算公式
            if "buy_price = (cost + VALUES(cost)) / (quantity + VALUES(quantity))" in source:
                print("\n❌ Bug 8 确认: buy_price 计算公式有误")
                print("   问题: cost 和 quantity 的更新顺序会导致计算错误")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("Bug 验证测试")
    print("="*60)
    
    # 运行测试
    pytest.main([__file__, "-v", "-s", "--tb=short"])
