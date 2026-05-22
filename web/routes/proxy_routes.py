"""代理上传/编辑/测试 路由。"""

import os
from pathlib import Path

from fastapi import APIRouter, Body, Depends, File, HTTPException, UploadFile

from config import get_config, save_config, update_config
from ..auth import require_session
from ..proxy_tester import (
    load_proxies_for_test,
    parse_proxies_text,
    test_proxies,
)


router = APIRouter(prefix="/api/proxies", tags=["proxies"])


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve_proxy_file_path() -> Path:
    cfg = get_config()
    name = cfg.get("proxy_file", "proxies.txt") or "proxies.txt"
    # 安全限制:只允许相对路径,不允许 .. 跳出项目目录
    target = (_project_root() / name).resolve()
    root = _project_root().resolve()
    try:
        target.relative_to(root)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"非法的代理文件路径: {name}")
    return target


@router.get("/file")
def get_file(_=Depends(require_session)):
    """读取当前 proxy_file 文本内容(用于在线编辑)。"""
    path = _resolve_proxy_file_path()
    cfg = get_config()
    if not path.exists():
        return {"path": str(path.relative_to(_project_root())), "content": "", "exists": False, "proxy_source": cfg.get("proxy_source")}
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    return {
        "path": str(path.relative_to(_project_root())),
        "content": content,
        "exists": True,
        "proxy_source": cfg.get("proxy_source"),
    }


@router.put("/file")
def put_file(payload: dict = Body(...), _=Depends(require_session)):
    """覆盖 proxy_file 内容。"""
    content = (payload or {}).get("content", "")
    if not isinstance(content, str):
        raise HTTPException(status_code=400, detail="content 必须是字符串")
    path = _resolve_proxy_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return {"ok": True, "bytes": len(content.encode("utf-8"))}


@router.post("/upload")
async def upload_file(file: UploadFile = File(...), _=Depends(require_session)):
    """上传 proxies.txt(覆盖目标文件)。"""
    path = _resolve_proxy_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = await file.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("utf-8", errors="replace")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return {"ok": True, "filename": file.filename, "bytes": len(raw)}


@router.post("/test")
def test_endpoint(payload: dict = Body(default={}), _=Depends(require_session)):
    """测试代理。

    payload 可选字段:
    - source: "current" | "file" | "freefile" | "inline"  (默认 current)
    - file_path: 当 source 为 file/freefile 时使用,默认配置 proxy_file
    - inline_text: 当 source 为 inline 时使用
    - urls: 自定义测试 URL 列表
    - timeout: 超时(秒)
    - limit: 最多测多少条(默认 10)
    - concurrency: 并发数(默认 5)
    """
    source = (payload or {}).get("source", "current")
    file_path = (payload or {}).get("file_path")
    inline_text = (payload or {}).get("inline_text")
    urls = (payload or {}).get("urls")
    timeout = (payload or {}).get("timeout")
    limit = (payload or {}).get("limit", 10)
    concurrency = (payload or {}).get("concurrency", 5)

    if file_path:
        # 安全:相对项目根
        candidate = (_project_root() / file_path).resolve()
        try:
            candidate.relative_to(_project_root().resolve())
        except ValueError:
            raise HTTPException(status_code=400, detail="非法的文件路径")
        file_path = str(candidate)

    proxies = load_proxies_for_test(source=source, file_path=file_path, inline_text=inline_text)
    if not proxies:
        return {"total": 0, "tested": 0, "passed": 0, "results": []}

    results = test_proxies(
        proxies=proxies,
        urls=urls,
        timeout=timeout,
        limit=limit,
        concurrency=concurrency,
    )
    passed = sum(1 for r in results if r.ok)
    return {
        "total": len(proxies),
        "tested": len(results),
        "passed": passed,
        "results": [r.to_dict() for r in results],
    }
