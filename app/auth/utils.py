"""
认证相关工具函数
"""
import pymysql
import bcrypt
from datetime import datetime, timedelta
from typing import Optional
from fastapi import HTTPException, status, Cookie, Request, Depends
from jose import JWTError, jwt
import secrets

from app.config.settings import (
    SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, 
    REFRESH_TOKEN_EXPIRE_DAYS
)
from app.config.database import get_db_connection


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    password_bytes = plain_password.encode('utf-8')
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
    return bcrypt.checkpw(password_bytes, hashed_password.encode('utf-8'))


def get_password_hash(password: str) -> str:
    """获取密码哈希"""
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode('utf-8')


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建访问令牌"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token() -> str:
    """创建刷新令牌"""
    import secrets
    return secrets.token_urlsafe(32)


async def get_current_user(request: Request, access_token: Optional[str] = Cookie(None)) -> dict:
    """获取当前登录用户"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="未认证",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not access_token:
        # 尝试从Authorization header获取
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            access_token = auth_header.split(" ")[1]
        else:
            raise credentials_exception

    try:
        payload = jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        user_id: int = payload.get("user_id")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    try:
        if user_id:
            cursor.execute("SELECT * FROM users WHERE id = %s AND username = %s", (user_id, username))
        else:
            cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
    finally:
        cursor.close()
        conn.close()

    if user is None:
        raise credentials_exception

    # 移除密码字段
    user.pop('password', None)
    return user


async def get_current_active_user(current_user: dict):
    """获取当前活跃用户"""
    if not current_user.get('is_active'):
        raise HTTPException(status_code=400, detail="用户已禁用")
    return current_user


def is_test_mode() -> bool:
    """检查是否处于测试模式（从数据库配置读取）"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute("SELECT config_value FROM system_config WHERE config_key = 'test_mode'")
        result = cursor.fetchone()
        cursor.close()
        conn.close()

        if result and result['config_value'].lower() == 'true':
            return True
        return False
    except Exception:
        return False


def load_user_longbridge_config(user_id: int) -> dict:
    """加载用户的长桥配置"""
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("""
        SELECT config_key, config_value
        FROM user_config
        WHERE user_id = %s AND config_key IN (
            'longbridge_app_key', 'longbridge_app_secret', 'longbridge_access_token',
            'longbridge_http_url', 'longbridge_quote_ws_url', 'longbridge_trade_ws_url'
        )
    """, (user_id,))
    configs = cursor.fetchall()
    cursor.close()
    conn.close()
    
    config_dict = {row['config_key']: row['config_value'] for row in configs}
    
    return {
        'app_key': config_dict.get('longbridge_app_key', ''),
        'app_secret': config_dict.get('longbridge_app_secret', ''),
        'access_token': config_dict.get('longbridge_access_token', ''),
        'http_url': config_dict.get('longbridge_http_url', ''),
        'quote_ws_url': config_dict.get('longbridge_quote_ws_url', ''),
        'trade_ws_url': config_dict.get('longbridge_trade_ws_url', '')
    }
