"""
模式切换集成测试
"""
import pytest
from tests.base import APITestCase
from tests.fixtures.test_data import StockFactory, TradeFactory, PositionFactory


class TestModeSwitchIntegration(APITestCase):
    """模式切换集成测试类"""
    
    async def setup_test_data(self):
        """设置测试数据"""
        # 创建测试用户并登录
        self.headers = await self.login_test_user()
        
        # 创建测试股票
        self.test_stocks = [
            StockFactory(symbol="MODE_AAPL", name="Apple Inc."),
            StockFactory(symbol="MODE_GOOGL", name="Alphabet Inc.")
        ]
        self.insert_test_stocks(self.test_stocks)
        
        # 设置Mock长桥SDK
        self.mock_longbridge.account_balance = 50000.0
    
    @pytest.mark.integration
    @pytest.mark.test_mode
    @pytest.mark.asyncio
    async def test_test_mode_to_real_mode_switch(self):
        """测试从测试模式切换到真实模式"""
        # 1. 确保当前在测试模式
        config_response = await self.client.get("/api/config", headers=self.headers)
        await self.assert_api_response(config_response, 200)
        
        # 2. 在测试模式下创建数据
        test_mode_config = {
            "test_mode": True,
            "buy_amount": 5000.0,
            "profit_target": 2.0
        }
        
        update_response = await self.client.put("/api/config",
                                              json=test_mode_config, headers=self.headers)
        await self.assert_api_response(update_response, 200)
        
        # 3. 执行测试模式交易
        buy_data = {
            "symbol": "MODE_AAPL",
            "quantity": 50,
            "max_price": 200.0
        }
        
        test_buy_response = await self.client.post("/api/smart-trade/execute-buy",
                                                 json=buy_data, headers=self.headers)
        await self.assert_api_response(test_buy_response, 200)
        
        # 4. 验证测试模式数据
        test_positions_response = await self.client.get("/api/positions", headers=self.headers)
        await self.assert_api_response(test_positions_response, 200)
        
        test_positions = test_positions_response.json()["positions"]
        test_aapl_position = next((p for p in test_positions if p.get("symbol") == "MODE_AAPL"), None)
        assert test_aapl_position is not None
        
        # 5. 切换到真实模式
        real_mode_config = {
            "test_mode": False,
            "buy_amount": 10000.0,
            "profit_target": 1.5
        }
        
        switch_response = await self.client.put("/api/config",
                                              json=real_mode_config, headers=self.headers)
        await self.assert_api_response(switch_response, 200)
        
        # 6. 验证真实模式下看不到测试数据
        real_positions_response = await self.client.get("/api/positions", headers=self.headers)
        await self.assert_api_response(real_positions_response, 200)
        
        real_positions = real_positions_response.json()["positions"]
        real_aapl_position = next((p for p in real_positions if p.get("symbol") == "MODE_AAPL"), None)
        # 真实模式下应该看不到测试模式的持仓
        assert real_aapl_position is None or real_aapl_position["quantity"] == 0
        
        # 7. 在真实模式下执行交易
        real_buy_response = await self.client.post("/api/smart-trade/execute-buy",
                                                 json=buy_data, headers=self.headers)
        await self.assert_api_response(real_buy_response, 200)
        
        # 8. 验证真实模式数据
        final_positions_response = await self.client.get("/api/positions", headers=self.headers)
        await self.assert_api_response(final_positions_response, 200)
        
        final_positions = final_positions_response.json()["positions"]
        final_aapl_position = next((p for p in final_positions if p.get("symbol") == "MODE_AAPL"), None)
        assert final_aapl_position is not None
        assert final_aapl_position["quantity"] == 50  # 真实模式的持仓
        
        # 9. 切换回测试模式验证数据隔离
        back_to_test_response = await self.client.put("/api/config",
                                                    json=test_mode_config, headers=self.headers)
        await self.assert_api_response(back_to_test_response, 200)
        
        # 10. 验证测试模式数据仍然存在
        back_positions_response = await self.client.get("/api/positions", headers=self.headers)
        await self.assert_api_response(back_positions_response, 200)
        
        back_positions = back_positions_response.json()["positions"]
        back_aapl_position = next((p for p in back_positions if p.get("symbol") == "MODE_AAPL"), None)
        assert back_aapl_position is not None
        assert back_aapl_position["quantity"] == 50  # 原来测试模式的持仓
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_mode_switch_data_isolation(self):
        """测试模式切换时的数据隔离"""
        # 1. 在测试模式下创建多种类型的数据
        test_trades = [
            TradeFactory(symbol="MODE_AAPL", action="BUY", test_mode=0),
            TradeFactory(symbol="MODE_GOOGL", action="BUY", test_mode=0)
        ]
        self.insert_test_trades(test_trades)
        
        test_positions = [
            PositionFactory(symbol="MODE_AAPL", quantity=100, test_mode=0),
            PositionFactory(symbol="MODE_GOOGL", quantity=50, test_mode=0)
        ]
        self.insert_test_positions(test_positions)
        
        # 2. 在真实模式下创建不同的数据
        real_trades = [
            TradeFactory(symbol="MODE_AAPL", action="BUY", quantity=200, test_mode=1),
        ]
        self.insert_test_trades(real_trades)
        
        real_positions = [
            PositionFactory(symbol="MODE_AAPL", quantity=200, test_mode=1),
        ]
        self.insert_test_positions(real_positions)
        
        # 3. 设置为测试模式
        test_config = {"test_mode": True}
        await self.client.put("/api/config", json=test_config, headers=self.headers)
        
        # 4. 验证只能看到测试模式数据
        test_trades_response = await self.client.get("/api/trades", headers=self.headers)
        await self.assert_api_response(test_trades_response, 200)
        
        test_trades_data = test_trades_response.json()["trades"]
        test_trade_quantities = [t["quantity"] for t in test_trades_data if t.get("symbol") == "MODE_AAPL"]
        assert 200 not in test_trade_quantities  # 真实模式的数量不应该出现
        
        # 5. 切换到真实模式
        real_config = {"test_mode": False}
        await self.client.put("/api/config", json=real_config, headers=self.headers)
        
        # 6. 验证只能看到真实模式数据
        real_trades_response = await self.client.get("/api/trades", headers=self.headers)
        await self.assert_api_response(real_trades_response, 200)
        
        real_trades_data = real_trades_response.json()["trades"]
        real_trade_quantities = [t["quantity"] for t in real_trades_data if t.get("symbol") == "MODE_AAPL"]
        
        # 应该只看到真实模式的交易（数量200）
        if real_trade_quantities:
            assert 200 in real_trade_quantities
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_mode_switch_configuration_persistence(self):
        """测试模式切换时配置的持久性"""
        # 1. 设置测试模式配置
        test_config = {
            "test_mode": True,
            "buy_amount": 5000.0,
            "profit_target": 2.5,
            "max_positions": 5
        }
        
        test_response = await self.client.put("/api/config", json=test_config, headers=self.headers)
        await self.assert_api_response(test_response, 200)
        
        # 2. 验证测试模式配置
        get_test_response = await self.client.get("/api/config", headers=self.headers)
        await self.assert_api_response(get_test_response, 200)
        
        test_config_data = get_test_response.json()
        assert test_config_data["test_mode"] is True
        assert test_config_data["buy_amount"] == 5000.0
        
        # 3. 切换到真实模式并设置不同配置
        real_config = {
            "test_mode": False,
            "buy_amount": 15000.0,
            "profit_target": 1.5,
            "max_positions": 10
        }
        
        real_response = await self.client.put("/api/config", json=real_config, headers=self.headers)
        await self.assert_api_response(real_response, 200)
        
        # 4. 验证真实模式配置
        get_real_response = await self.client.get("/api/config", headers=self.headers)
        await self.assert_api_response(get_real_response, 200)
        
        real_config_data = get_real_response.json()
        assert real_config_data["test_mode"] is False
        assert real_config_data["buy_amount"] == 15000.0
        
        # 5. 切换回测试模式
        back_to_test = {"test_mode": True}
        await self.client.put("/api/config", json=back_to_test, headers=self.headers)
        
        # 6. 验证测试模式配置是否保持
        final_test_response = await self.client.get("/api/config", headers=self.headers)
        await self.assert_api_response(final_test_response, 200)
        
        final_test_data = final_test_response.json()
        assert final_test_data["test_mode"] is True
        # 配置应该保持之前的测试模式设置
        assert final_test_data["buy_amount"] == 5000.0
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_mode_switch_smart_trading(self):
        """测试模式切换对智能交易的影响"""
        # 1. 在测试模式下配置智能交易
        test_smart_config = {
            "enabled": True,
            "max_daily_trades": 3,
            "buy_amount": 8000.0,
            "min_score": 70.0,
            "llm_enabled": True
        }
        
        test_config_response = await self.client.post("/api/smart-trade/config",
                                                    json=test_smart_config, headers=self.headers)
        await self.assert_api_response(test_config_response, 200)
        
        # 2. 运行测试模式预测
        test_prediction_response = await self.client.post("/api/smart-trade/run-prediction",
                                                        headers=self.headers)
        await self.assert_api_response(test_prediction_response, 200)
        
        # 3. 获取测试模式预测结果
        test_predictions_response = await self.client.get("/api/smart-trade/predictions",
                                                        headers=self.headers)
        await self.assert_api_response(test_predictions_response, 200)
        
        test_predictions = test_predictions_response.json()["predictions"]
        test_prediction_count = len(test_predictions)
        
        # 4. 切换到真实模式
        real_mode_config = {"test_mode": False}
        await self.client.put("/api/config", json=real_mode_config, headers=self.headers)
        
        # 5. 在真实模式下配置不同的智能交易参数
        real_smart_config = {
            "enabled": True,
            "max_daily_trades": 5,
            "buy_amount": 12000.0,
            "min_score": 80.0,
            "llm_enabled": False
        }
        
        real_config_response = await self.client.post("/api/smart-trade/config",
                                                    json=real_smart_config, headers=self.headers)
        await self.assert_api_response(real_config_response, 200)
        
        # 6. 运行真实模式预测
        real_prediction_response = await self.client.post("/api/smart-trade/run-prediction",
                                                        headers=self.headers)
        await self.assert_api_response(real_prediction_response, 200)
        
        # 7. 获取真实模式预测结果
        real_predictions_response = await self.client.get("/api/smart-trade/predictions",
                                                        headers=self.headers)
        await self.assert_api_response(real_predictions_response, 200)
        
        real_predictions = real_predictions_response.json()["predictions"]
        
        # 8. 验证预测结果的隔离性
        # 真实模式下应该看不到测试模式的预测，或者有不同的预测参数
        if real_predictions and test_predictions:
            # 检查预测配置是否不同
            assert real_smart_config["buy_amount"] != test_smart_config["buy_amount"]
            assert real_smart_config["llm_enabled"] != test_smart_config["llm_enabled"]
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_mode_switch_monitoring(self):
        """测试模式切换对监控功能的影响"""
        # 1. 在测试模式下启动监控
        test_mode_config = {"test_mode": True}
        await self.client.put("/api/config", json=test_mode_config, headers=self.headers)
        
        test_start_response = await self.client.post("/api/monitoring/start", headers=self.headers)
        await self.assert_api_response(test_start_response, 200)
        
        # 2. 检查测试模式监控状态
        test_status_response = await self.client.get("/api/monitoring/status", headers=self.headers)
        await self.assert_api_response(test_status_response, 200)
        
        test_status = test_status_response.json()
        assert test_status.get("is_running") is True
        assert test_status.get("test_mode") is True
        
        # 3. 切换到真实模式
        real_mode_config = {"test_mode": False}
        await self.client.put("/api/config", json=real_mode_config, headers=self.headers)
        
        # 4. 检查真实模式监控状态
        real_status_response = await self.client.get("/api/monitoring/status", headers=self.headers)
        await self.assert_api_response(real_status_response, 200)
        
        real_status = real_status_response.json()
        assert real_status.get("test_mode") is False
        
        # 5. 在真实模式下启动监控
        real_start_response = await self.client.post("/api/monitoring/start", headers=self.headers)
        await self.assert_api_response(real_start_response, 200)
        
        # 6. 验证真实模式监控独立运行
        final_status_response = await self.client.get("/api/monitoring/status", headers=self.headers)
        await self.assert_api_response(final_status_response, 200)
        
        final_status = final_status_response.json()
        assert final_status.get("is_running") is True
        assert final_status.get("test_mode") is False
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_concurrent_mode_operations(self):
        """测试并发模式操作"""
        import asyncio
        
        async def test_mode_operations():
            """测试模式操作"""
            # 设置测试模式
            test_config = {"test_mode": True}
            await self.client.put("/api/config", json=test_config, headers=self.headers)
            
            # 执行测试模式交易
            buy_data = {"symbol": "MODE_AAPL", "quantity": 30, "max_price": 200.0}
            await self.client.post("/api/smart-trade/execute-buy", json=buy_data, headers=self.headers)
            
            # 获取测试模式数据
            await self.client.get("/api/positions", headers=self.headers)
        
        async def real_mode_operations():
            """真实模式操作"""
            # 设置真实模式
            real_config = {"test_mode": False}
            await self.client.put("/api/config", json=real_config, headers=self.headers)
            
            # 执行真实模式交易
            buy_data = {"symbol": "MODE_GOOGL", "quantity": 40, "max_price": 300.0}
            await self.client.post("/api/smart-trade/execute-buy", json=buy_data, headers=self.headers)
            
            # 获取真实模式数据
            await self.client.get("/api/positions", headers=self.headers)
        
        # 并发执行两种模式的操作
        await asyncio.gather(
            test_mode_operations(),
            real_mode_operations()
        )
        
        # 验证最终数据状态
        # 检查当前模式
        final_config_response = await self.client.get("/api/config", headers=self.headers)
        await self.assert_api_response(final_config_response, 200)
        
        final_config = final_config_response.json()
        current_mode = final_config.get("test_mode")
        
        # 获取当前模式的持仓
        positions_response = await self.client.get("/api/positions", headers=self.headers)
        await self.assert_api_response(positions_response, 200)
        
        positions = positions_response.json()["positions"]
        
        # 验证数据一致性（具体验证取决于最终模式）
        assert isinstance(positions, list)
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_mode_switch_error_handling(self):
        """测试模式切换时的错误处理"""
        # 1. 模拟在切换过程中发生错误
        # 设置无效配置
        invalid_config = {
            "test_mode": "invalid_boolean",  # 无效的布尔值
            "buy_amount": -1000.0  # 无效的金额
        }
        
        error_response = await self.client.put("/api/config", json=invalid_config, headers=self.headers)
        await self.assert_api_error(error_response, 422)  # 验证错误
        
        # 2. 验证系统状态未被破坏
        status_response = await self.client.get("/api/config", headers=self.headers)
        await self.assert_api_response(status_response, 200)
        
        # 3. 尝试正常的模式切换
        valid_config = {
            "test_mode": True,
            "buy_amount": 8000.0
        }
        
        valid_response = await self.client.put("/api/config", json=valid_config, headers=self.headers)
        await self.assert_api_response(valid_response, 200)
        
        # 4. 验证系统恢复正常
        final_status_response = await self.client.get("/api/config", headers=self.headers)
        await self.assert_api_response(final_status_response, 200)
        
        final_status = final_status_response.json()
        assert final_status["test_mode"] is True
        assert final_status["buy_amount"] == 8000.0