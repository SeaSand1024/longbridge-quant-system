"""
认证API测试
"""
import pytest
from tests.base import APITestCase
from tests.fixtures.test_data import UserFactory


class TestAuthAPI(APITestCase):
    """认证API测试类"""
    
    async def setup_test_data(self):
        """设置测试数据"""
        self.test_user_data = {
            "username": "test_user_auth",
            "email": "test_auth@example.com", 
            "password": "test_password_123"
        }
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_user_registration_success(self):
        """测试用户注册成功"""
        response = await self.client.post("/api/auth/register", json=self.test_user_data)
        
        await self.assert_api_response(response, 200, ["message", "user_id"])
        
        # 验证用户已创建
        cursor = self.get_cursor()
        cursor.execute("SELECT * FROM users WHERE username = %s", (self.test_user_data["username"],))
        user = cursor.fetchone()
        cursor.close()
        
        assert user is not None
        assert user["username"] == self.test_user_data["username"]
        assert user["email"] == self.test_user_data["email"]
        assert user["is_active"] is True
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_user_registration_duplicate_username(self):
        """测试重复用户名注册"""
        # 先注册一个用户
        await self.client.post("/api/auth/register", json=self.test_user_data)
        
        # 再次注册相同用户名
        response = await self.client.post("/api/auth/register", json=self.test_user_data)
        
        await self.assert_api_error(response, 400, "用户名已存在")
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_user_registration_invalid_email(self):
        """测试无效邮箱注册"""
        invalid_data = self.test_user_data.copy()
        invalid_data["email"] = "invalid_email"
        
        response = await self.client.post("/api/auth/register", json=invalid_data)
        
        await self.assert_api_error(response, 422)  # Validation error
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_user_registration_weak_password(self):
        """测试弱密码注册"""
        weak_data = self.test_user_data.copy()
        weak_data["password"] = "123"  # 太短的密码
        
        response = await self.client.post("/api/auth/register", json=weak_data)
        
        await self.assert_api_error(response, 422)  # Validation error
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_user_login_success(self):
        """测试用户登录成功"""
        # 先注册用户
        await self.client.post("/api/auth/register", json=self.test_user_data)
        
        # 登录
        login_data = {
            "username": self.test_user_data["username"],
            "password": self.test_user_data["password"]
        }
        
        response = await self.client.post("/api/auth/login", json=login_data)
        
        await self.assert_api_response(response, 200, ["message"])
        
        # 检查是否设置了认证cookie或返回了token
        response_data = response.json()
        assert "access_token" in response_data or "Set-Cookie" in response.headers
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_user_login_invalid_credentials(self):
        """测试无效凭据登录"""
        # 先注册用户
        await self.client.post("/api/auth/register", json=self.test_user_data)
        
        # 使用错误密码登录
        login_data = {
            "username": self.test_user_data["username"],
            "password": "wrong_password"
        }
        
        response = await self.client.post("/api/auth/login", json=login_data)
        
        await self.assert_api_error(response, 401, "用户名或密码错误")
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_user_login_nonexistent_user(self):
        """测试不存在用户登录"""
        login_data = {
            "username": "nonexistent_user",
            "password": "any_password"
        }
        
        response = await self.client.post("/api/auth/login", json=login_data)
        
        await self.assert_api_error(response, 401, "用户名或密码错误")
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_get_current_user_authenticated(self):
        """测试获取当前用户信息（已认证）"""
        # 登录获取认证头
        headers = await self.login_test_user(
            self.test_user_data["username"], 
            self.test_user_data["password"]
        )
        
        response = await self.client.get("/api/auth/me", headers=headers)
        
        await self.assert_api_response(response, 200, ["user_id", "username", "email"])
        
        response_data = response.json()
        assert response_data["username"] == self.test_user_data["username"]
        assert response_data["email"] == self.test_user_data["email"]
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_get_current_user_unauthenticated(self):
        """测试获取当前用户信息（未认证）"""
        response = await self.client.get("/api/auth/me")
        
        await self.assert_api_error(response, 401, "未认证")
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_user_logout_success(self):
        """测试用户登出成功"""
        # 登录获取认证头
        headers = await self.login_test_user(
            self.test_user_data["username"],
            self.test_user_data["password"]
        )
        
        response = await self.client.post("/api/auth/logout", headers=headers)
        
        await self.assert_api_response(response, 200, ["message"])
        
        # 验证登出后无法访问需要认证的接口
        response = await self.client.get("/api/auth/me", headers=headers)
        await self.assert_api_error(response, 401)
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_user_logout_unauthenticated(self):
        """测试未认证用户登出"""
        response = await self.client.post("/api/auth/logout")
        
        # 未认证用户登出应该也返回成功（幂等操作）
        await self.assert_api_response(response, 200)
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_multiple_user_registration(self):
        """测试多用户注册"""
        users_data = [
            UserFactory() for _ in range(5)
        ]
        
        registered_users = []
        
        for user_data in users_data:
            response = await self.client.post("/api/auth/register", json=user_data)
            await self.assert_api_response(response, 200)
            registered_users.append(user_data["username"])
        
        # 验证所有用户都已注册
        cursor = self.get_cursor()
        cursor.execute("SELECT username FROM users WHERE username IN %s", (tuple(registered_users),))
        db_users = [row["username"] for row in cursor.fetchall()]
        cursor.close()
        
        assert len(db_users) == len(registered_users)
        assert set(db_users) == set(registered_users)
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_concurrent_login_attempts(self):
        """测试并发登录尝试"""
        import asyncio
        
        # 先注册用户
        await self.client.post("/api/auth/register", json=self.test_user_data)
        
        login_data = {
            "username": self.test_user_data["username"],
            "password": self.test_user_data["password"]
        }
        
        # 并发登录
        tasks = [
            self.client.post("/api/auth/login", json=login_data)
            for _ in range(5)
        ]
        
        responses = await asyncio.gather(*tasks)
        
        # 所有登录都应该成功
        for response in responses:
            await self.assert_api_response(response, 200)
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_password_security(self):
        """测试密码安全性"""
        # 测试密码不会在响应中泄露
        response = await self.client.post("/api/auth/register", json=self.test_user_data)
        
        response_data = response.json()
        response_str = str(response_data)
        
        # 确保密码不在响应中
        assert self.test_user_data["password"] not in response_str
        
        # 登录后获取用户信息
        headers = await self.login_test_user(
            self.test_user_data["username"],
            self.test_user_data["password"]
        )
        
        response = await self.client.get("/api/auth/me", headers=headers)
        response_data = response.json()
        response_str = str(response_data)
        
        # 确保密码不在用户信息中
        assert self.test_user_data["password"] not in response_str
        assert "password" not in response_data
        assert "password_hash" not in response_data
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_authentication_persistence(self):
        """测试认证持久性"""
        # 登录获取认证头
        headers = await self.login_test_user(
            self.test_user_data["username"],
            self.test_user_data["password"]
        )
        
        # 多次访问需要认证的接口
        for _ in range(3):
            response = await self.client.get("/api/auth/me", headers=headers)
            await self.assert_api_response(response, 200)
            
            # 短暂等待
            await asyncio.sleep(0.1)
    
    @pytest.mark.api
    @pytest.mark.asyncio
    async def test_user_status_management(self):
        """测试用户状态管理"""
        # 注册用户
        response = await self.client.post("/api/auth/register", json=self.test_user_data)
        user_id = response.json()["user_id"]
        
        # 验证用户默认为激活状态
        cursor = self.get_cursor()
        cursor.execute("SELECT is_active FROM users WHERE id = %s", (user_id,))
        is_active = cursor.fetchone()["is_active"]
        assert is_active is True
        
        # 手动禁用用户
        cursor.execute("UPDATE users SET is_active = FALSE WHERE id = %s", (user_id,))
        self.db.commit()
        cursor.close()
        
        # 尝试登录被禁用的用户
        login_data = {
            "username": self.test_user_data["username"],
            "password": self.test_user_data["password"]
        }
        
        response = await self.client.post("/api/auth/login", json=login_data)
        await self.assert_api_error(response, 401, "账户已被禁用")