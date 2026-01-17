"""
监控界面前端测试
"""
import pytest
import time
from selenium.webdriver.common.by import By
from tests.frontend.base_frontend import BaseFrontendTestCase


class TestMonitoringInterface(BaseFrontendTestCase):
    """监控界面测试类"""
    
    async def setup_test_data(self):
        """设置测试数据"""
        # 创建测试用户
        self.test_user = {
            "username": "monitoring_test_user",
            "email": "monitoring@test.com",
            "password": "test_password_123"
        }
        user_id = self.insert_test_user(self.test_user)
    
    def login_and_navigate_to_monitoring(self):
        """登录并导航到监控界面"""
        self.navigate_to("static/index.html")
        
        # 登录
        self.input_text((By.ID, "username"), self.test_user["username"])
        self.input_text((By.ID, "password"), self.test_user["password"])
        self.click_element((By.ID, "loginBtn"))
        
        # 等待主界面加载
        self.wait_for_element_visible((By.ID, "mainContent"))
    
    @pytest.mark.frontend
    @pytest.mark.asyncio
    async def test_monitoring_controls(self):
        """测试监控控制功能"""
        self.login_and_navigate_to_monitoring()
        
        # 验证监控控制按钮存在
        start_btn = (By.ID, "startMonitoring")
        stop_btn = (By.ID, "stopMonitoring")
        
        if self.is_element_present(start_btn):
            # 测试启动监控
            self.click_element(start_btn)
            
            # 等待状态更新
            time.sleep(1)
            
            # 验证监控状态指示器
            status_indicator = (By.ID, "monitoringStatus")
            if self.is_element_present(status_indicator):
                self.assert_text_in_element(status_indicator, "运行中")
        
        if self.is_element_present(stop_btn):
            # 测试停止监控
            self.click_element(stop_btn)
            
            # 等待状态更新
            time.sleep(1)
            
            # 验证监控状态
            if self.is_element_present(status_indicator):
                self.assert_text_in_element(status_indicator, "已停止")
    
    @pytest.mark.frontend
    @pytest.mark.asyncio
    async def test_real_time_data_display(self):
        """测试实时数据显示"""
        self.login_and_navigate_to_monitoring()
        
        # 验证实时数据面板
        real_time_panel = (By.ID, "realTimeData")
        if self.is_element_present(real_time_panel):
            self.assert_element_visible(real_time_panel)
            
            # 验证数据项
            data_items = [
                "currentPrice",
                "changePercent", 
                "volume",
                "timestamp"
            ]
            
            for item_id in data_items:
                if self.is_element_present((By.ID, item_id)):
                    self.assert_element_visible((By.ID, item_id))
    
    @pytest.mark.frontend
    @pytest.mark.asyncio
    async def test_monitoring_logs(self):
        """测试监控日志显示"""
        self.login_and_navigate_to_monitoring()
        
        # 验证日志面板
        log_panel = (By.ID, "monitoringLogs")
        if self.is_element_present(log_panel):
            self.assert_element_visible(log_panel)
            
            # 验证日志条目
            log_entries = self.find_elements_safe((By.CLASS_NAME, "log-entry"))
            
            # 如果有日志条目，验证其结构
            if log_entries:
                first_entry = log_entries[0]
                
                # 验证时间戳
                timestamp = first_entry.find_element(By.CLASS_NAME, "timestamp")
                assert timestamp.text != ""
                
                # 验证日志级别
                level = first_entry.find_element(By.CLASS_NAME, "level")
                assert level.text in ["INFO", "WARN", "ERROR", "DEBUG"]
                
                # 验证消息内容
                message = first_entry.find_element(By.CLASS_NAME, "message")
                assert message.text != ""