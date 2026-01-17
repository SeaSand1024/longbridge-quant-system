"""
监控API测试
"""
import pytest
from tests.base import APITestCase


class TestMonitoringAPI(APITestCase):
    """监控API测试类"""
    
    async def setup_test_data(self):
        """设置测试数据"""
        # 创建测试用户并登录
        self.headers = await self.login_test_user()
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_start_monitoring_success(self):
        """测试启动监控成功"""
        response = await self.client.post("/api/monitoring/start", 
                                        headers=self.headers)
        
        await self.assert_api_response(response, 200, ["message"])
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_stop_monitoring_success(self):
        """测试停止监控成功"""
        response = await self.client.post("/api/monitoring/stop",
                                        headers=self.headers)
        
        await self.assert_api_response(response, 200, ["message"])
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_get_monitoring_status_success(self):
        """测试获取监控状态成功"""
        response = await self.client.get("/api/monitoring/status",
                                       headers=self.headers)
        
        await self.assert_api_response(response, 200, ["is_running", "test_mode"])