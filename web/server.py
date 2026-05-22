"""FastAPI 应用入口。"""

import asyncio
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .log_bus import log_bus
from .task_manager import task_manager
from .routes import (
    auth_routes,
    batch_routes,
    config_routes,
    proxy_routes,
    results_routes,
    ws_routes,
)


def create_app() -> FastAPI:
    app = FastAPI(
        title="MS Mail Reg Tool — Web Console",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url=None,
    )

    static_dir = Path(__file__).resolve().parent / "static"
    static_dir.mkdir(parents=True, exist_ok=True)

    # 静态资源
    app.mount(
        "/assets",
        StaticFiles(directory=static_dir, html=False),
        name="assets",
    )

    # API 路由
    app.include_router(auth_routes.router)
    app.include_router(config_routes.router)
    app.include_router(proxy_routes.router)
    app.include_router(batch_routes.router)
    app.include_router(results_routes.router)
    app.include_router(ws_routes.router)

    @app.get("/", include_in_schema=False)
    def index():
        index_path = static_dir / "index.html"
        return FileResponse(str(index_path))

    @app.on_event("startup")
    async def _startup():
        loop = asyncio.get_running_loop()
        log_bus.attach_loop(loop)
        log_bus.patch_streams()
        task_manager.start_scheduler()
        log_bus.emit("info", "[Info] - Web 控制台已启动")

    @app.on_event("shutdown")
    async def _shutdown():
        log_bus.emit("info", "[Info] - Web 控制台准备关闭")
        log_bus.unpatch_streams()

    return app


app = create_app()
