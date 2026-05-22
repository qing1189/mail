"""WebSocket 连接管理"""
import asyncio
import json
from typing import List
from fastapi import WebSocket


class ConnectionManager:
    """WebSocket 连接管理器"""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        """广播消息到所有连接"""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)

        # 清理断开的连接
        for conn in disconnected:
            try:
                self.active_connections.remove(conn)
            except ValueError:
                pass

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        try:
            await websocket.send_json(message)
        except Exception:
            pass


# 全局连接管理器
ws_manager = ConnectionManager()


async def broadcast_status(status: dict):
    """广播状态更新"""
    await ws_manager.broadcast({
        "type": "status",
        "data": status,
    })


async def broadcast_log(message: str):
    """广播日志"""
    await ws_manager.broadcast({
        "type": "log",
        "data": {"message": message},
    })


async def broadcast_success(email: str):
    """广播成功消息"""
    await ws_manager.broadcast({
        "type": "success",
        "data": {"email": email},
    })
