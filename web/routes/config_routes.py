"""配置项 GET/PUT 路由。"""

from copy import deepcopy

from fastapi import APIRouter, Body, Depends, HTTPException

from config import get_config, save_config, update_config
from ..auth import require_session


router = APIRouter(prefix="/api/config", tags=["config"])

# 在返回给前端时,这些敏感字段会被脱敏
_SENSITIVE_PATHS = (
    ("web", "password_hash"),
    ("web", "session_secret"),
)

# 不允许通过 PUT /api/config 直接修改的顶级或嵌套字段
_PROTECTED_TOP_KEYS = {"web", "choose_browser"}


def _redact(cfg: dict) -> dict:
    out = deepcopy(cfg)
    for path in _SENSITIVE_PATHS:
        cursor = out
        for key in path[:-1]:
            cursor = cursor.get(key, {}) if isinstance(cursor, dict) else {}
        if isinstance(cursor, dict) and path[-1] in cursor:
            cursor[path[-1]] = "***" if cursor[path[-1]] else ""
    # web 配置只暴露 host/port,不返回 password_hash/session_secret
    web = out.get("web", {})
    out["web"] = {
        "host": web.get("host"),
        "port": web.get("port"),
        "password_set": bool(web.get("password_hash")),
    }
    return out


@router.get("")
def get_config_route(_=Depends(require_session)):
    return _redact(get_config())


@router.put("")
def put_config_route(payload: dict = Body(...), _=Depends(require_session)):
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="payload 必须是对象")

    sanitized = {}
    for key, value in payload.items():
        if key in _PROTECTED_TOP_KEYS:
            continue
        sanitized[key] = value

    # 嵌套对象做深合并,而不是整段覆盖
    current = get_config()
    for key, value in list(sanitized.items()):
        if key in ("oauth2", "ruyipage") and isinstance(value, dict):
            merged = dict(current.get(key, {}))
            merged.update(value)
            sanitized[key] = merged

    update_config(sanitized)
    save_config()
    return _redact(get_config())
