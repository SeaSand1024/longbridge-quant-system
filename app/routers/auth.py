"""
认证路由
"""
from fastapi import APIRouter, HTTPException, Response, Request
from datetime import datetime, timedelta
import pymysql
import re

from app.models.schemas import LoginRequest, RegisterRequest
from app.config.database import get_db_connection
from app.config.settings import REFRESH_TOKEN_EXPIRE_DAYS, ACCESS_TOKEN_EXPIRE_MINUTES, LONGBRIDGE_CONFIG
from app.auth.utils import (
    verify_password, get_password_hash, 
    create_access_token, create_refresh_token,
    get_current_user, load_user_longbridge_config
)
from fastapi import Depends

router = APIRouter(prefix="/api/auth", tags=["认证"])


def validate_password(password: str) -> tuple[bool, str]:
    """验证密码强度"""
    if not password:
        return False, "密码不能为空"
    if len(password) < 6:
        return False, "密码长度至少6个字符"
    if len(password) > 50:
        return False, "密码长度不能超过50个字符"
    if not re.search(r'[a-zA-Z]', password):
        return False, "密码必须包含字母"
    if not re.search(r'\d', password):
        return False, "密码必须包含数字"
    return True, ""


@router.post("/register")
async def register(request: RegisterRequest):
    """用户注册"""
    # 验证密码强度
    is_valid, error_msg = validate_password(request.password)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)
    
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    try:
        cursor.execute("SELECT id FROM users WHERE username = %s", (request.username,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="用户名已存在")
        
        if request.email:
            cursor.execute("SELECT id FROM users WHERE email = %s", (request.email,))
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="邮箱已被使用")
        
        hashed_password = get_password_hash(request.password)
        cursor.execute(
            "INSERT INTO users (username, password, email) VALUES (%s, %s, %s)",
            (request.username, hashed_password, request.email)
        )
        conn.commit()
        
        return {"code": 0, "message": "注册成功"}
    finally:
        cursor.close()
        conn.close()


@router.post("/login")
async def login(request: LoginRequest, response: Response):
    """用户登录"""
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    try:
        cursor.execute("SELECT * FROM users WHERE username = %s", (request.username,))
        user = cursor.fetchone()
        
        if not user or not verify_password(request.password, user['password']):
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        
        if not user['is_active']:
            raise HTTPException(status_code=403, detail="账户已禁用")
        
        access_token = create_access_token(
            data={"sub": user['username'], "user_id": user['id']},
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        
        refresh_token = create_refresh_token()
        expires_at = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        
        cursor.execute(
            "INSERT INTO refresh_tokens (user_id, token, expires_at) VALUES (%s, %s, %s)",
            (user['id'], refresh_token, expires_at)
        )
        conn.commit()
        
        response.set_cookie(
            key="access_token", value=access_token,
            httponly=True, max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            samesite="lax", secure=False
        )
        response.set_cookie(
            key="refresh_token", value=refresh_token,
            httponly=True, max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
            samesite="lax", secure=False
        )
        
        # 登录成功后加载用户的长桥配置到全局变量
        user_lb_config = load_user_longbridge_config(user['id'])
        if user_lb_config.get('app_key'):
            LONGBRIDGE_CONFIG['app_key'] = user_lb_config['app_key']
        if user_lb_config.get('app_secret'):
            LONGBRIDGE_CONFIG['app_secret'] = user_lb_config['app_secret']
        if user_lb_config.get('access_token'):
            LONGBRIDGE_CONFIG['access_token'] = user_lb_config['access_token']
        
        # 如果用户有完整配置，尝试重新连接SDK
        if user_lb_config.get('app_key') and user_lb_config.get('app_secret') and user_lb_config.get('access_token'):
            try:
                from app.services.longbridge_sdk import longbridge_sdk, LONGBRIDGE_AVAILABLE
                longbridge_sdk.use_real_sdk = LONGBRIDGE_AVAILABLE
                # 异步连接SDK（不阻塞登录）
                import asyncio
                asyncio.create_task(longbridge_sdk.connect())
            except Exception:
                pass  # 忽略SDK连接失败
        
        return {
            "code": 0,
            "message": "登录成功",
            "data": {
                "user": {"id": user['id'], "username": user['username'], "email": user['email']}
            }
        }
    finally:
        cursor.close()
        conn.close()


@router.post("/logout")
async def logout(request: Request, response: Response):
    """用户登出"""
    # 从cookie获取refresh_token并从数据库删除
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM refresh_tokens WHERE token = %s", (refresh_token,))
            conn.commit()
            cursor.close()
            conn.close()
        except Exception:
            pass  # 忽略删除失败
    
    response.delete_cookie(key="access_token")
    response.delete_cookie(key="refresh_token")
    return {"code": 0, "message": "登出成功"}


@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    """获取当前用户信息"""
    return {"code": 0, "data": current_user}
