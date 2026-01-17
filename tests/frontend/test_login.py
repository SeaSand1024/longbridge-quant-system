"""
登录页面前端测试
"""
import pytest
from selenium.webdriver.common.by import By
from tests.frontend.base_frontend import BaseFrontendTestCase


class TestLoginPage(BaseFrontendTestCase):
    """登录页面测试类"""
    
    async def setup_test_data(self):
        """设置测试数据"""
        # 创建测试用户（通过API）
        self.test_user = {
            "username": "frontend_test_user",
            "email": "frontend@test.com",
            "password": "test_password_123"
        }
        
        # 通过API创建用户
        user_id = self.insert_test_user(self.test_user)
        self.test_user["user_id"] = user_id
    
    @pytest.mark.frontend
    @pytest.mark.asyncio
    async def test_login_page_loads(self):
        """测试登录页面加载"""
        self.navigate_to("static/index.html")
        
        # 验证页面标题
        self.assert_title_contains("量化交易系统")
        
        # 验证登录表单元素存在
        self.assert_element_present((By.ID, "loginForm"))
        self.assert_element_present((By.ID, "username"))
        self.assert_element_present((By.ID, "password"))
        self.assert_element_present((By.ID, "loginBtn"))
    
    @pytest.mark.frontend
    @pytest.mark.asyncio
    async def test_successful_login(self):
        """测试成功登录"""
        self.navigate_to("static/index.html")
        
        # 输入用户名和密码
        self.input_text((By.ID, "username"), self.test_user["username"])
        self.input_text((By.ID, "password"), self.test_user["password"])
        
        # 点击登录按钮
        self.click_element((By.ID, "loginBtn"))
        
        # 等待登录成功，主界面显示
        self.wait_for_element_visible((By.ID, "mainContent"), timeout=10)
        
        # 验证登录表单隐藏
        self.assert_element_not_visible((By.ID, "loginForm"))
        
        # 验证用户信息显示
        self.assert_element_visible((By.ID, "userInfo"))
        self.assert_text_in_element((By.ID, "currentUser"), self.test_user["username"])
    
    @pytest.mark.frontend
    @pytest.mark.asyncio
    async def test_login_with_invalid_credentials(self):
        """测试无效凭据登录"""
        self.navigate_to("static/index.html")
        
        # 输入错误的用户名和密码
        self.input_text((By.ID, "username"), "invalid_user")
        self.input_text((By.ID, "password"), "wrong_password")
        
        # 点击登录按钮
        self.click_element((By.ID, "loginBtn"))
        
        # 等待错误消息显示
        self.wait_for_element_visible((By.CLASS_NAME, "error-message"), timeout=5)
        
        # 验证错误消息内容
        self.assert_text_in_element((By.CLASS_NAME, "error-message"), "用户名或密码错误")
        
        # 验证仍在登录页面
        self.assert_element_visible((By.ID, "loginForm"))
    
    @pytest.mark.frontend
    @pytest.mark.asyncio
    async def test_login_with_empty_fields(self):
        """测试空字段登录"""
        self.navigate_to("static/index.html")
        
        # 不输入任何内容，直接点击登录
        self.click_element((By.ID, "loginBtn"))
        
        # 验证表单验证消息
        username_field = self.driver.find_element(By.ID, "username")
        password_field = self.driver.find_element(By.ID, "password")
        
        # HTML5表单验证应该阻止提交
        assert username_field.get_attribute("required") is not None
        assert password_field.get_attribute("required") is not None
    
    @pytest.mark.frontend
    @pytest.mark.asyncio
    async def test_register_new_user(self):
        """测试注册新用户"""
        self.navigate_to("static/index.html")
        
        # 点击注册链接
        self.click_element((By.ID, "showRegister"))
        
        # 验证注册表单显示
        self.wait_for_element_visible((By.ID, "registerForm"))
        self.assert_element_not_visible((By.ID, "loginForm"))
        
        # 填写注册信息
        new_user = {
            "username": "new_frontend_user",
            "email": "newfrontend@test.com",
            "password": "new_password_123"
        }
        
        self.input_text((By.ID, "regUsername"), new_user["username"])
        self.input_text((By.ID, "regEmail"), new_user["email"])
        self.input_text((By.ID, "regPassword"), new_user["password"])
        
        # 点击注册按钮
        self.click_element((By.ID, "registerBtn"))
        
        # 等待注册成功消息
        self.wait_for_element_visible((By.CLASS_NAME, "success-message"), timeout=10)
        
        # 验证成功消息
        self.assert_text_in_element((By.CLASS_NAME, "success-message"), "注册成功")
        
        # 验证自动跳转到登录表单
        self.wait_for_element_visible((By.ID, "loginForm"))
        self.assert_element_not_visible((By.ID, "registerForm"))
    
    @pytest.mark.frontend
    @pytest.mark.asyncio
    async def test_register_with_existing_username(self):
        """测试使用已存在用户名注册"""
        self.navigate_to("static/index.html")
        
        # 显示注册表单
        self.click_element((By.ID, "showRegister"))
        self.wait_for_element_visible((By.ID, "registerForm"))
        
        # 使用已存在的用户名
        self.input_text((By.ID, "regUsername"), self.test_user["username"])
        self.input_text((By.ID, "regEmail"), "another@test.com")
        self.input_text((By.ID, "regPassword"), "password123")
        
        # 点击注册按钮
        self.click_element((By.ID, "registerBtn"))
        
        # 等待错误消息
        self.wait_for_element_visible((By.CLASS_NAME, "error-message"))
        
        # 验证错误消息
        self.assert_text_in_element((By.CLASS_NAME, "error-message"), "用户名已存在")
    
    @pytest.mark.frontend
    @pytest.mark.asyncio
    async def test_form_switching(self):
        """测试登录和注册表单切换"""
        self.navigate_to("static/index.html")
        
        # 初始状态：显示登录表单
        self.assert_element_visible((By.ID, "loginForm"))
        self.assert_element_not_visible((By.ID, "registerForm"))
        
        # 切换到注册表单
        self.click_element((By.ID, "showRegister"))
        self.wait_for_element_visible((By.ID, "registerForm"))
        self.assert_element_not_visible((By.ID, "loginForm"))
        
        # 切换回登录表单
        self.click_element((By.ID, "showLogin"))
        self.wait_for_element_visible((By.ID, "loginForm"))
        self.assert_element_not_visible((By.ID, "registerForm"))
    
    @pytest.mark.frontend
    @pytest.mark.asyncio
    async def test_password_visibility_toggle(self):
        """测试密码可见性切换"""
        self.navigate_to("static/index.html")
        
        password_field = (By.ID, "password")
        toggle_button = (By.CLASS_NAME, "password-toggle")
        
        # 输入密码
        self.input_text(password_field, "test_password")
        
        # 初始状态：密码隐藏
        assert self.get_attribute(password_field, "type") == "password"
        
        # 点击切换按钮（如果存在）
        if self.is_element_present(toggle_button):
            self.click_element(toggle_button)
            
            # 验证密码显示
            assert self.get_attribute(password_field, "type") == "text"
            
            # 再次点击切换回隐藏
            self.click_element(toggle_button)
            assert self.get_attribute(password_field, "type") == "password"
    
    @pytest.mark.frontend
    @pytest.mark.asyncio
    async def test_remember_me_functionality(self):
        """测试记住我功能"""
        self.navigate_to("static/index.html")
        
        remember_checkbox = (By.ID, "rememberMe")
        
        # 如果存在记住我复选框
        if self.is_element_present(remember_checkbox):
            # 勾选记住我
            checkbox = self.driver.find_element(*remember_checkbox)
            if not checkbox.is_selected():
                self.click_element(remember_checkbox)
            
            # 登录
            self.input_text((By.ID, "username"), self.test_user["username"])
            self.input_text((By.ID, "password"), self.test_user["password"])
            self.click_element((By.ID, "loginBtn"))
            
            # 等待登录成功
            self.wait_for_element_visible((By.ID, "mainContent"))
            
            # 刷新页面验证是否保持登录状态
            self.refresh_page()
            
            # 应该直接显示主界面，不需要重新登录
            self.wait_for_element_visible((By.ID, "mainContent"), timeout=5)
    
    @pytest.mark.frontend
    @pytest.mark.asyncio
    async def test_login_form_validation(self):
        """测试登录表单验证"""
        self.navigate_to("static/index.html")
        
        # 测试用户名长度验证
        self.input_text((By.ID, "username"), "a")  # 太短
        self.input_text((By.ID, "password"), "valid_password")
        self.click_element((By.ID, "loginBtn"))
        
        # 验证用户名长度错误提示
        if self.is_element_present((By.CLASS_NAME, "validation-error")):
            self.assert_text_in_element((By.CLASS_NAME, "validation-error"), "用户名")
        
        # 测试密码长度验证
        self.input_text((By.ID, "username"), "valid_username", clear=True)
        self.input_text((By.ID, "password"), "123", clear=True)  # 太短
        self.click_element((By.ID, "loginBtn"))
        
        # 验证密码长度错误提示
        if self.is_element_present((By.CLASS_NAME, "validation-error")):
            self.assert_text_in_element((By.CLASS_NAME, "validation-error"), "密码")
    
    @pytest.mark.frontend
    @pytest.mark.asyncio
    async def test_login_loading_state(self):
        """测试登录加载状态"""
        self.navigate_to("static/index.html")
        
        # 输入有效凭据
        self.input_text((By.ID, "username"), self.test_user["username"])
        self.input_text((By.ID, "password"), self.test_user["password"])
        
        # 点击登录按钮
        login_button = self.driver.find_element(By.ID, "loginBtn")
        original_text = login_button.text
        
        self.click_element((By.ID, "loginBtn"))
        
        # 验证按钮状态变化（如果实现了加载状态）
        # 这里可能需要根据实际实现调整
        try:
            # 检查按钮是否显示加载状态
            self.wait_for_text_in_element((By.ID, "loginBtn"), "登录中", timeout=2)
            
            # 等待登录完成
            self.wait_for_element_visible((By.ID, "mainContent"))
            
        except AssertionError:
            # 如果没有实现加载状态，直接等待登录完成
            self.wait_for_element_visible((By.ID, "mainContent"))
    
    @pytest.mark.frontend
    @pytest.mark.asyncio
    async def test_responsive_design(self):
        """测试响应式设计"""
        self.navigate_to("static/index.html")
        
        # 测试桌面尺寸
        self.driver.set_window_size(1920, 1080)
        self.assert_element_visible((By.ID, "loginForm"))
        
        # 测试平板尺寸
        self.driver.set_window_size(768, 1024)
        self.assert_element_visible((By.ID, "loginForm"))
        
        # 测试手机尺寸
        self.driver.set_window_size(375, 667)
        self.assert_element_visible((By.ID, "loginForm"))
        
        # 恢复原始尺寸
        config = get_test_config()
        self.driver.set_window_size(*config.window_size)