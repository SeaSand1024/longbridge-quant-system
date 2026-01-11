from fastapi import FastAPI, HTTPException, Depends, Cookie, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
import secrets
from jose import JWTError, jwt
import bcrypt

# JWT配置
SECRET_KEY = "demo-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24小时

# 内存用户存储（仅用于演示）
users_db = {
    1: {
        "id": 1,
        "username": "demo",
        "email": "demo@example.com",
        "password": bcrypt.hashpw("demo123".encode('utf-8')[:72], bcrypt.gensalt()).decode('utf-8'),
        "is_active": True,
        "created_at": datetime.now().isoformat()
    }
}
refresh_tokens_db = {}
user_id_counter = 2

app = FastAPI(title="美股量化交易系统认证演示")

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")

# 请求/响应模型
class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str

# 认证函数
def verify_password(plain_password: str, hashed_password: str) -> bool:
    password_bytes = plain_password.encode('utf-8')
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
    try:
        return bcrypt.checkpw(password_bytes, hashed_password.encode('utf-8'))
    except:
        return False

def get_password_hash(password: str) -> str:
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode('utf-8')

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire.timestamp()})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token() -> str:
    return secrets.token_urlsafe(64)

async def get_current_user(token: Optional[str] = Cookie(None)) -> dict:
    credentials_exception = HTTPException(
        status_code=401,
        detail="未认证",
    )
    
    if not token:
        auth_header = None
        raise credentials_exception
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        user_id: int = payload.get("user_id")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    for user in users_db.values():
        if user["id"] == user_id and user["username"] == username:
            return user
    
    raise credentials_exception

# API端点
@app.get("/")
async def root():
    """根路径"""
    return HTMLResponse(content="""
    <html>
        <head><title>美股量化交易系统认证演示</title></head>
        <body>
            <h1>美股量化交易系统认证演示</h1>
            <p>这是认证功能的演示版本，使用内存数据库。</p>
            <h2>测试账号：</h2>
            <p>用户名: demo</p>
            <p>密码: demo123</p>
            <p><a href="/static/index.html">访问前端页面</a></p>
        </body>
    </html>
    """)

@app.post("/api/auth/register")
async def register(request: RegisterRequest):
    """用户注册"""
    global user_id_counter
    
    # 检查用户名是否已存在
    for user in users_db.values():
        if user["username"] == request.username:
            raise HTTPException(status_code=400, detail="用户名已存在")
    
    # 创建用户
    user_id = user_id_counter
    user_id_counter += 1
    
    user = {
        "id": user_id,
        "username": request.username,
        "email": request.email,
        "password": get_password_hash(request.password),
        "is_active": True,
        "created_at": datetime.now().isoformat()
    }
    users_db[user_id] = user
    
    return {"code": 0, "message": "注册成功", "data": {"user_id": user_id, "username": request.username}}

@app.post("/api/auth/login")
async def login(request: LoginRequest, response: Response):
    """用户登录"""
    # 查找用户
    user = None
    for u in users_db.values():
        if u["username"] == request.username:
            user = u
            break
    
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    
    # 验证密码
    if not verify_password(request.password, user["password"]):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    
    # 创建令牌
    access_token = create_access_token(
        data={"sub": user["username"], "user_id": user["id"]},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    refresh_token = create_refresh_token()
    refresh_tokens_db[refresh_token] = user["id"]
    
    response_data = JSONResponse(content={
        "code": 0,
        "message": "登录成功",
        "data": {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "user": {
                "id": user["id"],
                "username": user["username"],
                "email": user.get("email")
            }
        }
    })
    
    response_data.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
        samesite="lax"
    )
    
    response_data.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        max_age=7 * 24 * 3600,
        path="/",
        samesite="lax"
    )
    
    return response_data

@app.get("/api/auth/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    """获取当前用户信息"""
    return {"code": 0, "data": current_user}

@app.post("/api/auth/logout")
async def logout(response: Response, current_user: dict = Depends(get_current_user)):
    """用户登出"""
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="refresh_token", path="/")
    return {"code": 0, "message": "登出成功"}

@app.post("/api/auth/refresh")
async def refresh(request: Request, response: Response):
    """刷新令牌"""
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token or refresh_token not in refresh_tokens_db:
        raise HTTPException(status_code=401, detail="无效的刷新令牌")
    
    user_id = refresh_tokens_db[refresh_token]
    user = users_db.get(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    
    access_token = create_access_token(
        data={"sub": user["username"], "user_id": user["id"]},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    new_refresh_token = create_refresh_token()
    del refresh_tokens_db[refresh_token]
    refresh_tokens_db[new_refresh_token] = user_id
    
    response_data = JSONResponse(content={
        "code": 0,
        "data": {
            "access_token": access_token,
            "refresh_token": new_refresh_token,
            "token_type": "Bearer"
        }
    })
    
    response_data.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
        samesite="lax"
    )
    
    response_data.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        max_age=7 * 24 * 3600,
        path="/",
        samesite="lax"
    )
    
    return response_data

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5173)
