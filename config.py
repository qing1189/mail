import json
import os
import threading

_config = None
_config_lock = threading.Lock()

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
}


def _config_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def _load_base_config():
    path = _config_path()
    if not os.path.exists(path):
        return dict(_DEFAULTS)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        merged = dict(_DEFAULTS)
        merged.update(data)
        if "oauth2" in data and isinstance(data["oauth2"], dict):
            merged_oauth = dict(_DEFAULTS["oauth2"])
            merged_oauth.update(data["oauth2"])
            merged["oauth2"] = merged_oauth
        if "ruyipage" in data and isinstance(data["ruyipage"], dict):
            merged_rp = dict(_DEFAULTS["ruyipage"])
            merged_rp.update(data["ruyipage"])
            merged["ruyipage"] = merged_rp
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


def save_config():
    with _config_lock:
        if _config is None:
            return
        path = _config_path()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(_config, f, ensure_ascii=False, indent=4)
