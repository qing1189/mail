import os
import random
import requests
import secrets
import string
import threading
from urllib.parse import quote

from config import get_config


def random_email():
    letter_count = random.randint(6, 8)
    digit_count = random.randint(5, 6)
    letters = "".join(random.choice(string.ascii_lowercase) for _ in range(letter_count))
    digits = "".join(random.choice(string.digits) for _ in range(digit_count))
    return letters + digits


def generate_strong_password(length=random.randint(11, 15)):
    chars = string.ascii_letters + string.digits + "!@#$%^&*"

    while True:
        password = "".join(secrets.choice(chars) for _ in range(length))

        if (
            any(c.islower() for c in password)
            and any(c.isupper() for c in password)
            and any(c.isdigit() for c in password)
            and any(c in "!@#$%^&*" for c in password)
        ):
            return password


def build_proxy_config(host, port, username="", password=""):
    server = f"http://{host}:{port}"
    if username or password:
        encoded_username = quote(username, safe="")
        encoded_password = quote(password, safe="")
        requests_url = f"http://{encoded_username}:{encoded_password}@{host}:{port}"
    else:
        requests_url = server

    return {
        "server": server,
        "username": username,
        "password": password,
        "requests_url": requests_url,
    }


def parse_http_proxy_line(line, proxy_source="file"):
    parts = line.strip().split(":")
    if proxy_source == "freefile":
        if len(parts) < 2:
            return None
        return build_proxy_config(parts[0], parts[1])

    if len(parts) != 4 or not all(parts):
        return None
    return build_proxy_config(parts[0], parts[1], parts[2], parts[3])


def parse_http_proxy_api_response(text):
    parts = text.strip().split(":", 1)
    if len(parts) != 2 or not all(parts):
        return None

    host, port = parts
    return build_proxy_config(host, port)


def parse_http_proxy_api_responses(text):
    proxies = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        proxy = parse_http_proxy_api_response(line)
        if proxy:
            proxies.append(proxy)
    return proxies


def load_http_proxies(file_path=None, proxy_source="file"):
    if file_path is None:
        data = get_config()
        file_path = data.get("proxy_file", "proxies.txt")

    # 检查路径是否存在且是文件
    if not os.path.exists(file_path) or not os.path.isfile(file_path):
        return []

    proxies = []
    with open(file_path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            proxy = parse_http_proxy_line(line, proxy_source=proxy_source)
            if proxy:
                proxies.append(proxy)
    return proxies


def load_proxies_from_api(api_url, timeout=8):
    if not api_url:
        return []

    try:
        response = requests.get(api_url, timeout=(5, timeout))
        response.raise_for_status()
        return parse_http_proxy_api_responses(response.text)
    except Exception:
        return []


def build_requests_proxy(proxy_config):
    if not proxy_config:
        return {"http": None, "https": None}

    return {
        "http": proxy_config["requests_url"],
        "https": proxy_config["requests_url"],
    }


_proxy_health_lock = threading.Lock()
_bad_proxy_keys = set()
_proxy_assignment_lock = threading.Lock()
_proxy_assignment_index = 0
_cached_api_proxy_batch = None
_cached_api_proxy_signature = None
_active_proxy_keys = set()


def _get_proxy_key(proxy_config):
    return proxy_config["server"], proxy_config["username"], proxy_config["password"]


def format_proxy_label(proxy_config):
    if not proxy_config:
        return "none"
    if proxy_config["username"]:
        return f"{proxy_config['server']}:{proxy_config['username']}:***"
    return proxy_config["server"]


def reserve_proxy(proxy_config):
    if not proxy_config:
        return False

    key = _get_proxy_key(proxy_config)
    with _proxy_assignment_lock:
        if key in _active_proxy_keys:
            return False
        _active_proxy_keys.add(key)
        return True


def release_proxy(proxy_config):
    if not proxy_config:
        return

    key = _get_proxy_key(proxy_config)
    with _proxy_assignment_lock:
        _active_proxy_keys.discard(key)


def _is_proxy_active(proxy_config):
    if not proxy_config:
        return False

    key = _get_proxy_key(proxy_config)
    with _proxy_assignment_lock:
        return key in _active_proxy_keys


def _get_api_proxy_signature(source_config):
    return source_config["proxy_api_url"], source_config["proxy_api_timeout"]


def get_proxy_source_config():
    data = get_config()

    return {
        "proxy_source": data.get("proxy_source", "file"),
        "proxy_file": data.get("proxy_file", "proxies.txt"),
        "proxy_api_url": data.get("proxy_api_url", ""),
        "proxy_api_timeout": data.get("proxy_api_timeout", 8),
    }


def get_proxy_candidates(file_path=None, proxy_source=None, force_refresh=False):
    source_config = get_proxy_source_config()
    selected_source = proxy_source or source_config["proxy_source"]

    if selected_source == "api":
        global _cached_api_proxy_batch, _cached_api_proxy_signature

        signature = _get_api_proxy_signature(source_config)
        with _proxy_assignment_lock:
            should_refresh = (
                force_refresh
                or _cached_api_proxy_batch is None
                or _cached_api_proxy_signature != signature
            )
            if should_refresh:
                _cached_api_proxy_batch = load_proxies_from_api(
                    source_config["proxy_api_url"],
                    source_config["proxy_api_timeout"],
                )
                _cached_api_proxy_signature = signature
            return list(_cached_api_proxy_batch)

    if file_path is not None:
        return load_http_proxies(file_path, proxy_source=selected_source)

    return load_http_proxies(source_config["proxy_file"], proxy_source=selected_source)


def fetch_api_proxy_assignment():
    source_config = get_proxy_source_config()
    for _ in range(4):
        proxies = load_proxies_from_api(
            source_config["proxy_api_url"],
            source_config["proxy_api_timeout"],
        )
        if not proxies:
            continue

        with _proxy_health_lock:
            healthy_proxies = [
                proxy for proxy in proxies if _get_proxy_key(proxy) not in _bad_proxy_keys
            ]

        candidate_pool = healthy_proxies or proxies
        random.shuffle(candidate_pool)

        for proxy in candidate_pool:
            if not _is_proxy_active(proxy):
                return proxy

    return None


def get_next_proxy_assignment(file_path=None, proxy_source=None):
    global _proxy_assignment_index

    source_config = get_proxy_source_config()
    selected_source = proxy_source or source_config["proxy_source"]
    
    # 无代理模式
    if selected_source == "none":
        return None
    
    # API 模式
    if selected_source == "api":
        proxy = fetch_api_proxy_assignment()
        if proxy:
            with _proxy_assignment_lock:
                _proxy_assignment_index += 1
        return proxy
    
    # 文件模式 - 从文件加载代理并轮询
    proxies = get_proxy_candidates(file_path, proxy_source=selected_source)
    if not proxies:
        return None
    
    with _proxy_assignment_lock:
        index = _proxy_assignment_index % len(proxies)
        _proxy_assignment_index += 1
    
    return proxies[index]


def test_proxy_connectivity(proxy_config, url, timeout):
    if not proxy_config:
        return False

    try:
        response = requests.get(
            url,
            proxies=build_requests_proxy(proxy_config),
            timeout=(5, timeout),
            allow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/136.0.0.0 Safari/537.36"
                )
            },
        )
        return response.ok
    except Exception:
        return False


