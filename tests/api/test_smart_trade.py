"""
智能交易API测试
"""
import pytest
from datetime import datetime, date
from tests.base import APITestCase
from tests.fixtures.test_data import TestDataGenerator, StockFactory, PredictionFactory


class TestSmartTradeAPI(APITestCase):
    """智能交易API测试类"""
    
    async def setup_test_data(self):
        """设置测试数据"""
        # 创建测试用户并登录
        self.headers = await self.login_test_user()
        
        # 创建测试股票
        self.test_stocks = [
            StockFactory(symbol="AAPL", name="Apple Inc."),
            StockFactory(symbol="GOOGL", name="Alphabet Inc."),
            StockFactory(symbol="MSFT", name="Microsoft Corp.")
        ]
        self.insert_test_stocks(self.test_stocks)
        
        # 创建测试预测数据
        self.test_predictions = [
            PredictionFactory(symbol="AAPL", predicted_return=2.5, confidence_score=0.85),
            PredictionFactory(symbol="GOOGL", predicted_return=1.8, confidence_score=0.75),
            PredictionFactory(symbol="MSFT", predicted_return=-0.5, confidence_score=0.65)
        ]
        self.insert_test_predictions(self.test_predictions)
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_get_smart_trade_status_success(self):
        """测试获取智能交易状态成功"""
        response = await self.client.get("/api/smart-trade/status", headers=self.headers)
        
        await self.assert_api_response(response, 200, [
            "enabled", "today_predictions", "today_trades", "config"
        ])
        
        response_data = response.json()
        assert isinstance(response_data["enabled"], bool)
        assert isinstance(response_data["today_predictions"], list)
        assert isinstance(response_data["today_trades"], list)
        assert isinstance(response_data["config"], dict)
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_get_smart_trade_status_unauthenticated(self):
        """测试未认证获取智能交易状态"""
        response = await self.client.get("/api/smart-trade/status")
        
        await self.assert_api_error(response, 401)
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_update_smart_trade_config_success(self):
        """测试更新智能交易配置成功"""
        config_data = {
            "enabled": True,
            "max_daily_trades": 5,
            "buy_amount": 10000.0,
            "min_score": 70.0,
            "llm_enabled": True,
            "llm_weight": 0.3,
            "llm_model": "gpt-3.5-turbo"
        }
        
        response = await self.client.post("/api/smart-trade/config", 
                                        json=config_data, headers=self.headers)
        
        await self.assert_api_response(response, 200, ["message"])
        
        # 验证配置已更新
        self.assert_system_config_updated("smart_trade_enabled", True)
        self.assert_system_config_updated("max_daily_trades", 5)
        self.assert_system_config_updated("buy_amount", 10000.0)
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_update_smart_trade_config_invalid_data(self):
        """测试更新智能交易配置无效数据"""
        invalid_config = {
            "enabled": "not_boolean",  # 应该是布尔值
            "max_daily_trades": -1,    # 应该是正数
            "buy_amount": "invalid"    # 应该是数字
        }
        
        response = await self.client.post("/api/smart-trade/config",
                                        json=invalid_config, headers=self.headers)
        
        await self.assert_api_error(response, 422)  # Validation error
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_run_prediction_success(self):
        """测试运行股票预测成功"""
        response = await self.client.post("/api/smart-trade/run-prediction", 
                                        headers=self.headers)
        
        await self.assert_api_response(response, 200, ["message", "predictions_count"])
        
        response_data = response.json()
        assert response_data["predictions_count"] >= 0
        
        # 验证预测记录已创建
        cursor = self.get_cursor()
        cursor.execute("""
            SELECT COUNT(*) as count FROM stock_predictions 
            WHERE DATE(prediction_date) = CURDATE()
        """)
        count = cursor.fetchone()["count"]
        cursor.close()
        
        assert count > 0
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_run_prediction_no_stocks(self):
        """测试无股票时运行预测"""
        # 清空股票数据
        cursor = self.get_cursor()
        cursor.execute("DELETE FROM stocks")
        self.db.commit()
        cursor.close()
        
        response = await self.client.post("/api/smart-trade/run-prediction",
                                        headers=self.headers)
        
        await self.assert_api_response(response, 200)
        
        response_data = response.json()
        assert response_data["predictions_count"] == 0
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_execute_smart_buy_success(self):
        """测试执行智能买入成功"""
        # 设置Mock长桥SDK返回成功
        self.mock_longbridge.account_balance = 50000.0
        
        buy_data = {
            "symbol": "AAPL",
            "quantity": 100,
            "max_price": 200.0
        }
        
        response = await self.client.post("/api/smart-trade/execute-buy",
                                        json=buy_data, headers=self.headers)
        
        await self.assert_api_response(response, 200, ["message", "order_id"])
        
        # 验证交易记录已创建
        self.assert_trade_executed("AAPL", "BUY", 100)
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_execute_smart_buy_insufficient_balance(self):
        """测试余额不足时执行买入"""
        # 设置Mock长桥SDK余额不足
        self.mock_longbridge.account_balance = 100.0
        
        buy_data = {
            "symbol": "AAPL",
            "quantity": 1000,  # 大量购买
            "max_price": 200.0
        }
        
        response = await self.client.post("/api/smart-trade/execute-buy",
                                        json=buy_data, headers=self.headers)
        
        await self.assert_api_error(response, 400, "余额不足")
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_execute_smart_buy_invalid_symbol(self):
        """测试无效股票代码执行买入"""
        buy_data = {
            "symbol": "INVALID",
            "quantity": 100,
            "max_price": 200.0
        }
        
        response = await self.client.post("/api/smart-trade/execute-buy",
                                        json=buy_data, headers=self.headers)
        
        await self.assert_api_error(response, 400, "股票不存在")
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_get_predictions_history_success(self):
        """测试获取预测历史成功"""
        response = await self.client.get("/api/smart-trade/predictions", 
                                       headers=self.headers)
        
        await self.assert_api_response(response, 200, ["predictions", "total", "page", "size"])
        
        response_data = response.json()
        assert isinstance(response_data["predictions"], list)
        assert response_data["total"] >= 0
        assert len(response_data["predictions"]) <= response_data["size"]
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_get_predictions_history_with_filters(self):
        """测试带过滤条件获取预测历史"""
        params = {
            "symbol": "AAPL",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "page": 1,
            "size": 10
        }
        
        response = await self.client.get("/api/smart-trade/predictions",
                                       params=params, headers=self.headers)
        
        await self.assert_api_response(response, 200, ["predictions"])
        
        response_data = response.json()
        # 验证过滤条件生效
        for prediction in response_data["predictions"]:
            if "symbol" in prediction:
                assert prediction["symbol"] == "AAPL"
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_get_prediction_accuracy_success(self):
        """测试获取预测准确率成功"""
        response = await self.client.get("/api/smart-trade/prediction-accuracy",
                                       headers=self.headers)
        
        await self.assert_api_response(response, 200, [
            "total_predictions", "accurate_predictions", "accuracy_rate"
        ])
        
        response_data = response.json()
        assert response_data["total_predictions"] >= 0
        assert response_data["accurate_predictions"] >= 0
        assert 0 <= response_data["accuracy_rate"] <= 100
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_get_prediction_accuracy_by_symbol(self):
        """测试按股票获取预测准确率"""
        params = {"symbol": "AAPL"}
        
        response = await self.client.get("/api/smart-trade/prediction-accuracy",
                                       params=params, headers=self.headers)
        
        await self.assert_api_response(response, 200)
        
        response_data = response.json()
        assert response_data["total_predictions"] >= 0
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_smart_trade_workflow_integration(self):
        """测试智能交易完整工作流程"""
        # 1. 获取初始状态
        status_response = await self.client.get("/api/smart-trade/status", 
                                              headers=self.headers)
        await self.assert_api_response(status_response, 200)
        
        # 2. 更新配置启用智能交易
        config_data = {
            "enabled": True,
            "max_daily_trades": 3,
            "buy_amount": 5000.0,
            "min_score": 60.0
        }
        
        config_response = await self.client.post("/api/smart-trade/config",
                                               json=config_data, headers=self.headers)
        await self.assert_api_response(config_response, 200)
        
        # 3. 运行预测
        prediction_response = await self.client.post("/api/smart-trade/run-prediction",
                                                   headers=self.headers)
        await self.assert_api_response(prediction_response, 200)
        
        # 4. 检查预测结果
        predictions_response = await self.client.get("/api/smart-trade/predictions",
                                                   headers=self.headers)
        await self.assert_api_response(predictions_response, 200)
        
        # 5. 执行买入（如果有好的预测）
        predictions_data = predictions_response.json()
        if predictions_data["predictions"]:
            best_prediction = max(predictions_data["predictions"], 
                                key=lambda x: x.get("predicted_return", 0))
            
            if best_prediction.get("predicted_return", 0) > 1.0:  # 预期收益>1%
                buy_data = {
                    "symbol": best_prediction["symbol"],
                    "quantity": 50,
                    "max_price": 300.0
                }
                
                buy_response = await self.client.post("/api/smart-trade/execute-buy",
                                                    json=buy_data, headers=self.headers)
                await self.assert_api_response(buy_response, 200)
        
        # 6. 检查最终状态
        final_status_response = await self.client.get("/api/smart-trade/status",
                                                    headers=self.headers)
        await self.assert_api_response(final_status_response, 200)
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_smart_trade_error_handling(self):
        """测试智能交易错误处理"""
        # 测试长桥SDK连接失败的情况
        self.mock_longbridge.is_connected = False
        
        response = await self.client.post("/api/smart-trade/run-prediction",
                                        headers=self.headers)
        
        # 应该优雅处理SDK连接失败
        await self.assert_api_error(response, 500, "长桥SDK连接失败")
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_smart_trade_rate_limiting(self):
        """测试智能交易频率限制"""
        # 设置每日交易限制为1
        config_data = {
            "enabled": True,
            "max_daily_trades": 1,
            "buy_amount": 5000.0
        }
        
        await self.client.post("/api/smart-trade/config",
                             json=config_data, headers=self.headers)
        
        buy_data = {
            "symbol": "AAPL",
            "quantity": 50,
            "max_price": 200.0
        }
        
        # 第一次买入应该成功
        response1 = await self.client.post("/api/smart-trade/execute-buy",
                                         json=buy_data, headers=self.headers)
        await self.assert_api_response(response1, 200)
        
        # 第二次买入应该被限制
        response2 = await self.client.post("/api/smart-trade/execute-buy",
                                         json=buy_data, headers=self.headers)
        await self.assert_api_error(response2, 400, "超过每日交易限制")
    
    @pytest.mark.api
    @pytest.mark.test_mode
    @pytest.mark.asyncio
    async def test_smart_trade_test_mode_isolation(self):
        """测试智能交易测试模式数据隔离"""
        # 在测试模式下执行交易
        buy_data = {
            "symbol": "AAPL",
            "quantity": 100,
            "max_price": 200.0
        }
        
        response = await self.client.post("/api/smart-trade/execute-buy",
                                        json=buy_data, headers=self.headers)
        await self.assert_api_response(response, 200)
        
        # 验证数据隔离
        self.assert_data_isolation(test_mode=0)  # 测试模式
        
        # 验证真实模式下没有数据
        cursor = self.get_cursor()
        cursor.execute("SELECT COUNT(*) as count FROM trades WHERE test_mode = 1")
        real_trades = cursor.fetchone()["count"]
        cursor.close()
        
        assert real_trades == 0