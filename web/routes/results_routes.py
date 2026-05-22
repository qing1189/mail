"""结果文件浏览/下载 路由。"""

import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse

from ..auth import require_session


router = APIRouter(prefix="/api/results", tags=["results"])


_RESULT_FILES = {
    "registered": "logged_email.txt",        # 注册成功 + 已授权 (oauth2 启用)
    "registered_unauth": "unlogged_email.txt",  # 注册成功 + 未授权 (oauth2 关闭)
    "tokens": "outlook_token.txt",            # OAuth2 拿到 refresh token 的账号
}


def _results_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "Results"


def _resolve(name: str) -> Path:
    if name not in _RESULT_FILES:
        raise HTTPException(status_code=404, detail="未知的结果文件类型")
    return _results_dir() / _RESULT_FILES[name]


@router.get("")
def index(_=Depends(require_session)):
    """所有结果文件的元信息(行数、字节数、是否存在)。"""
    summary = {}
    for key, filename in _RESULT_FILES.items():
        path = _results_dir() / filename
        if path.exists():
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                lines = sum(1 for _ in f)
            summary[key] = {
                "filename": filename,
                "exists": True,
                "lines": lines,
                "bytes": path.stat().st_size,
            }
        else:
            summary[key] = {
                "filename": filename,
                "exists": False,
                "lines": 0,
                "bytes": 0,
            }
    return summary


@router.get("/{name}/preview", response_class=PlainTextResponse)
def preview(name: str, limit: int = 200, _=Depends(require_session)):
    path = _resolve(name)
    if not path.exists():
        return ""
    lines = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f):
            if i >= limit:
                break
            lines.append(line.rstrip("\n"))
    return "\n".join(lines)


@router.get("/{name}/download")
def download(name: str, _=Depends(require_session)):
    path = _resolve(name)
    if not path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(path, media_type="text/plain", filename=path.name)
