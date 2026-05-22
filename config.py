import json
import os
import threading

_config = None
_config_lock = threading.Lock()

# proxy_source 取值:
#   "api"      - 从 API 拉取 HOST:PORT 列表
#   "file"     - 从文件读取 HOST:PORT:USER:PASS
#   "freefile" - 从文件读取 HOST:PORT
#   "none"     - 直连模式,不走代理
_DEFAULTS = {
    "choose_browser": "ruyipage",
    "email_suffix": "@outlook.com",
    "proxy_source": "api",
    "proxy_file": "proxies.txt",
    "proxy_api_url": "",
    "proxy_api_timeout": 8,
    "proxy_test_urls": [
        "https://outlook.live.com/mail/0/?prompt=create_account",
        "https://login.live.com",
    ],
    "proxy_test_timeout": 8,
    "bot_protection_wait": 11,
    "max_captcha_retries": 2,
    "concurrent_flows": 10,
    "max_tasks": 20,
    "oauth2": {
        "enable_oauth2": True,
        "client_id": "",
        "redirect_url": "http://localhost:8000",
        "Scopes": [
            "offline_access",
            "https://graph.microsoft.com/Mail.ReadWrite",
            "https://graph.microsoft.com/Mail.Send",
            "https://graph.microsoft.com/User.Read",
        ],
    },
    "ruyipage": {
        "browser_path": "",
        "profile_root": "Profiles",
        "headless": False,
        "xpath_picker": False,
        "action_visual": False,
    },
    "web": {
        "host": "0.0.0.0",
        "port": 8787,
        # SHA256(password) hex; 空字符串表示尚未设置密码,首次访问时由用户设置
        "password_hash": "",
        # 会话密钥,首次启动时自动生成并写回 config.json
        "session_secret": "",
    },
}


def _config_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def _deep_merge_section(defaults_section, user_section):
    """为带有嵌套对象的 section 做一层深合并。"""
    if not isinstance(user_section, dict):
        return dict(defaults_section)
    merged = dict(defaults_section)
    merged.update(user_section)
    return merged


def _load_base_config():
    path = _config_path()
    if not os.path.exists(path):
        return dict(_DEFAULTS)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        merged = dict(_DEFAULTS)
        merged.update(data)
        for nested_key in ("oauth2", "ruyipage", "web"):
            if nested_key in data:
                merged[nested_key] = _deep_merge_section(
                    _DEFAULTS[nested_key], data[nested_key]
                )
        return merged
    except (json.JSONDecodeError, OSError):
        return dict(_DEFAULTS)


def get_config():
    global _config
    if _config is None:
        with _config_lock:
            if _config is None:
                _config = _load_base_config()
    return _config


def update_config(overrides):
    global _config
    with _config_lock:
        if _config is None:
            _config = _load_base_config()
        _config.update(overrides)


def update_section(section, overrides):
    """对嵌套 section(如 oauth2/ruyipage/web)做局部更新。"""
    global _config
    with _config_lock:
        if _config is None:
            _config = _load_base_config()
        current = dict(_config.get(section, {}))
        current.update(overrides or {})
        _config[section] = current


def save_config():
    with _config_lock:
        if _config is None:
            return
        path = _config_path()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(_config, f, ensure_ascii=False, indent=4)


def reload_config():
    """强制从磁盘重新加载配置。"""
    global _config
    with _config_lock:
        _config = _load_base_config()
    return _config
