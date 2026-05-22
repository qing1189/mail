"""认证相关路由。"""

from fastapi import APIRouter, Body, Depends, HTTPException, Response

from ..auth import (
    SESSION_COOKIE_NAME,
    SESSION_TTL_SECONDS,
    change_password,
    password_is_set,
    require_session,
    session_store,
    setup_password,
    verify_password,
)


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/status")
def auth_status(token: str | None = None):
    return {
        "setup_required": not password_is_set(),
        "authenticated": session_store.is_valid(token) if token else False,
    }


@router.post("/setup")
def setup(payload: dict = Body(...)):
    if password_is_set():
        raise HTTPException(status_code=400, detail="密码已经设置过了")
    password = (payload or {}).get("password", "")
    setup_password(password)
    return {"ok": True}


@router.post("/login")
def login(payload: dict = Body(...), response: Response = None):
    if not password_is_set():
        raise HTTPException(status_code=400, detail="尚未设置密码,请先调用 /api/auth/setup")
    password = (payload or {}).get("password", "")
    if not verify_password(password):
        raise HTTPException(status_code=401, detail="密码错误")
    token = session_store.create()
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return {"ok": True, "token": token}


@router.post("/logout")
def logout(token: str = Depends(require_session), response: Response = None):
    session_store.revoke(token)
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return {"ok": True}


@router.post("/change-password")
def change_pw(
    payload: dict = Body(...),
    _token: str = Depends(require_session),
    response: Response = None,
):
    old_password = (payload or {}).get("old_password", "")
    new_password = (payload or {}).get("new_password", "")
    change_password(old_password, new_password)
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return {"ok": True, "message": "密码已更新,请重新登录"}
