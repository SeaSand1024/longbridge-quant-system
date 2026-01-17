"""
持仓管理API测试
"""
import pytest
from tests.base import APITestCase
from tests.fixtures.test_data import PositionFactory, TradeFactory


class TestPositionsAPI(APITestCase):
    """持仓管理API测试类"""
    
    async def setup_test_data(self):
        """设置测试数据"""
        # 创建测试用户并登录
        self.headers = await self.login_test_user()
        
        # 创建测试持仓数据
        self.test_positions = [
            PositionFactory(symbol="AAPL", quantity=100, avg_cost=150.0, current_price=155.0),
            PositionFactory(symbol="GOOGL", quantity=50, avg_cost=2800.0, current_price=2850.0),
            PositionFactory(symbol="MSFT", quantity=200, avg_cost=300.0, current_price=295.0)
        ]
        self.insert_test_positions(self.test_positions)
        
        # 创建测试交易记录
        self.test_trades = [
            TradeFactory(symbol="AAPL", action="BUY", quantity=100, price=150.0),
            TradeFactory(symbol="GOOGL", action="BUY", quantity=50, price=2800.0),
            TradeFactory(symbol="MSFT", action="BUY", quantity=200, price=300.0)
        ]
        self.insert_test_trades(self.test_trades)
        
        # 设置Mock长桥SDK持仓数据
        self.mock_longbridge.positions = [
            {
                'symbol': 'AAPL',
                'quantity': 100,
                'market_value': 15500.0,
                'cost_price': 150.0,
                'current_price': 155.0,
                'unrealized_pnl': 500.0,
                'realized_pnl': 0.0,
                'side': 'Long'
            },
            {
                'symbol': 'GOOGL',
                'quantity': 50,
                'market_value': 142500.0,
                'cost_price': 2800.0,
                'current_price': 2850.0,
                'unrealized_pnl': 2500.0,
                'realized_pnl': 0.0,
                'side': 'Long'
            }
        ]
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_get_positions_success(self):
        """测试获取持仓信息成功"""
        response = await self.client.get("/api/positions", headers=self.headers)
        
        await self.assert_api_response(response, 200, ["positions", "total_count"])
        
        response_data = response.json()
        assert isinstance(response_data["positions"], list)
        assert response_data["total_count"] >= 0
        assert len(response_data["positions"]) <= response_data["total_count"]
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_get_positions_unauthenticated(self):
        """测试未认证获取持仓信息"""
        response = await self.client.get("/api/positions")
        
        await self.assert_api_error(response, 401)
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_get_positions_with_filters(self):
        """测试带过滤条件获取持仓"""
        params = {
            "symbol": "AAPL",
            "min_quantity": 50
        }
        
        response = await self.client.get("/api/positions", 
                                       params=params, headers=self.headers)
        
        await self.assert_api_response(response, 200)
        
        response_data = response.json()
        for position in response_data["positions"]:
            if "symbol" in position:
                assert position["symbol"] == "AAPL"
            if "quantity" in position:
                assert position["quantity"] >= 50
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_get_portfolio_overview_success(self):
        """测试获取账户总览成功"""
        response = await self.client.get("/api/portfolio", headers=self.headers)
        
        await self.assert_api_response(response, 200, [
            "account_balance", "total_market_value", "total_assets",
            "unrealized_pnl", "realized_pnl", "positions_summary"
        ])
        
        response_data = response.json()
        assert isinstance(response_data["account_balance"], (int, float))
        assert isinstance(response_data["total_market_value"], (int, float))
        assert isinstance(response_data["total_assets"], (int, float))
        assert isinstance(response_data["positions_summary"], list)
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_get_portfolio_overview_calculations(self):
        """测试账户总览计算正确性"""
        response = await self.client.get("/api/portfolio", headers=self.headers)
        
        await self.assert_api_response(response, 200)
        
        response_data = response.json()
        
        # 验证总资产 = 现金余额 + 市值
        expected_total = response_data["account_balance"] + response_data["total_market_value"]
        assert abs(response_data["total_assets"] - expected_total) < 0.01
        
        # 验证持仓摘要数据
        positions_summary = response_data["positions_summary"]
        if positions_summary:
            total_positions_value = sum(pos.get("market_value", 0) for pos in positions_summary)
            assert abs(total_positions_value - response_data["total_market_value"]) < 0.01
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_get_portfolio_empty_positions(self):
        """测试空持仓时的账户总览"""
        # 清空持仓数据
        cursor = self.get_cursor()
        cursor.execute("DELETE FROM positions WHERE test_mode = 0")
        self.db.commit()
        cursor.close()
        
        # 清空Mock持仓
        self.mock_longbridge.positions = []
        
        response = await self.client.get("/api/portfolio", headers=self.headers)
        
        await self.assert_api_response(response, 200)
        
        response_data = response.json()
        assert response_data["total_market_value"] == 0
        assert len(response_data["positions_summary"]) == 0
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_positions_data_consistency(self):
        """测试持仓数据一致性"""
        # 获取持仓数据
        positions_response = await self.client.get("/api/positions", headers=self.headers)
        await self.assert_api_response(positions_response, 200)
        
        # 获取账户总览
        portfolio_response = await self.client.get("/api/portfolio", headers=self.headers)
        await self.assert_api_response(portfolio_response, 200)
        
        positions_data = positions_response.json()["positions"]
        portfolio_data = portfolio_response.json()["positions_summary"]
        
        # 验证持仓数据在两个接口中一致
        positions_symbols = {pos["symbol"] for pos in positions_data if "symbol" in pos}
        portfolio_symbols = {pos["symbol"] for pos in portfolio_data if "symbol" in pos}
        
        assert positions_symbols == portfolio_symbols
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_positions_profit_loss_calculation(self):
        """测试持仓盈亏计算"""
        response = await self.client.get("/api/positions", headers=self.headers)
        
        await self.assert_api_response(response, 200)
        
        response_data = response.json()
        
        for position in response_data["positions"]:
            if all(key in position for key in ["quantity", "avg_cost", "current_price"]):
                expected_pnl = (position["current_price"] - position["avg_cost"]) * position["quantity"]
                actual_pnl = position.get("profit_loss", 0)
                
                # 允许小的浮点数误差
                assert abs(actual_pnl - expected_pnl) < 0.01, f"盈亏计算错误: 期望 {expected_pnl}, 实际 {actual_pnl}"
                
                if position["avg_cost"] > 0:
                    expected_pnl_pct = ((position["current_price"] - position["avg_cost"]) / position["avg_cost"]) * 100
                    actual_pnl_pct = position.get("profit_loss_pct", 0)
                    
                    assert abs(actual_pnl_pct - expected_pnl_pct) < 0.01, f"盈亏百分比计算错误: 期望 {expected_pnl_pct}%, 实际 {actual_pnl_pct}%"
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_positions_real_time_update(self):
        """测试持仓实时更新"""
        # 获取初始持仓
        initial_response = await self.client.get("/api/positions", headers=self.headers)
        await self.assert_api_response(initial_response, 200)
        
        # 模拟价格变动
        self.simulate_market_movement("AAPL", 5.0)  # AAPL上涨5%
        
        # 再次获取持仓
        updated_response = await self.client.get("/api/positions", headers=self.headers)
        await self.assert_api_response(updated_response, 200)
        
        initial_data = initial_response.json()["positions"]
        updated_data = updated_response.json()["positions"]
        
        # 查找AAPL持仓
        initial_aapl = next((pos for pos in initial_data if pos.get("symbol") == "AAPL"), None)
        updated_aapl = next((pos for pos in updated_data if pos.get("symbol") == "AAPL"), None)
        
        if initial_aapl and updated_aapl:
            # 验证价格已更新
            assert updated_aapl["current_price"] > initial_aapl["current_price"]
            # 验证盈亏已重新计算
            assert updated_aapl["profit_loss"] > initial_aapl["profit_loss"]
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_positions_pagination(self):
        """测试持仓分页"""
        # 创建更多测试持仓
        additional_positions = [
            PositionFactory(symbol=f"TEST{i:03d}", quantity=100, avg_cost=100.0)
            for i in range(1, 21)  # 20个额外持仓
        ]
        self.insert_test_positions(additional_positions)
        
        # 测试分页
        params = {"page": 1, "size": 10}
        response = await self.client.get("/api/positions", 
                                       params=params, headers=self.headers)
        
        await self.assert_api_response(response, 200)
        
        response_data = response.json()
        assert len(response_data["positions"]) <= 10
        assert response_data["total_count"] >= 20  # 至少20个持仓
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_positions_sorting(self):
        """测试持仓排序"""
        params = {
            "sort_by": "profit_loss_pct",
            "sort_order": "desc"
        }
        
        response = await self.client.get("/api/positions",
                                       params=params, headers=self.headers)
        
        await self.assert_api_response(response, 200)
        
        response_data = response.json()
        positions = response_data["positions"]
        
        # 验证按盈亏百分比降序排列
        if len(positions) > 1:
            for i in range(len(positions) - 1):
                current_pct = positions[i].get("profit_loss_pct", 0)
                next_pct = positions[i + 1].get("profit_loss_pct", 0)
                assert current_pct >= next_pct
    
    @pytest.mark.api
    @pytest.mark.test_mode
    @pytest.mark.asyncio
    async def test_positions_test_mode_isolation(self):
        """测试持仓测试模式数据隔离"""
        # 获取测试模式持仓
        response = await self.client.get("/api/positions", headers=self.headers)
        await self.assert_api_response(response, 200)
        
        test_positions = response.json()["positions"]
        
        # 验证数据隔离
        self.assert_data_isolation(test_mode=0)
        
        # 验证只返回测试模式数据
        for position in test_positions:
            # 从数据库验证test_mode字段
            cursor = self.get_cursor()
            cursor.execute("SELECT test_mode FROM positions WHERE symbol = %s", 
                         (position["symbol"],))
            db_position = cursor.fetchone()
            cursor.close()
            
            if db_position:
                assert db_position["test_mode"] == 0  # 测试模式
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_positions_error_handling(self):
        """测试持仓错误处理"""
        # 测试长桥SDK连接失败
        self.mock_longbridge.is_connected = False
        
        response = await self.client.get("/api/positions", headers=self.headers)
        
        # 应该返回本地数据或适当的错误信息
        # 具体行为取决于实现策略
        assert response.status_code in [200, 500]
        
        if response.status_code == 500:
            await self.assert_api_error(response, 500, "长桥SDK")
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_positions_performance(self):
        """测试持仓接口性能"""
        import time
        
        # 创建大量持仓数据
        large_positions = [
            PositionFactory(symbol=f"PERF{i:04d}", quantity=100)
            for i in range(100)
        ]
        self.insert_test_positions(large_positions)
        
        start_time = time.time()
        response = await self.client.get("/api/positions", headers=self.headers)
        end_time = time.time()
        
        await self.assert_api_response(response, 200)
        
        # 验证响应时间在合理范围内（<2秒）
        response_time = end_time - start_time
        assert response_time < 2.0, f"持仓接口响应时间过长: {response_time:.2f}秒"
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_portfolio_risk_metrics(self):
        """测试投资组合风险指标"""
        response = await self.client.get("/api/portfolio", headers=self.headers)
        
        await self.assert_api_response(response, 200)
        
        response_data = response.json()
        
        # 验证风险指标存在且合理
        if "risk_metrics" in response_data:
            risk_metrics = response_data["risk_metrics"]
            
            # 验证集中度风险
            if "concentration_risk" in risk_metrics:
                assert 0 <= risk_metrics["concentration_risk"] <= 100
            
            # 验证波动率
            if "portfolio_volatility" in risk_metrics:
                assert risk_metrics["portfolio_volatility"] >= 0
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_positions_data_validation(self):
        """测试持仓数据验证"""
        response = await self.client.get("/api/positions", headers=self.headers)
        
        await self.assert_api_response(response, 200)
        
        response_data = response.json()
        
        for position in response_data["positions"]:
            # 验证必要字段存在
            required_fields = ["symbol", "quantity", "avg_cost", "current_price"]
            for field in required_fields:
                assert field in position, f"持仓记录缺少必要字段: {field}"
            
            # 验证数据类型和范围
            assert isinstance(position["symbol"], str)
            assert position["symbol"].strip() != ""
            assert isinstance(position["quantity"], (int, float))
            assert position["quantity"] >= 0
            assert isinstance(position["avg_cost"], (int, float))
            assert position["avg_cost"] > 0
            assert isinstance(position["current_price"], (int, float))
            assert position["current_price"] > 0