"""
前端测试基类
"""
import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
import time
from typing import Optional, List, Dict, Any

from tests.base import BaseTestCase
from tests.test_config import get_test_config


class BaseFrontendTestCase(BaseTestCase):
    """前端测试基类"""
    
    @pytest.fixture(autouse=True)
    async def setup_selenium(self):
        """设置Selenium WebDriver"""
        config = get_test_config()
        
        # Chrome选项配置
        chrome_options = Options()
        
        if config.headless:
            chrome_options.add_argument('--headless')
        
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-web-security')
        chrome_options.add_argument('--allow-running-insecure-content')
        chrome_options.add_argument(f'--window-size={config.window_size[0]},{config.window_size[1]}')
        
        # 设置下载目录
        prefs = {
            "download.default_directory": "/tmp/selenium_downloads",
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        # 创建WebDriver
        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
        except Exception as e:
            # 如果ChromeDriverManager失败，尝试使用系统Chrome
            self.driver = webdriver.Chrome(options=chrome_options)
        
        # 设置隐式等待
        self.driver.implicitly_wait(10)
        
        # 设置页面加载超时
        self.driver.set_page_load_timeout(30)
        
        # WebDriverWait实例
        self.wait = WebDriverWait(self.driver, 10)
        
        # 基础URL
        self.base_url = config.base_url
        
        yield
        
        # 清理
        if hasattr(self, 'driver'):
            self.driver.quit()
    
    def navigate_to(self, path: str = ""):
        """导航到指定页面"""
        url = f"{self.base_url}/{path}".rstrip('/')
        self.driver.get(url)
        
        # 等待页面加载完成
        self.wait_for_page_load()
    
    def wait_for_page_load(self, timeout: int = 10):
        """等待页面加载完成"""
        try:
            WebDriverWait(self.driver, timeout).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )
        except TimeoutException:
            print("页面加载超时")
    
    def wait_for_element(self, locator: tuple, timeout: int = 10):
        """等待元素出现"""
        try:
            return WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located(locator)
            )
        except TimeoutException:
            raise AssertionError(f"元素 {locator} 在 {timeout} 秒内未出现")
    
    def wait_for_element_clickable(self, locator: tuple, timeout: int = 10):
        """等待元素可点击"""
        try:
            return WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable(locator)
            )
        except TimeoutException:
            raise AssertionError(f"元素 {locator} 在 {timeout} 秒内不可点击")
    
    def wait_for_element_visible(self, locator: tuple, timeout: int = 10):
        """等待元素可见"""
        try:
            return WebDriverWait(self.driver, timeout).until(
                EC.visibility_of_element_located(locator)
            )
        except TimeoutException:
            raise AssertionError(f"元素 {locator} 在 {timeout} 秒内不可见")
    
    def wait_for_text_in_element(self, locator: tuple, text: str, timeout: int = 10):
        """等待元素包含指定文本"""
        try:
            return WebDriverWait(self.driver, timeout).until(
                EC.text_to_be_present_in_element(locator, text)
            )
        except TimeoutException:
            raise AssertionError(f"元素 {locator} 在 {timeout} 秒内未包含文本 '{text}'")
    
    def find_element_safe(self, locator: tuple) -> Optional[webdriver.remote.webelement.WebElement]:
        """安全查找元素，不抛出异常"""
        try:
            return self.driver.find_element(*locator)
        except NoSuchElementException:
            return None
    
    def find_elements_safe(self, locator: tuple) -> List[webdriver.remote.webelement.WebElement]:
        """安全查找多个元素"""
        try:
            return self.driver.find_elements(*locator)
        except NoSuchElementException:
            return []
    
    def click_element(self, locator: tuple, timeout: int = 10):
        """点击元素"""
        element = self.wait_for_element_clickable(locator, timeout)
        
        # 滚动到元素可见
        self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
        time.sleep(0.5)
        
        # 点击元素
        try:
            element.click()
        except Exception:
            # 如果普通点击失败，使用JavaScript点击
            self.driver.execute_script("arguments[0].click();", element)
    
    def input_text(self, locator: tuple, text: str, clear: bool = True, timeout: int = 10):
        """输入文本"""
        element = self.wait_for_element_visible(locator, timeout)
        
        if clear:
            element.clear()
        
        element.send_keys(text)
    
    def get_text(self, locator: tuple, timeout: int = 10) -> str:
        """获取元素文本"""
        element = self.wait_for_element_visible(locator, timeout)
        return element.text
    
    def get_attribute(self, locator: tuple, attribute: str, timeout: int = 10) -> str:
        """获取元素属性"""
        element = self.wait_for_element(locator, timeout)
        return element.get_attribute(attribute)
    
    def is_element_present(self, locator: tuple) -> bool:
        """检查元素是否存在"""
        return self.find_element_safe(locator) is not None
    
    def is_element_visible(self, locator: tuple) -> bool:
        """检查元素是否可见"""
        element = self.find_element_safe(locator)
        return element is not None and element.is_displayed()
    
    def scroll_to_element(self, locator: tuple):
        """滚动到元素"""
        element = self.wait_for_element(locator)
        self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
        time.sleep(0.5)
    
    def scroll_to_bottom(self):
        """滚动到页面底部"""
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(0.5)
    
    def scroll_to_top(self):
        """滚动到页面顶部"""
        self.driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(0.5)
    
    def hover_element(self, locator: tuple):
        """悬停在元素上"""
        element = self.wait_for_element_visible(locator)
        ActionChains(self.driver).move_to_element(element).perform()
        time.sleep(0.5)
    
    def double_click_element(self, locator: tuple):
        """双击元素"""
        element = self.wait_for_element_clickable(locator)
        ActionChains(self.driver).double_click(element).perform()
    
    def right_click_element(self, locator: tuple):
        """右键点击元素"""
        element = self.wait_for_element_clickable(locator)
        ActionChains(self.driver).context_click(element).perform()
    
    def select_dropdown_by_text(self, locator: tuple, text: str):
        """通过文本选择下拉框选项"""
        from selenium.webdriver.support.ui import Select
        
        element = self.wait_for_element(locator)
        select = Select(element)
        select.select_by_visible_text(text)
    
    def select_dropdown_by_value(self, locator: tuple, value: str):
        """通过值选择下拉框选项"""
        from selenium.webdriver.support.ui import Select
        
        element = self.wait_for_element(locator)
        select = Select(element)
        select.select_by_value(value)
    
    def wait_for_alert_and_accept(self, timeout: int = 10):
        """等待并接受警告框"""
        try:
            alert = WebDriverWait(self.driver, timeout).until(EC.alert_is_present())
            alert_text = alert.text
            alert.accept()
            return alert_text
        except TimeoutException:
            raise AssertionError(f"警告框在 {timeout} 秒内未出现")
    
    def wait_for_alert_and_dismiss(self, timeout: int = 10):
        """等待并取消警告框"""
        try:
            alert = WebDriverWait(self.driver, timeout).until(EC.alert_is_present())
            alert_text = alert.text
            alert.dismiss()
            return alert_text
        except TimeoutException:
            raise AssertionError(f"警告框在 {timeout} 秒内未出现")
    
    def switch_to_window(self, window_index: int = -1):
        """切换到指定窗口"""
        windows = self.driver.window_handles
        if window_index == -1:
            window_index = len(windows) - 1
        
        if 0 <= window_index < len(windows):
            self.driver.switch_to.window(windows[window_index])
        else:
            raise AssertionError(f"窗口索引 {window_index} 超出范围")
    
    def close_current_window_and_switch_back(self):
        """关闭当前窗口并切换回主窗口"""
        self.driver.close()
        self.switch_to_window(0)
    
    def execute_javascript(self, script: str, *args):
        """执行JavaScript代码"""
        return self.driver.execute_script(script, *args)
    
    def take_screenshot(self, filename: str = None) -> str:
        """截图"""
        if filename is None:
            filename = f"screenshot_{int(time.time())}.png"
        
        screenshot_path = f"/tmp/{filename}"
        self.driver.save_screenshot(screenshot_path)
        return screenshot_path
    
    def get_page_source(self) -> str:
        """获取页面源码"""
        return self.driver.page_source
    
    def get_current_url(self) -> str:
        """获取当前URL"""
        return self.driver.current_url
    
    def get_page_title(self) -> str:
        """获取页面标题"""
        return self.driver.title
    
    def refresh_page(self):
        """刷新页面"""
        self.driver.refresh()
        self.wait_for_page_load()
    
    def go_back(self):
        """后退"""
        self.driver.back()
        self.wait_for_page_load()
    
    def go_forward(self):
        """前进"""
        self.driver.forward()
        self.wait_for_page_load()
    
    # 断言方法
    def assert_element_present(self, locator: tuple, message: str = ""):
        """断言元素存在"""
        assert self.is_element_present(locator), f"元素 {locator} 不存在. {message}"
    
    def assert_element_not_present(self, locator: tuple, message: str = ""):
        """断言元素不存在"""
        assert not self.is_element_present(locator), f"元素 {locator} 存在但不应该存在. {message}"
    
    def assert_element_visible(self, locator: tuple, message: str = ""):
        """断言元素可见"""
        assert self.is_element_visible(locator), f"元素 {locator} 不可见. {message}"
    
    def assert_element_not_visible(self, locator: tuple, message: str = ""):
        """断言元素不可见"""
        assert not self.is_element_visible(locator), f"元素 {locator} 可见但不应该可见. {message}"
    
    def assert_text_in_element(self, locator: tuple, expected_text: str, message: str = ""):
        """断言元素包含指定文本"""
        actual_text = self.get_text(locator)
        assert expected_text in actual_text, f"元素 {locator} 不包含文本 '{expected_text}', 实际文本: '{actual_text}'. {message}"
    
    def assert_element_text_equals(self, locator: tuple, expected_text: str, message: str = ""):
        """断言元素文本等于指定文本"""
        actual_text = self.get_text(locator)
        assert actual_text == expected_text, f"元素 {locator} 文本不匹配. 期望: '{expected_text}', 实际: '{actual_text}'. {message}"
    
    def assert_url_contains(self, expected_url_part: str, message: str = ""):
        """断言URL包含指定部分"""
        current_url = self.get_current_url()
        assert expected_url_part in current_url, f"URL不包含 '{expected_url_part}', 当前URL: '{current_url}'. {message}"
    
    def assert_title_contains(self, expected_title_part: str, message: str = ""):
        """断言页面标题包含指定文本"""
        current_title = self.get_page_title()
        assert expected_title_part in current_title, f"页面标题不包含 '{expected_title_part}', 当前标题: '{current_title}'. {message}"
    
    # 页面对象模式支持
    def wait_for_page_ready(self, ready_indicator_locator: tuple, timeout: int = 15):
        """等待页面准备就绪"""
        self.wait_for_element_visible(ready_indicator_locator, timeout)
        
        # 等待JavaScript加载完成
        WebDriverWait(self.driver, timeout).until(
            lambda driver: driver.execute_script("return jQuery.active == 0") if 
            driver.execute_script("return typeof jQuery != 'undefined'") else True
        )
    
    def login_user(self, username: str, password: str):
        """登录用户（前端操作）"""
        # 导航到登录页面
        self.navigate_to("login.html")
        
        # 输入用户名和密码
        self.input_text((By.ID, "username"), username)
        self.input_text((By.ID, "password"), password)
        
        # 点击登录按钮
        self.click_element((By.ID, "loginBtn"))
        
        # 等待登录成功（跳转到主页面）
        self.wait_for_url_change(timeout=10)
    
    def wait_for_url_change(self, timeout: int = 10):
        """等待URL变化"""
        original_url = self.get_current_url()
        
        WebDriverWait(self.driver, timeout).until(
            lambda driver: driver.current_url != original_url
        )