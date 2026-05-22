"""配置管理 API"""
import os
import sys
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, List

# 添加项目根目录到 path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from config import get_config, update_config, save_config

router = APIRouter(prefix="/api/config", tags=["config"])


class OAuth2Config(BaseModel):
    enable_oauth2: Optional[bool] = None
    client_id: Optional[str] = None
    redirect_url: Optional[str] = None
    Scopes: Optional[List[str]] = None


class RuyiPageConfig(BaseModel):
    browser_path: Optional[str] = None
    profile_root: Optional[str] = None
    headless: Optional[bool] = None
    xpath_picker: Optional[bool] = None
    action_visual: Optional[bool] = None


class ConfigUpdate(BaseModel):
    email_suffix: Optional[str] = None
    proxy_source: Optional[str] = None
    proxy_file: Optional[str] = None
    proxy_api_url: Optional[str] = None
    proxy_api_timeout: Optional[int] = None
    bot_protection_wait: Optional[int] = None
    max_captcha_retries: Optional[int] = None
    concurrent_flows: Optional[int] = None
    max_tasks: Optional[int] = None
    oauth2: Optional[OAuth2Config] = None
    ruyipage: Optional[RuyiPageConfig] = None


@router.get("")
async def get_current_config():
    """获取当前配置"""
    config = get_config()
    # 隐藏敏感信息
    safe_config = dict(config)
    if "oauth2" in safe_config and "client_id" in safe_config["oauth2"]:
        client_id = safe_config["oauth2"]["client_id"]
        if client_id:
            safe_config["oauth2"]["client_id"] = client_id[:4] + "****" + client_id[-4:] if len(client_id) > 8 else "****"
    return {"code": 0, "data": safe_config}


@router.put("")
async def update_current_config(config_update: ConfigUpdate):
    """更新配置"""
    update_data = config_update.model_dump(exclude_none=True)

    # 处理嵌套配置
    current_config = get_config()

    if "oauth2" in update_data:
        oauth2_update = update_data.pop("oauth2")
        current_oauth2 = dict(current_config.get("oauth2", {}))
        current_oauth2.update(oauth2_update)
        update_data["oauth2"] = current_oauth2

    if "ruyipage" in update_data:
        ruyipage_update = update_data.pop("ruyipage")
        current_ruyipage = dict(current_config.get("ruyipage", {}))
        current_ruyipage.update(ruyipage_update)
        update_data["ruyipage"] = current_ruyipage

    update_config(update_data)
    save_config()

    return {"code": 0, "message": "配置已更新"}


@router.post("/reset")
async def reset_config():
    """重置为默认配置"""
    from config import _DEFAULTS
    update_config(_DEFAULTS)
    save_config()
    return {"code": 0, "message": "配置已重置为默认值"}
