"""
股票管理API测试
"""
import pytest
from tests.base import APITestCase
from tests.fixtures.test_data import StockFactory


class TestStocksAPI(APITestCase):
    """股票管理API测试类"""
    
    async def setup_test_data(self):
        """设置测试数据"""
        # 创建测试用户并登录
        self.headers = await self.login_test_user()
        
        # 创建测试股票
        self.test_stocks = [
            StockFactory(symbol="AAPL", name="Apple Inc.", group_name="Tech"),
            StockFactory(symbol="GOOGL", name="Alphabet Inc.", group_name="Tech"),
            StockFactory(symbol="MSFT", name="Microsoft Corp.", group_name="Tech")
        ]
        self.insert_test_stocks(self.test_stocks)
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_get_stocks_success(self):
        """测试获取股票列表成功"""
        response = await self.client.get("/api/stocks", headers=self.headers)
        
        await self.assert_api_response(response, 200, ["stocks", "total"])
        
        response_data = response.json()
        assert isinstance(response_data["stocks"], list)
        assert response_data["total"] >= len(self.test_stocks)
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_add_stock_success(self):
        """测试添加股票成功"""
        new_stock = {
            "symbol": "TSLA",
            "name": "Tesla Inc.",
            "stock_type": "STOCK",
            "group_name": "Auto"
        }
        
        response = await self.client.post("/api/stocks", 
                                        json=new_stock, headers=self.headers)
        
        await self.assert_api_response(response, 200, ["message", "stock_id"])
        
        # 验证股票已添加
        cursor = self.get_cursor()
        cursor.execute("SELECT * FROM stocks WHERE symbol = %s", (new_stock["symbol"],))
        stock = cursor.fetchone()
        cursor.close()
        
        assert stock is not None
        assert stock["name"] == new_stock["name"]
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_add_duplicate_stock(self):
        """测试添加重复股票"""
        duplicate_stock = {
            "symbol": "AAPL",  # 已存在
            "name": "Apple Inc.",
            "stock_type": "STOCK",
            "group_name": "Tech"
        }
        
        response = await self.client.post("/api/stocks",
                                        json=duplicate_stock, headers=self.headers)
        
        await self.assert_api_error(response, 400, "股票已存在")
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_delete_stock_success(self):
        """测试删除股票成功"""
        # 获取要删除的股票ID
        cursor = self.get_cursor()
        cursor.execute("SELECT id FROM stocks WHERE symbol = 'MSFT'")
        stock = cursor.fetchone()
        cursor.close()
        
        assert stock is not None
        stock_id = stock["id"]
        
        response = await self.client.delete(f"/api/stocks/{stock_id}", 
                                          headers=self.headers)
        
        await self.assert_api_response(response, 200, ["message"])
        
        # 验证股票已删除
        cursor = self.get_cursor()
        cursor.execute("SELECT * FROM stocks WHERE id = %s", (stock_id,))
        deleted_stock = cursor.fetchone()
        cursor.close()
        
        assert deleted_stock is None
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_toggle_stock_status_success(self):
        """测试切换股票状态成功"""
        # 获取股票ID
        cursor = self.get_cursor()
        cursor.execute("SELECT id, is_active FROM stocks WHERE symbol = 'AAPL'")
        stock = cursor.fetchone()
        cursor.close()
        
        assert stock is not None
        stock_id = stock["id"]
        original_status = stock["is_active"]
        
        response = await self.client.put(f"/api/stocks/{stock_id}/toggle",
                                       headers=self.headers)
        
        await self.assert_api_response(response, 200, ["message", "is_active"])
        
        # 验证状态已切换
        cursor = self.get_cursor()
        cursor.execute("SELECT is_active FROM stocks WHERE id = %s", (stock_id,))
        updated_stock = cursor.fetchone()
        cursor.close()
        
        assert updated_stock["is_active"] != original_status