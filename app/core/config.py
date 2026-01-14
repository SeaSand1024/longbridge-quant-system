from __future__ import annotations

import os
from typing import Dict, Iterable, Optional, Set

from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    'host': os.getenv('MYSQL_HOST', '127.0.0.1'),
    'port': int(os.getenv('MYSQL_PORT', 3306)),
    'user': os.getenv('MYSQL_USER', 'root'),
    'password': os.getenv('MYSQL_PASSWORD', '123456'),
    'database': os.getenv('MYSQL_DB', 'quant_system'),
    'charset': 'utf8mb4'
}

LONGBRIDGE_CONFIG = {
    'app_key': '',
    'app_secret': '',
    'access_token': '',
    'http_url': 'https://openapi.longbridgeapp.com',
    'quote_ws_url': 'wss://openapi-quote.longbridgeapp.com',
    'trade_ws_url': 'wss://openapi-trade.longbridgeapp.com'
}

EXCHANGE_RATES: Dict[str, float] = {
    'USD': 1.0,
    'HKD': 0.128,
    'CNY': 0.138,
}

WECHAT_CONFIG = {
    'app_id': os.getenv('WECHAT_APP_ID', ''),
    'app_secret': os.getenv('WECHAT_APP_SECRET', ''),
    'enabled': os.getenv('WECHAT_LOGIN_ENABLED', 'false').lower() == 'true'
}

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


def ensure_default_system_configs(cursor, existing_keys: Optional[Iterable[str]] = None) -> bool:
    """确保 system_config 表中存在默认配置项。返回是否插入了新记录。"""
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
