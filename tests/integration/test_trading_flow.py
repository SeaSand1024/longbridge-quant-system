"""
完整交易流程集成测试
"""
import pytest
import asyncio
from tests.base import APITestCase
from tests.fixtures.test_data import StockFactory, TestDataGenerator


class TestTradingFlowIntegration(APITestCase):
    """完整交易流程集成测试类"""
    
    async def setup_test_data(self):
        """设置测试数据"""
        # 创建测试用户并登录
        self.headers = await self.login_test_user()
        
        # 创建测试股票
        self.test_stocks = [
            StockFactory(symbol="FLOW_AAPL", name="Apple Inc.", group_name="Tech"),
            StockFactory(symbol="FLOW_GOOGL", name="Alphabet Inc.", group_name="Tech"),
            StockFactory(symbol="FLOW_MSFT", name="Microsoft Corp.", group_name="Tech")
        ]
        self.insert_test_stocks(self.test_stocks)
        
        # 设置Mock长桥SDK
        self.mock_longbridge.account_balance = 100000.0
        self.mock_longbridge.positions = []
        
        # 设置Mock市场数据
        for stock in self.test_stocks:
            quote = {
                "symbol": stock["symbol"],
                "price": 150.0,
                "change": 2.5,
                "change_pct": 1.7,
                "volume": 1000000,
                "high": 152.0,
                "low": 148.0,
                "open": 149.0
            }
            self.mock_longbridge.market_data[stock["symbol"]] = quote
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_complete_trading_workflow(self):
        """测试完整交易工作流程"""
        # 1. 配置系统参数
        config_data = {
            "enabled": True,
            "max_daily_trades": 5,
            "buy_amount": 10000.0,
            "profit_target": 2.0,
            "min_acceleration": 0.001
        }
        
        config_response = await self.client.post("/api/smart-trade/config",
                                               json=config_data, headers=self.headers)
        await self.assert_api_response(config_response, 200)
        
        # 2. 获取市场数据
        market_response = await self.client.get("/api/market-data", headers=self.headers)
        await self.assert_api_response(market_response, 200)
        
        market_data = market_response.json()
        assert len(market_data["groups"]) > 0
        
        # 3. 运行智能预测
        prediction_response = await self.client.post("/api/smart-trade/run-prediction",
                                                   headers=self.headers)
        await self.assert_api_response(prediction_response, 200)
        
        prediction_data = prediction_response.json()
        assert prediction_data["predictions_count"] >= 0
        
        # 4. 获取预测结果
        predictions_response = await self.client.get("/api/smart-trade/predictions",
                                                   headers=self.headers)
        await self.assert_api_response(predictions_response, 200)
        
        predictions = predictions_response.json()["predictions"]
        
        # 5. 执行买入操作（选择最佳预测）
        if predictions:
            best_prediction = max(predictions, key=lambda x: x.get("predicted_return", 0))
            
            if best_prediction.get("predicted_return", 0) > 1.0:
                buy_data = {
                    "symbol": best_prediction["symbol"],
                    "quantity": 50,
                    "max_price": 200.0
                }
                
                buy_response = await self.client.post("/api/smart-trade/execute-buy",
                                                    json=buy_data, headers=self.headers)
                await self.assert_api_response(buy_response, 200)
                
                # 验证交易记录
                self.assert_trade_executed(best_prediction["symbol"], "BUY", 50)
        
        # 6. 检查持仓状态
        positions_response = await self.client.get("/api/positions", headers=self.headers)
        await self.assert_api_response(positions_response, 200)
        
        # 7. 检查账户总览
        portfolio_response = await self.client.get("/api/portfolio", headers=self.headers)
        await self.assert_api_response(portfolio_response, 200)
        
        portfolio_data = portfolio_response.json()
        assert "account_balance" in portfolio_data
        assert "total_market_value" in portfolio_data
        
        # 8. 获取交易记录
        trades_response = await self.client.get("/api/trades", headers=self.headers)
        await self.assert_api_response(trades_response, 200)
        
        trades_data = trades_response.json()
        assert isinstance(trades_data["trades"], list)
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_monitoring_workflow(self):
        """测试监控工作流程"""
        # 1. 启动监控
        start_response = await self.client.post("/api/monitoring/start", headers=self.headers)
        await self.assert_api_response(start_response, 200)
        
        # 2. 检查监控状态
        status_response = await self.client.get("/api/monitoring/status", headers=self.headers)
        await self.assert_api_response(status_response, 200)
        
        status_data = status_response.json()
        assert status_data.get("is_running") is True
        
        # 3. 等待一段时间让监控运行
        await asyncio.sleep(2)
        
        # 4. 停止监控
        stop_response = await self.client.post("/api/monitoring/stop", headers=self.headers)
        await self.assert_api_response(stop_response, 200)
        
        # 5. 再次检查状态
        final_status_response = await self.client.get("/api/monitoring/status", headers=self.headers)
        await self.assert_api_response(final_status_response, 200)
        
        final_status_data = final_status_response.json()
        assert final_status_data.get("is_running") is False
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_stock_management_workflow(self):
        """测试股票管理工作流程"""
        # 1. 获取初始股票列表
        initial_response = await self.client.get("/api/stocks", headers=self.headers)
        await self.assert_api_response(initial_response, 200)
        
        initial_count = initial_response.json()["total"]
        
        # 2. 添加新股票
        new_stock = {
            "symbol": "FLOW_TSLA",
            "name": "Tesla Inc.",
            "stock_type": "STOCK",
            "group_name": "Auto"
        }
        
        add_response = await self.client.post("/api/stocks", 
                                            json=new_stock, headers=self.headers)
        await self.assert_api_response(add_response, 200)
        
        stock_id = add_response.json()["stock_id"]
        
        # 3. 验证股票已添加
        updated_response = await self.client.get("/api/stocks", headers=self.headers)
        await self.assert_api_response(updated_response, 200)
        
        updated_count = updated_response.json()["total"]
        assert updated_count == initial_count + 1
        
        # 4. 切换股票状态
        toggle_response = await self.client.put(f"/api/stocks/{stock_id}/toggle",
                                              headers=self.headers)
        await self.assert_api_response(toggle_response, 200)
        
        # 5. 删除股票
        delete_response = await self.client.delete(f"/api/stocks/{stock_id}",
                                                 headers=self.headers)
        await self.assert_api_response(delete_response, 200)
        
        # 6. 验证股票已删除
        final_response = await self.client.get("/api/stocks", headers=self.headers)
        await self.assert_api_response(final_response, 200)
        
        final_count = final_response.json()["total"]
        assert final_count == initial_count
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_longbridge_integration_workflow(self):
        """测试长桥SDK集成工作流程"""
        # 1. 获取长桥配置
        config_response = await self.client.get("/api/longbridge/config", headers=self.headers)
        await self.assert_api_response(config_response, 200)
        
        # 2. 更新长桥配置
        config_data = {
            "app_key": "test_app_key",
            "app_secret": "test_app_secret",
            "access_token": "test_access_token"
        }
        
        update_response = await self.client.post("/api/longbridge/config",
                                               json=config_data, headers=self.headers)
        await self.assert_api_response(update_response, 200)
        
        # 3. 同步自选股
        sync_watchlist_response = await self.client.post("/api/longbridge/sync-watchlist",
                                                       headers=self.headers)
        await self.assert_api_response(sync_watchlist_response, 200)
        
        # 4. 同步持仓
        sync_positions_response = await self.client.post("/api/longbridge/sync-positions",
                                                       headers=self.headers)
        await self.assert_api_response(sync_positions_response, 200)
        
        # 5. 验证同步结果
        positions_response = await self.client.get("/api/positions", headers=self.headers)
        await self.assert_api_response(positions_response, 200)
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_error_recovery_workflow(self):
        """测试错误恢复工作流程"""
        # 1. 模拟网络错误
        self.mock_longbridge.is_connected = False
        
        # 2. 尝试执行需要长桥SDK的操作
        buy_data = {
            "symbol": "FLOW_AAPL",
            "quantity": 50,
            "max_price": 200.0
        }
        
        error_response = await self.client.post("/api/smart-trade/execute-buy",
                                              json=buy_data, headers=self.headers)
        
        # 应该返回错误
        await self.assert_api_error(error_response, 500)
        
        # 3. 恢复连接
        self.mock_longbridge.is_connected = True
        
        # 4. 重试操作
        retry_response = await self.client.post("/api/smart-trade/execute-buy",
                                              json=buy_data, headers=self.headers)
        
        # 现在应该成功
        await self.assert_api_response(retry_response, 200)
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_concurrent_operations_workflow(self):
        """测试并发操作工作流程"""
        # 创建多个并发任务
        tasks = []
        
        # 任务1：获取市场数据
        tasks.append(self.client.get("/api/market-data", headers=self.headers))
        
        # 任务2：获取持仓信息
        tasks.append(self.client.get("/api/positions", headers=self.headers))
        
        # 任务3：获取交易记录
        tasks.append(self.client.get("/api/trades", headers=self.headers))
        
        # 任务4：获取智能交易状态
        tasks.append(self.client.get("/api/smart-trade/status", headers=self.headers))
        
        # 并发执行所有任务
        responses = await asyncio.gather(*tasks)
        
        # 验证所有响应都成功
        for response in responses:
            assert response.status_code == 200
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_data_consistency_workflow(self):
        """测试数据一致性工作流程"""
        # 1. 执行买入操作
        buy_data = {
            "symbol": "FLOW_AAPL",
            "quantity": 100,
            "max_price": 200.0
        }
        
        buy_response = await self.client.post("/api/smart-trade/execute-buy",
                                            json=buy_data, headers=self.headers)
        await self.assert_api_response(buy_response, 200)
        
        # 2. 验证交易记录
        trades_response = await self.client.get("/api/trades", headers=self.headers)
        await self.assert_api_response(trades_response, 200)
        
        trades = trades_response.json()["trades"]
        aapl_trades = [t for t in trades if t.get("symbol") == "FLOW_AAPL"]
        assert len(aapl_trades) > 0
        
        # 3. 验证持仓更新
        positions_response = await self.client.get("/api/positions", headers=self.headers)
        await self.assert_api_response(positions_response, 200)
        
        positions = positions_response.json()["positions"]
        aapl_position = next((p for p in positions if p.get("symbol") == "FLOW_AAPL"), None)
        
        if aapl_position:
            assert aapl_position["quantity"] >= 100
        
        # 4. 验证账户余额更新
        portfolio_response = await self.client.get("/api/portfolio", headers=self.headers)
        await self.assert_api_response(portfolio_response, 200)
        
        portfolio = portfolio_response.json()
        # 余额应该减少（买入消耗资金）
        assert portfolio["account_balance"] < 100000.0
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_performance_workflow(self):
        """测试性能工作流程"""
        import time
        
        # 测试批量操作性能
        start_time = time.time()
        
        # 并发执行多个API调用
        tasks = []
        for _ in range(10):
            tasks.append(self.client.get("/api/market-data", headers=self.headers))
        
        responses = await asyncio.gather(*tasks)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # 验证所有请求都成功
        for response in responses:
            assert response.status_code == 200
        
        # 验证性能（10个请求应该在5秒内完成）
        assert duration < 5.0, f"批量请求耗时过长: {duration:.2f}秒"
        
        # 计算平均响应时间
        avg_response_time = duration / len(responses)
        assert avg_response_time < 0.5, f"平均响应时间过长: {avg_response_time:.2f}秒"