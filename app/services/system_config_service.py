from __future__ import annotations

from typing import Dict

import pymysql

from app.core.config import CONFIG_DEFINITIONS, DEFAULT_SYSTEM_CONFIGS, ensure_default_system_configs
from app.db.session import get_db_connection


class SystemConfigService:
    """系统配置读写业务逻辑。"""

    @staticmethod
    def fetch_all() -> Dict[str, str]:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        try:
            cursor.execute("SELECT config_key, config_value FROM system_config")
            rows = cursor.fetchall()
            ensure_default_system_configs(cursor, [row['config_key'] for row in rows])
            conn.commit()
            cursor.execute("SELECT config_key, config_value FROM system_config")
            rows = cursor.fetchall()
            return {row['config_key']: row['config_value'] for row in rows}
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def get_full_payload() -> Dict[str, Dict[str, str]]:
        values = SystemConfigService.fetch_all()
        return {
            "values": values,
            "definitions": CONFIG_DEFINITIONS,
            "defaults": {key: meta['value'] for key, meta in DEFAULT_SYSTEM_CONFIGS.items()}
        }

    @staticmethod
    def upsert_config(config_key: str, config_value: str, description: str | None = None) -> None:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE system_config SET config_value = %s WHERE config_key = %s",
                (config_value, config_key)
            )
            if cursor.rowcount == 0:
                cursor.execute(
                    "INSERT INTO system_config (config_key, config_value, description) VALUES (%s, %s, %s)",
                    (config_key, config_value, description or '')
                )
            conn.commit()
        finally:
            cursor.close()
            conn.close()


system_config_service = SystemConfigService()
