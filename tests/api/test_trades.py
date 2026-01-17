"""
交易记录API测试
"""
import pytest
from tests.base import APITestCase
from tests.fixtures.test_data import TradeFactory


class TestTradesAPI(APITestCase):
    """交易记录API测试类"""
    
    async def setup_test_data(self):
        """设置测试数据"""
        # 创建测试用户并登录
        self.headers = await self.login_test_user()
        
        # 创建测试交易记录
        self.test_trades = [
            TradeFactory(symbol="AAPL", action="BUY", quantity=100, price=150.0),
            TradeFactory(symbol="GOOGL", action="BUY", quantity=50, price=2800.0),
            TradeFactory(symbol="AAPL", action="SELL", quantity=50, price=155.0)
        ]
        self.insert_test_trades(self.test_trades)
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_get_trades_success(self):
        """测试获取交易记录成功"""
        response = await self.client.get("/api/trades", headers=self.headers)
        
        await self.assert_api_response(response, 200, ["trades", "total"])
        
        response_data = response.json()
        assert isinstance(response_data["trades"], list)
        assert response_data["total"] >= len(self.test_trades)
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_get_orders_success(self):
        """测试获取历史订单成功"""
        response = await self.client.get("/api/orders", headers=self.headers)
        
        await self.assert_api_response(response, 200, ["orders"])
        
        response_data = response.json()
        assert isinstance(response_data["orders"], list)