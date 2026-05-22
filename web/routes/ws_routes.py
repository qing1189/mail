"""WebSocket 实时事件推送(日志 + 批次状态)。"""

import asyncio
import json

from fastapi import APIRouter, Cookie, WebSocket, WebSocketDisconnect, status

from ..auth import SESSION_COOKIE_NAME, is_session_token_valid
from ..log_bus import log_bus
from ..task_manager import task_manager


router = APIRouter()


@router.websocket("/ws/events")
async def ws_events(
    websocket: WebSocket,
    token: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
):
    # 也允许 query string 携带 token,兼容更多客户端
    query_token = websocket.query_params.get("token")
    effective = token or query_token

    if not is_session_token_valid(effective):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()

    queue = log_bus.subscribe()
    try:
        # 1) 历史日志
        history = log_bus.history(limit=100)
        await websocket.send_text(json.dumps({"type": "history", "data": history}, ensure_ascii=False))
        # 2) 当前批次列表快照
        await websocket.send_text(
            json.dumps({"type": "batch_snapshot", "data": task_manager.list_batches()}, ensure_ascii=False)
        )

        while True:
            envelope = await queue.get()
            await websocket.send_text(json.dumps(envelope, ensure_ascii=False))
    except WebSocketDisconnect:
        pass
    except asyncio.CancelledError:
        pass
    finally:
        log_bus.unsubscribe(queue)