def get_proxy_test_targets():
    data = get_config()

    urls = data.get("proxy_test_urls")
    if not urls:
        urls = [
            data.get("proxy_test_url", "https://outlook.live.com/mail/0/?prompt=create_account"),
            "https://login.live.com",
        ]

    return urls, data.get("proxy_test_timeout", 8)


def get_working_proxy(file_path=None, preferred_proxy=None, reserve=False):
    proxies = get_proxy_candidates(file_path)
    if not proxies and preferred_proxy:
        proxies = [preferred_proxy]

    if preferred_proxy:
        preferred_key = _get_proxy_key(preferred_proxy)
        ordered_proxies = [preferred_proxy]
        ordered_proxies.extend(
            proxy_config
            for proxy_config in proxies
            if _get_proxy_key(proxy_config) != preferred_key
        )
        proxies = ordered_proxies

    if not proxies:
        return None

    test_urls, timeout = get_proxy_test_targets()
    if not preferred_proxy:
        random.shuffle(proxies)

    for proxy_config in proxies:
        key = _get_proxy_key(proxy_config)
        with _proxy_health_lock:
            if key in _bad_proxy_keys:
                continue
        if _is_proxy_active(proxy_config):
            continue

        failed_url = None
        for url in test_urls:
            if not test_proxy_connectivity(proxy_config, url, timeout):
                failed_url = url
                break

        if failed_url is None:
            if reserve and not reserve_proxy(proxy_config):
                continue
            return proxy_config

        with _proxy_health_lock:
            _bad_proxy_keys.add(key)

        proxy_label = format_proxy_label(proxy_config)
        print(f"[Skip: Proxy] - 代理阶段检测失败，已跳过 {proxy_label} | failed_url={failed_url}")

    source_config = get_proxy_source_config()
    if source_config["proxy_source"] == "api" and not preferred_proxy and proxies:
        refreshed_proxies = get_proxy_candidates(proxy_source="api", force_refresh=True)
        if refreshed_proxies:
            return get_working_proxy(
                file_path=file_path,
                preferred_proxy=refreshed_proxies[0],
                reserve=reserve,
            )

    if source_config["proxy_source"] == "api" and preferred_proxy:
        for _ in range(3):
            fresh_proxy = fetch_api_proxy_assignment()
            if not fresh_proxy:
                continue
            result = get_working_proxy(
                file_path=file_path,
                preferred_proxy=fresh_proxy,
                reserve=reserve,
            )
            if result:
                return result

    return None


def reset_bad_proxies():
    global _proxy_assignment_index, _cached_api_proxy_batch, _cached_api_proxy_signature

    with _proxy_health_lock:
        _bad_proxy_keys.clear()
    with _proxy_assignment_lock:
        _proxy_assignment_index = 0
        _cached_api_proxy_batch = None
        _cached_api_proxy_signature = None
        _active_proxy_keys.clear()


def get_browser_proxy_settings(proxy_config):
    if not proxy_config:
        return None

    return {
        "server": proxy_config["server"],
        "username": proxy_config["username"],
        "password": proxy_config["password"],
        "bypass": "localhost",
    }
