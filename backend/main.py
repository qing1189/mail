"""FastAPI 主入口"""
import asyncio
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# 添加项目根目录到 path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.api.config import router as config_router
from backend.api.task import router as task_router
from backend.api.result import router as result_router
from backend.api.auth import router as auth_router, verify_token
from backend.api.websocket import ws_manager, broadcast_status, broadcast_log
from backend.core.state import state
from backend.core.task_manager import task_manager
from backend.core.log_capture import log_capture

# 静态文件目录
STATIC_DIR = Path(__file__).parent.parent / "static"

# 不需要认证的路径
PUBLIC_PATHS = [
    "/api/auth/login",
    "/api/auth/check",
    "/api/auth/status",
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
]


def on_log_message(message: str):
    """日志消息回调"""
    state.add_log(message)
    # 异步广播到 WebSocket
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(broadcast_log(message))
    except Exception:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    os.makedirs("Results", exist_ok=True)
    
    # 启动日志捕获
    log_capture.set_callback(on_log_message)
    log_capture.start()
    
    yield
    
    # 关闭时
    log_capture.stop()
    task_manager.cleanup()


app = FastAPI(
    title="Outlook Register Web UI",
    description="Outlook/Hotmail 邮箱自动注册工具 Web 控制面板",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册 API 路由
app.include_router(auth_router)
app.include_router(config_router)
app.include_router(task_router)
app.include_router(result_router)


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """认证中间件"""
    path = request.url.path
    
    # 公开路径不需要认证
    if any(path.startswith(p) for p in PUBLIC_PATHS):
        return await call_next(request)
    
    # WebSocket 连接检查 cookie
    if path.startswith("/ws/"):
        token = request.cookies.get("auth_token")
        if not verify_token(token):
            return Response(status_code=401, content="Unauthorized")
        return await call_next(request)
    
    # 静态资源和首页不需要认证（前端会处理登录状态）
    if path.startswith("/assets") or path == "/" or path == "/index.html":
        return await call_next(request)
    
    # API 路由需要认证
    if path.startswith("/api/"):
        token = request.cookies.get("auth_token")
        if not verify_token(token):
            return Response(status_code=401, content="Unauthorized")
        return await call_next(request)
    
    # 其他路径（SPA 路由）不需要认证
    return await call_next(request)


@app.websocket("/ws/status")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 端点 - 实时状态推送"""
    await ws_manager.connect(websocket)
    try:
        # 发送当前状态
        await websocket.send_json({
            "type": "status",
            "data": state.get_status(),
        })
        
        # 发送最近的日志
        recent_logs = state.get_logs(50)
        for log in recent_logs:
            await websocket.send_json({
                "type": "log",
                "data": {"message": log},
            })

        # 保持连接
        while True:
            try:
                # 接收客户端消息（心跳）
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                # 如果收到 ping，回复 pong
                if data == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                # 超时发送心跳
                try:
                    await websocket.send_text("heartbeat")
                except Exception:
                    break
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)


@app.get("/health")
async def health():
    return {"status": "ok"}


# 静态文件服务（前端构建产物）
if STATIC_DIR.exists():
    # 挂载静态资源
    app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="assets")

    # SPA 路由 - 所有非 API 路由都返回 index.html
    @app.get("/{full_path:path}")
    async def serve_spa(request: Request, full_path: str):
        # 如果是 API 路由，跳过
        if full_path.startswith("api/") or full_path.startswith("ws/"):
            return {"error": "Not found"}
        
        # 尝试返回静态文件
        file_path = STATIC_DIR / full_path
        if file_path.is_file():
            return FileResponse(str(file_path))
        
        # 返回 index.html（SPA 路由）
        return FileResponse(str(STATIC_DIR / "index.html"))
else:
    @app.get("/")
    async def root():
        return {
            "message": "Outlook Register Web UI",
            "docs": "/docs",
            "note": "Frontend not built. Run 'cd frontend && npm run build' first.",
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
