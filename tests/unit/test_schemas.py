"""
Schema模型单元测试
"""
import pytest
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


class TestSchemaValidation:
    """测试Schema验证"""
    
    def test_schemas_module_import(self):
        """测试Schema模块可导入"""
        from app.models import schemas
        
        # 验证常用Schema类存在
        assert hasattr(schemas, 'Stock')
        assert hasattr(schemas, 'Trade')
        assert hasattr(schemas, 'Position')
        assert hasattr(schemas, 'SystemConfig')
        assert hasattr(schemas, 'MarketData')
    
    def test_stock_schema(self):
        """测试股票Schema"""
        from app.models.schemas import Stock
        
        stock = Stock(symbol="AAPL", name="Apple Inc.")
        assert stock.symbol == "AAPL"
        assert stock.name == "Apple Inc."
        assert stock.is_active is True  # 默认值
    
    def test_trade_schema(self):
        """测试交易Schema"""
        from app.models.schemas import Trade
        
        trade = Trade(
            symbol="AAPL",
            action="BUY",
            price=150.0,
            quantity=100,
            amount=15000.0
        )
        assert trade.symbol == "AAPL"
        assert trade.action == "BUY"
        assert trade.status == "PENDING"  # 默认值
    
    def test_position_schema(self):
        """测试持仓Schema"""
        from app.models.schemas import Position
        
        position = Position(
            symbol="AAPL",
            quantity=100,
            buy_price=150.0,
            cost=15000.0
        )
        assert position.symbol == "AAPL"
        assert position.quantity == 100
    
    def test_pydantic_model_basic(self):
        """测试Pydantic模型基本功能"""
        from pydantic import BaseModel
        
        class TestModel(BaseModel):
            name: str
            value: int
        
        model = TestModel(name="test", value=123)
        assert model.name == "test"
        assert model.value == 123
    
    def test_pydantic_validation_error(self):
        """测试Pydantic验证错误"""
        from pydantic import BaseModel, ValidationError
        
        class StrictModel(BaseModel):
            email: str
            age: int
        
        with pytest.raises(ValidationError):
            StrictModel(email="test", age="not_a_number")
