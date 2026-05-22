"""代理管理 API"""
import os
import sys
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional

# 添加项目根目录到 path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

router = APIRouter(prefix="/api/proxies", tags=["proxies"])

# 代理文件路径
PROXY_FILE = os.path.join(os.path.dirname(__file__), "../..", "proxies.txt")


class ProxyItem(BaseModel):
    host: str
    port: str
    username: Optional[str] = ""
    password: Optional[str] = ""


class ProxyList(BaseModel):
    proxies: List[ProxyItem]


def _read_proxies() -> List[dict]:
    """读取代理列表"""
    if not os.path.exists(PROXY_FILE) or not os.path.isfile(PROXY_FILE):
        return []
    
    proxies = []
    with open(PROXY_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(":")
            if len(parts) >= 2:
                proxy = {
                    "host": parts[0],
                    "port": parts[1],
                    "username": parts[2] if len(parts) > 2 else "",
                    "password": parts[3] if len(parts) > 3 else "",
                }
                proxies.append(proxy)
    return proxies


def _write_proxies(proxies: List[dict]):
    """写入代理列表"""
    os.makedirs(os.path.dirname(PROXY_FILE), exist_ok=True)
    with open(PROXY_FILE, "w", encoding="utf-8") as f:
        for proxy in proxies:
            username = proxy.get("username", "")
            password = proxy.get("password", "")
            if username or password:
                f.write(f"{proxy['host']}:{proxy['port']}:{username}:{password}\n")
            else:
                f.write(f"{proxy['host']}:{proxy['port']}\n")


@router.get("")
async def get_proxies():
    """获取代理列表"""
    proxies = _read_proxies()
    return {"code": 0, "data": proxies}


@router.post("")
async def save_proxies(data: ProxyList):
    """保存代理列表"""
    proxies = [p.model_dump() for p in data.proxies]
    _write_proxies(proxies)
    return {"code": 0, "message": f"已保存 {len(proxies)} 个代理"}


@router.post("/add")
async def add_proxy(proxy: ProxyItem):
    """添加单个代理"""
    proxies = _read_proxies()
    # 检查是否已存在
    for p in proxies:
        if p["host"] == proxy.host and p["port"] == proxy.port:
            return {"code": 1, "message": "代理已存在"}
    
    proxies.append(proxy.model_dump())
    _write_proxies(proxies)
    return {"code": 0, "message": "代理已添加"}


@router.delete("/{host}/{port}")
async def delete_proxy(host: str, port: str):
    """删除代理"""
    proxies = _read_proxies()
    proxies = [p for p in proxies if not (p["host"] == host and p["port"] == port)]
    _write_proxies(proxies)
    return {"code": 0, "message": "代理已删除"}


@router.delete("")
async def clear_proxies():
    """清空代理列表"""
    _write_proxies([])
    return {"code": 0, "message": "代理列表已清空"}
