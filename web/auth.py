"""Web 控制台的密码登录 / 会话管理。

设计:
- 首次启动:config.web.password_hash 为空 → 前端提示设置密码
- 登录:输入密码,SHA256 对比,匹配则下发 Cookie(session_id)
- 会话:内存中维护 session_id → expire_at 的映射
- 所有 API/WebSocket 都通过 require_session 依赖检查

注意:本工具默认是个人/小团队使用,未做高强度防护(没有 CSRF token、没有
密码爆破限速)。不要把它直接挂到公网而不加额外的防护层。
"""

import hashlib
import secrets
import threading
import time
from typing import Optional

from fastapi import Cookie, HTTPException, status

from config import get_config, save_config, update_section


SESSION_COOKIE_NAME = "ms_mail_session"
SESSION_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 天


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


class SessionStore:
    def __init__(self):
        self._lock = threading.Lock()
        self._sessions: "dict[str, float]" = {}

    def create(self) -> str:
        token = secrets.token_urlsafe(32)
        with self._lock:
            self._sessions[token] = time.time() + SESSION_TTL_SECONDS
        return token

    def is_valid(self, token: Optional[str]) -> bool:
        if not token:
            return False
        with self._lock:
            expire_at = self._sessions.get(token)
            if not expire_at:
                return False
            if expire_at < time.time():
                self._sessions.pop(token, None)
                return False
            return True

    def revoke(self, token: Optional[str]):
        if not token:
            return
        with self._lock:
            self._sessions.pop(token, None)

    def revoke_all(self):
        with self._lock:
            self._sessions.clear()


session_store = SessionStore()


def password_is_set() -> bool:
    cfg = get_config()
    return bool(cfg.get("web", {}).get("password_hash"))


def setup_password(password: str):
    if not password or len(password) < 4:
        raise HTTPException(status_code=400, detail="密码长度至少 4 位")
    update_section("web", {"password_hash": _hash_password(password)})
    save_config()


def verify_password(password: str) -> bool:
    cfg = get_config()
    expected = cfg.get("web", {}).get("password_hash", "")
    if not expected:
        return False
    return _hash_password(password) == expected


def change_password(old_password: str, new_password: str):
    if not verify_password(old_password):
        raise HTTPException(status_code=401, detail="旧密码不正确")
    if not new_password or len(new_password) < 4:
        raise HTTPException(status_code=400, detail="新密码长度至少 4 位")
    update_section("web", {"password_hash": _hash_password(new_password)})
    save_config()
    session_store.revoke_all()


# ── FastAPI 依赖 ─────────────────────────────────────────────────────


def require_session(
    token: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE_NAME),
):
    """REST API 依赖:校验会话 cookie。"""
    if not session_store.is_valid(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录或会话已过期",
        )
    return token


def is_session_token_valid(token: Optional[str]) -> bool:
    """供 WebSocket 路由手动校验使用。"""
    return session_store.is_valid(token)
