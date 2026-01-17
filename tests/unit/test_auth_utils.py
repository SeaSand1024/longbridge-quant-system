"""
认证工具单元测试
"""
import pytest
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


class TestPasswordHashing:
    """测试密码哈希功能"""
    
    def test_pwd_context_exists(self):
        """测试密码上下文存在"""
        from app.config.settings import pwd_context
        
        assert pwd_context is not None
    
    def test_password_hash_and_verify(self):
        """测试密码哈希和验证"""
        from app.config.settings import pwd_context
        
        password = "test_password_123"
        hashed = pwd_context.hash(password)
        
        # 哈希后的密码应该不同于原密码
        assert hashed != password
        
        # 验证应该成功
        assert pwd_context.verify(password, hashed)
    
    def test_password_hash_different_each_time(self):
        """测试每次哈希结果不同（加盐）"""
        from app.config.settings import pwd_context
        
        password = "test_password_123"
        hash1 = pwd_context.hash(password)
        hash2 = pwd_context.hash(password)
        
        # 两次哈希结果应该不同
        assert hash1 != hash2
        
        # 但验证都应该成功
        assert pwd_context.verify(password, hash1)
        assert pwd_context.verify(password, hash2)
    
    def test_wrong_password_verification(self):
        """测试错误密码验证"""
        from app.config.settings import pwd_context
        
        password = "test_password_123"
        wrong_password = "wrong_password"
        hashed = pwd_context.hash(password)
        
        # 错误密码验证应该失败
        assert not pwd_context.verify(wrong_password, hashed)


class TestAuthUtils:
    """测试认证工具函数"""
    
    def test_auth_module_import(self):
        """测试认证模块可导入"""
        from app.auth import utils
        
        # 验证常用函数存在
        assert hasattr(utils, 'create_access_token') or hasattr(utils, 'get_current_user')
    
    def test_jwt_config_values(self):
        """测试JWT配置值合理"""
        from app.config.settings import ACCESS_TOKEN_EXPIRE_MINUTES, ALGORITHM
        
        # Token过期时间应该大于0
        assert ACCESS_TOKEN_EXPIRE_MINUTES > 0
        
        # 算法应该是有效的JWT算法
        assert ALGORITHM in ['HS256', 'HS384', 'HS512', 'RS256', 'RS384', 'RS512']
