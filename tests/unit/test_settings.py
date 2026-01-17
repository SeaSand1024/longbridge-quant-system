"""
设置模块单元测试
"""
import pytest
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


class TestSettings:
    """测试设置配置"""
    
    def test_db_config_exists(self):
        """测试数据库配置存在"""
        from app.config import settings
        
        assert hasattr(settings, 'DB_CONFIG')
        assert 'host' in settings.DB_CONFIG
        assert 'port' in settings.DB_CONFIG
        assert 'user' in settings.DB_CONFIG
        assert 'password' in settings.DB_CONFIG
        assert 'database' in settings.DB_CONFIG
    
    def test_longbridge_config_exists(self):
        """测试长桥SDK配置存在"""
        from app.config import settings
        
        assert hasattr(settings, 'LONGBRIDGE_CONFIG')
        assert 'app_key' in settings.LONGBRIDGE_CONFIG
        assert 'app_secret' in settings.LONGBRIDGE_CONFIG
        assert 'access_token' in settings.LONGBRIDGE_CONFIG
    
    def test_llm_config_exists(self):
        """测试LLM配置存在"""
        from app.config import settings
        
        assert hasattr(settings, 'LLM_CONFIG')
        assert 'enabled' in settings.LLM_CONFIG
        assert 'provider' in settings.LLM_CONFIG
        assert 'model' in settings.LLM_CONFIG
    
    def test_jwt_config_exists(self):
        """测试JWT配置存在"""
        from app.config import settings
        
        assert hasattr(settings, 'SECRET_KEY')
        assert hasattr(settings, 'ALGORITHM')
        assert hasattr(settings, 'ACCESS_TOKEN_EXPIRE_MINUTES')
        assert settings.ALGORITHM == "HS256"
    
    def test_exchange_rates_defined(self):
        """测试汇率配置存在"""
        from app.config import settings
        
        assert hasattr(settings, 'EXCHANGE_RATES')
        assert 'USD' in settings.EXCHANGE_RATES
        assert 'HKD' in settings.EXCHANGE_RATES
        assert 'CNY' in settings.EXCHANGE_RATES


class TestCurrencyConversion:
    """测试货币转换功能"""
    
    def test_same_currency_conversion(self):
        """测试相同货币转换"""
        from app.config.settings import convert_currency
        
        result = convert_currency(100.0, 'USD', 'USD')
        assert result == 100.0
    
    def test_usd_to_hkd_conversion(self):
        """测试USD到HKD转换"""
        from app.config.settings import convert_currency, EXCHANGE_RATES
        
        amount = 100.0
        result = convert_currency(amount, 'USD', 'HKD')
        
        # USD to HKD = amount * USD_rate / HKD_rate
        expected = amount * EXCHANGE_RATES['USD'] / EXCHANGE_RATES['HKD']
        assert abs(result - expected) < 0.01


class TestSymbolClassification:
    """测试股票类型分类功能"""
    
    def test_classify_stock_symbol(self):
        """测试正股代码分类"""
        from app.config.settings import classify_symbol_type
        
        result = classify_symbol_type('AAPL')
        assert result == 'STOCK'
    
    def test_classify_stock_with_suffix(self):
        """测试带后缀的股票代码分类"""
        from app.config.settings import classify_symbol_type
        
        result = classify_symbol_type('AAPL.US')
        assert result == 'STOCK'
    
    def test_classify_etf_symbol(self):
        """测试ETF代码分类"""
        from app.config.settings import classify_symbol_type
        
        result = classify_symbol_type('SPY')
        assert result == 'ETF'
        
        result = classify_symbol_type('QQQ')
        assert result == 'ETF'
    
    def test_classify_option_symbol(self):
        """测试期权代码分类"""
        from app.config.settings import classify_symbol_type
        
        # 长代码通常是期权
        result = classify_symbol_type('AAPL230120C00150000')
        assert result == 'OPTION'
    
    def test_classify_unknown_symbol(self):
        """测试未知代码分类"""
        from app.config.settings import classify_symbol_type
        
        result = classify_symbol_type('')
        assert result == 'UNKNOWN'
