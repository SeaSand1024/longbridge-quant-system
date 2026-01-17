"""
Pydantic 数据模型定义
"""
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class Stock(BaseModel):
    id: Optional[int] = None
    symbol: str
    name: str
    is_active: bool = True


class Trade(BaseModel):
    id: Optional[int] = None
    symbol: str
    action: str
    price: float
    quantity: int
    amount: float
    acceleration: Optional[float] = None
    trade_time: Optional[datetime] = None
    status: str = 'PENDING'
    message: Optional[str] = None


class Position(BaseModel):
    id: Optional[int] = None
    symbol: str
    quantity: int
    buy_price: float
    cost: float
    buy_time: Optional[datetime] = None


class SystemConfig(BaseModel):
    config_key: str
    config_value: str
    description: Optional[str] = None


class MarketData(BaseModel):
    symbol: str
    price: float
    change: float
    change_pct: float
    volume: Optional[int] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    email: Optional[str] = None


class WeChatLoginRequest(BaseModel):
    code: str


class LongBridgeConfigUpdate(BaseModel):
    app_key: Optional[str] = None
    app_secret: Optional[str] = None
    access_token: Optional[str] = None
    http_url: Optional[str] = None
    quote_ws_url: Optional[str] = None
    trade_ws_url: Optional[str] = None
