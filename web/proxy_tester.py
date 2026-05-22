"""库化的代理测试器,供 Web API 调用。

接口:
- test_proxies(proxies, urls, timeout, concurrency) -> list[ProxyTestResult]
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict, field
from typing import List, Optional

import requests

from utils import (
    build_requests_proxy,
    format_proxy_label,
    get_proxy_candidates,
    get_proxy_test_targets,
    parse_http_proxy_api_responses,
    parse_http_proxy_line,
)


_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/136.0.0.0 Safari/537.36"
    )
}


@dataclass
class UrlResult:
    url: str
    ok: bool
    status_code: Optional[int] = None
    elapsed: float = 0.0
    error: Optional[str] = None


@dataclass
class ProxyTestResult:
    label: str
    server: str
    ok: bool
    urls: List[UrlResult] = field(default_factory=list)
    elapsed: float = 0.0

    def to_dict(self):
        d = asdict(self)
        d["urls"] = [asdict(u) for u in self.urls]
        return d


def _test_url(proxy_config, url: str, timeout: int) -> UrlResult:
    start = time.perf_counter()
    try:
        response = requests.get(
            url,
            proxies=build_requests_proxy(proxy_config),
            timeout=(5, timeout),
            allow_redirects=True,
            headers=_HEADERS,
        )
        return UrlResult(
            url=url,
            ok=response.ok,
            status_code=response.status_code,
            elapsed=time.perf_counter() - start,
        )
    except Exception as e:
        return UrlResult(
            url=url,
            ok=False,
            elapsed=time.perf_counter() - start,
            error=str(e)[:300],
        )


def _test_one_proxy(proxy_config, urls, timeout) -> ProxyTestResult:
    start = time.perf_counter()
    url_results = []
    all_ok = True
    for url in urls:
        result = _test_url(proxy_config, url, timeout)
        url_results.append(result)
        if not result.ok:
            all_ok = False
    return ProxyTestResult(
        label=format_proxy_label(proxy_config),
        server=proxy_config["server"],
        ok=all_ok,
        urls=url_results,
        elapsed=time.perf_counter() - start,
    )


def parse_proxies_text(text: str, source: str = "file") -> List[dict]:
    """从原始文本(每行一个代理)解析代理对象。

    source: "file" | "freefile" | "api_text"
    - file: HOST:PORT:USER:PASS
    - freefile: HOST:PORT
    - api_text: HOST:PORT(同 api 响应格式)
    """
    if source == "api_text":
        return parse_http_proxy_api_responses(text)

    proxies = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        proxy = parse_http_proxy_line(line, proxy_source=source)
        if proxy:
            proxies.append(proxy)
    return proxies


def load_proxies_for_test(source: str, file_path: Optional[str], inline_text: Optional[str]) -> List[dict]:
    """根据来源加载代理:
    - "current": 用全局配置(file/freefile/api)
    - "file" / "freefile": 直接从指定文件路径
    - "inline": 用 inline_text(假定 HOST:PORT 或 HOST:PORT:USER:PASS,自动判断)
    """
    if source == "inline" and inline_text:
        # 自动判断:如果存在四段冒号格式按 file 解析,否则按 freefile
        candidates_full = parse_proxies_text(inline_text, "file")
        candidates_free = parse_proxies_text(inline_text, "freefile")
        return candidates_full or candidates_free

    if source in ("file", "freefile") and file_path:
        from utils import load_http_proxies
        return load_http_proxies(file_path, proxy_source=source)

    # current = 用全局配置
    return get_proxy_candidates()


def test_proxies(
    proxies: List[dict],
    urls: Optional[List[str]] = None,
    timeout: Optional[int] = None,
    limit: Optional[int] = None,
    concurrency: int = 5,
) -> List[ProxyTestResult]:
    if not proxies:
        return []

    test_urls, default_timeout = get_proxy_test_targets()
    actual_urls = urls or test_urls
    actual_timeout = timeout or default_timeout

    if limit and limit > 0:
        proxies = proxies[:limit]

    results: List[Optional[ProxyTestResult]] = [None] * len(proxies)
    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        future_to_index = {
            pool.submit(_test_one_proxy, proxy, actual_urls, actual_timeout): idx
            for idx, proxy in enumerate(proxies)
        }
        for future in as_completed(future_to_index):
            idx = future_to_index[future]
            try:
                results[idx] = future.result()
            except Exception as e:
                results[idx] = ProxyTestResult(
                    label=format_proxy_label(proxies[idx]),
                    server=proxies[idx]["server"],
                    ok=False,
                    urls=[UrlResult(url="-", ok=False, error=str(e)[:300])],
                )
    return [r for r in results if r is not None]
