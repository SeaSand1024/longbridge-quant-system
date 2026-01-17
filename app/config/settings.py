"""
全局配置设置
"""
import os
import secrets
from dotenv import load_dotenv
from passlib.context import CryptContext

# 加载环境变量
load_dotenv()

# 数据库配置
DB_CONFIG = {
    'host': os.getenv('MYSQL_HOST', '127.0.0.1'),
    'port': int(os.getenv('MYSQL_PORT', 3306)),
    'user': os.getenv('MYSQL_USER', 'root'),
    'password': os.getenv('MYSQL_PASSWORD', '123456'),
    'database': os.getenv('MYSQL_DB', 'quant_system'),
    'charset': 'utf8mb4'
}

# 长桥SDK配置（初始为空，从数据库加载）
LONGBRIDGE_CONFIG = {
    'app_key': '',
    'app_secret': '',
    'access_token': '',
    'http_url': 'https://openapi.longbridgeapp.com',
    'quote_ws_url': 'wss://openapi-quote.longbridgeapp.com',
    'trade_ws_url': 'wss://openapi-trade.longbridgeapp.com'
}

# 大模型API配置
LLM_CONFIG = {
    'enabled': False,
    'provider': 'openai',
    'api_key': '',
    'api_base': 'https://api.openai.com/v1',
    'model': 'gpt-4o-mini',
    'max_tokens': 1000,
    'temperature': 0.3,
    'weight': 0.3
}

# JWT配置
SECRET_KEY = os.getenv('SECRET_KEY', secrets.token_urlsafe(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24小时
REFRESH_TOKEN_EXPIRE_DAYS = 7

# 密码加密配置
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 汇率配置
EXCHANGE_RATES = {
    'USD': 1.0,
    'HKD': 0.128,
    'CNY': 0.138
}

# 微信登录配置
WECHAT_CONFIG = {
    'app_id': os.getenv('WECHAT_APP_ID', ''),
    'app_secret': os.getenv('WECHAT_APP_SECRET', ''),
    'enabled': os.getenv('WECHAT_LOGIN_ENABLED', 'false').lower() == 'true'
}

# 系统配置默认值
DEFAULT_SYSTEM_CONFIGS = {
    'profit_target': {
        'value': '1.0',
        'description': '单笔止盈目标（百分比）'
    },
    'buy_amount': {
        'value': '200000',
        'description': '单笔买入金额（USD）'
    },
    'max_concurrent_positions': {
        'value': '1',
        'description': '最大并发持仓数量'
    }
}

# 配置元数据
CONFIG_DEFINITIONS = {
    'profit_target': {
        'label': '止盈目标',
        'type': 'number',
        'unit': '%',
        'step': 0.1,
        'min': 0.1,
        'max': 100
    },
    'buy_amount': {
        'label': '单笔买入金额',
        'type': 'number',
        'unit': 'USD',
        'step': 1000,
        'min': 1000
    },
    'max_concurrent_positions': {
        'label': '最大持仓数',
        'type': 'number',
        'min': 1
    }
}


def ensure_default_system_configs(cursor, existing_keys=None):
    """确保默认系统配置存在于数据库中"""
    if existing_keys is None:
        cursor.execute("SELECT config_key FROM system_config")
        rows = cursor.fetchall()
        if rows:
            first_row = rows[0]
            if isinstance(first_row, dict):
                existing_keys = {row['config_key'] for row in rows}
            else:
                existing_keys = {row[0] for row in rows}
        else:
            existing_keys = set()
    else:
        existing_keys = set(existing_keys)

    inserted = False
    for key, meta in DEFAULT_SYSTEM_CONFIGS.items():
        if key not in existing_keys:
            cursor.execute(
                "INSERT INTO system_config (config_key, config_value, description) VALUES (%s, %s, %s)",
                (key, meta['value'], meta.get('description', ''))
            )
            existing_keys.add(key)
            inserted = True
    return inserted


def convert_currency(amount: float, from_currency: str = 'USD', to_currency: str = 'USD') -> float:
    """货币转换"""
    if from_currency == to_currency:
        return amount
    from_rate = EXCHANGE_RATES.get(from_currency, 1.0)
    to_rate = EXCHANGE_RATES.get(to_currency, 1.0)
    amount_in_usd = amount * from_rate
    return amount_in_usd / to_rate


def classify_symbol_type(symbol: str, security_type_hint=None) -> str:
    """
    判断股票类型（正股/期权）
    :param security_type_hint: 来自长桥静态信息的类型字段
    """
    if not symbol:
        return 'UNKNOWN'
    
    # 1) 使用长桥返回的 security_type
    if security_type_hint is not None:
        name = ''
        if hasattr(security_type_hint, 'name'):
            name = security_type_hint.name.lower()
        else:
            name = str(security_type_hint).lower()

        if 'option' in name:
            return 'OPTION'
        if 'equity' in name or 'stock' in name or 'common' in name:
            return 'STOCK'

    symbol_upper = symbol.upper()
    
    # 2) 代码模式推断：长桥期权代码通常包含较长的数字串
    if len(symbol) > 10 and any(ch.isdigit() for ch in symbol):
        return 'OPTION'
    if any(ch.isdigit() for ch in symbol) and len(symbol.replace('.', '')) > 8:
        return 'OPTION'
    
    # 3) ETF检测
    common_etfs = {'SPY', 'QQQ', 'IWM', 'DIA', 'VTI', 'VOO', 'ARKK', 'XLF', 'XLE', 'GLD', 'SLV'}
    if symbol_upper in common_etfs:
        return 'ETF'
    
    # 4) 后缀推断（.US/.HK 等）
    if '.' in symbol:
        return 'STOCK'
    
    return 'STOCK'
