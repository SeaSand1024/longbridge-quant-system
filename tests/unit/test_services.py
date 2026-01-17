"""
服务模块单元测试
"""
import pytest
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


class TestServicesModule:
    """测试服务模块"""
    
    def test_services_init_import(self):
        """测试服务模块初始化导入"""
        from app import services
        
        # 验证服务模块存在
        assert services is not None
    
    def test_longbridge_sdk_module(self):
        """测试LongBridge SDK模块存在"""
        from app.services import longbridge_sdk
        
        assert longbridge_sdk is not None
    
    def test_smart_trader_module(self):
        """测试智能交易模块存在"""
        from app.services import smart_trader
        
        assert smart_trader is not None
    
    def test_acceleration_module(self):
        """测试加速度计算模块存在"""
        from app.services import acceleration
        
        assert acceleration is not None
    
    def test_trading_strategy_module(self):
        """测试交易策略模块存在"""
        from app.services import trading_strategy
        
        assert trading_strategy is not None
    
    def test_sse_module(self):
        """测试SSE推送模块存在"""
        from app.services import sse
        
        assert sse is not None
    
    def test_task_queue_module(self):
        """测试任务队列模块存在"""
        from app.services import task_queue
        
        assert task_queue is not None
    
    def test_test_mode_module(self):
        """测试测试模式模块存在"""
        from app.services import test_mode
        
        assert test_mode is not None


class TestRoutersModule:
    """测试路由模块"""
    
    def test_auth_router_exists(self):
        """测试认证路由存在"""
        from app.routers import auth
        
        assert hasattr(auth, 'router')
    
    def test_smart_trade_router_exists(self):
        """测试智能交易路由存在"""
        from app.routers import smart_trade
        
        assert hasattr(smart_trade, 'router')
    
    def test_positions_router_exists(self):
        """测试持仓路由存在"""
        from app.routers import positions
        
        assert hasattr(positions, 'router')
    
    def test_market_data_router_exists(self):
        """测试市场数据路由存在"""
        from app.routers import market_data
        
        assert hasattr(market_data, 'router')
    
    def test_stocks_router_exists(self):
        """测试股票管理路由存在"""
        from app.routers import stocks
        
        assert hasattr(stocks, 'router')
    
    def test_trades_router_exists(self):
        """测试交易记录路由存在"""
        from app.routers import trades
        
        assert hasattr(trades, 'router')
    
    def test_monitoring_router_exists(self):
        """测试监控路由存在"""
        from app.routers import monitoring
        
        assert hasattr(monitoring, 'router')
    
    def test_config_router_exists(self):
        """测试配置路由存在"""
        from app.routers import config
        
        assert hasattr(config, 'router')


class TestMainApp:
    """测试主应用"""
    
    def test_main_app_import(self):
        """测试主应用可导入"""
        # 这里只测试模块存在，不启动应用
        import main
        
        assert hasattr(main, 'app')
    
    def test_app_is_fastapi_instance(self):
        """测试应用是FastAPI实例"""
        from fastapi import FastAPI
        import main
        
        assert isinstance(main.app, FastAPI)
