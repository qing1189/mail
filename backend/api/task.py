"""任务控制 API"""
import os
import sys
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

# 添加项目根目录到 path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from backend.core.task_manager import task_manager
from backend.core.state import state
from backend.api.websocket import broadcast_status

router = APIRouter(prefix="/api/task", tags=["task"])


class TaskStartConfig(BaseModel):
    concurrent_flows: Optional[int] = None
    max_tasks: Optional[int] = None
    email_suffix: Optional[str] = None
    proxy_source: Optional[str] = None
    proxy_file: Optional[str] = None
    proxy_api_url: Optional[str] = None
    enable_oauth2: Optional[bool] = None
    client_id: Optional[str] = None
    redirect_url: Optional[str] = None


@router.post("/start")
async def start_task(config: TaskStartConfig):
    """启动任务"""
    if state.task_status.is_running:
        return {"code": 1, "message": "任务已在运行中"}

    # 构建配置
    task_config = {}
    if config.concurrent_flows is not None:
        task_config["concurrent_flows"] = config.concurrent_flows
    if config.max_tasks is not None:
        task_config["max_tasks"] = config.max_tasks
    if config.email_suffix is not None:
        task_config["email_suffix"] = config.email_suffix
    if config.proxy_source is not None:
        task_config["proxy_source"] = config.proxy_source
    if config.proxy_file is not None:
        task_config["proxy_file"] = config.proxy_file
    if config.proxy_api_url is not None:
        task_config["proxy_api_url"] = config.proxy_api_url

    # OAuth2 配置
    oauth2_config = {}
    if config.enable_oauth2 is not None:
        oauth2_config["enable_oauth2"] = config.enable_oauth2
    if config.client_id is not None:
        oauth2_config["client_id"] = config.client_id
    if config.redirect_url is not None:
        oauth2_config["redirect_url"] = config.redirect_url
    if oauth2_config:
        task_config["oauth2"] = oauth2_config

    success = task_manager.start(task_config)
    if success:
        await broadcast_status(state.get_status())
        return {"code": 0, "message": "任务已启动"}
    else:
        return {"code": 1, "message": "启动失败"}


@router.post("/stop")
async def stop_task():
    """停止任务"""
    if not state.task_status.is_running:
        return {"code": 1, "message": "没有正在运行的任务"}

    success = task_manager.stop()
    if success:
        await broadcast_status(state.get_status())
        return {"code": 0, "message": "正在停止任务..."}
    else:
        return {"code": 1, "message": "停止失败"}


@router.get("/status")
async def get_task_status():
    """获取任务状态"""
    return {"code": 0, "data": state.get_status()}


@router.get("/logs")
async def get_task_logs(limit: int = 100):
    """获取任务日志"""
    return {"code": 0, "data": state.get_logs(limit)}


@router.get("/success")
async def get_success_emails(limit: int = 100):
    """获取成功注册的邮箱"""
    return {"code": 0, "data": state.get_success_emails(limit)}
