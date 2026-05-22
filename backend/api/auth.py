"""认证 API"""
import hashlib
import os
import secrets
import sys
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from pydantic import BaseModel

# 添加项目根目录到 path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

router = APIRouter(prefix="/api/auth", tags=["auth"])

# 从环境变量读取密码，如果没有则使用默认密码
WEB_PASSWORD = os.environ.get("WEB_PASSWORD", "admin123")
# Token 有效期（小时）
TOKEN_EXPIRE_HOURS = int(os.environ.get("TOKEN_EXPIRE_HOURS", "24"))

# 存储有效的 token（生产环境应使用 Redis）
valid_tokens: dict[str, datetime] = {}


def hash_password(password: str) -> str:
    """密码哈希"""
    return hashlib.sha256(password.encode()).hexdigest()


def generate_token() -> str:
    """生成随机 token"""
    return secrets.token_hex(32)


def verify_token(token: Optional[str]) -> bool:
    """验证 token 是否有效"""
    if not token:
        return False
    
    # 检查 token 是否存在且未过期
    if token in valid_tokens:
        expire_time = valid_tokens[token]
        if datetime.now() < expire_time:
            return True
        else:
            # 清理过期 token
            del valid_tokens[token]
    
    return False


def cleanup_expired_tokens():
    """清理过期 token"""
    now = datetime.now()
    expired = [t for t, exp in valid_tokens.items() if exp < now]
    for t in expired:
        del valid_tokens[t]


class LoginRequest(BaseModel):
    password: str


class LoginResponse(BaseModel):
    success: bool
    message: str
    token: Optional[str] = None


@router.post("/login")
async def login(request: LoginRequest, response: Response):
    """登录"""
    # 验证密码
    if hash_password(request.password) != hash_password(WEB_PASSWORD):
        raise HTTPException(status_code=401, detail="密码错误")
    
    # 生成 token
    token = generate_token()
    expire_time = datetime.now() + timedelta(hours=TOKEN_EXPIRE_HOURS)
    valid_tokens[token] = expire_time
    
    # 清理过期 token
    cleanup_expired_tokens()
    
    # 设置 cookie
    response.set_cookie(
        key="auth_token",
        value=token,
        httponly=True,
        max_age=TOKEN_EXPIRE_HOURS * 3600,
        samesite="lax",
    )
    
    return LoginResponse(success=True, message="登录成功", token=token)


@router.post("/logout")
async def logout(response: Response, auth_token: Optional[str] = Cookie(None)):
    """登出"""
    if auth_token and auth_token in valid_tokens:
        del valid_tokens[auth_token]
    
    response.delete_cookie("auth_token")
    return {"success": True, "message": "已登出"}


@router.get("/check")
async def check_auth(auth_token: Optional[str] = Cookie(None)):
    """检查认证状态"""
    if verify_token(auth_token):
        return {"authenticated": True}
    return {"authenticated": False}


@router.get("/status")
async def auth_status():
    """获取认证配置状态"""
    return {
        "password_protected": bool(WEB_PASSWORD),
        "password_length": len(WEB_PASSWORD) if WEB_PASSWORD else 0,
    }
