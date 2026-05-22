"""事件总线 + 日志拦截。

设计:
- LogBus 同时承担「日志拦截」和「事件广播」两个职责
- 任意线程都可以 emit 日志或自定义事件
- 协程通过 subscribe() 拿到一个 asyncio.Queue,从中读取 dict 形式的事件
"""

import asyncio
import builtins
import re
import sys
import threading
import time
from collections import deque
from typing import Any, Optional


_TAG_PATTERN = re.compile(r"^\s*\[(?P<tag>[^\]]+)\]")


def _classify_level(message: str) -> str:
    match = _TAG_PATTERN.match(message)
    if not match:
        return "info"
    tag = match.group("tag").strip().lower()
    if tag.startswith("error"):
        return "error"
    if tag.startswith("warn"):
        return "warn"
    if tag.startswith("success"):
        return "success"
    if tag.startswith("debug"):
        return "debug"
    if tag.startswith("skip"):
        return "warn"
    if tag.startswith("result"):
        return "success"
    return "info"


class LogBus:
    """跨线程的事件总线。

    事件统一格式:{"type": str, "data": dict}
    """

    def __init__(self, history_limit: int = 500):
        self._history: "deque[dict]" = deque(maxlen=history_limit)
        self._history_lock = threading.Lock()
        self._subscribers: "set[asyncio.Queue]" = set()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_lock = threading.Lock()
        self._patched = False
        self._original_print = None
        self._original_stdout_write = None
        self._original_stderr_write = None
        self._tls = threading.local()
        self._current_batch_id: Optional[str] = None

    # ── lifecycle ─────────────────────────────────────────────────────

    def attach_loop(self, loop: asyncio.AbstractEventLoop):
        with self._loop_lock:
            self._loop = loop

    def patch_streams(self):
        if self._patched:
            return
        self._original_print = builtins.print
        self._original_stdout_write = sys.stdout.write
        self._original_stderr_write = sys.stderr.write

        bus = self

        def patched_print(*args, **kwargs):
            file = kwargs.get("file", None)
            if file is not None and file is not sys.stdout and file is not sys.stderr:
                bus._original_print(*args, **kwargs)
                return
            sep = kwargs.get("sep", " ")
            end = kwargs.get("end", "\n")
            msg = sep.join(str(a) for a in args) + end
            bus._handle_text(msg, prefer_stderr=(file is sys.stderr))

        def make_patched_write(original_write, is_stderr):
            def patched_write(data):
                if getattr(bus._tls, "in_raw", False) or not data:
                    return original_write(data)
                bus._handle_text(data, prefer_stderr=is_stderr)
                return len(data)
            return patched_write

        builtins.print = patched_print
        sys.stdout.write = make_patched_write(self._original_stdout_write, False)
        sys.stderr.write = make_patched_write(self._original_stderr_write, True)
        self._patched = True

    def unpatch_streams(self):
        if not self._patched:
            return
        builtins.print = self._original_print
        sys.stdout.write = self._original_stdout_write
        sys.stderr.write = self._original_stderr_write
        self._patched = False

    # ── batch correlation ────────────────────────────────────────────

    def set_current_batch(self, batch_id: Optional[str]):
        self._current_batch_id = batch_id

    # ── log emission ──────────────────────────────────────────────────

    def _handle_text(self, text: str, prefer_stderr: bool = False):
        # 把原文回写到真实 stdout/stderr,容器/CLI 端依旧能看见
        try:
            self._tls.in_raw = True
            (self._original_stderr_write if prefer_stderr else self._original_stdout_write)(text)
        finally:
            self._tls.in_raw = False

        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            level = (
                "error"
                if prefer_stderr and not _TAG_PATTERN.match(stripped)
                else _classify_level(stripped)
            )
            self.emit(level, stripped)

    def emit(self, level: str, message: str, batch_id: Optional[str] = None):
        entry = {
            "ts": time.time(),
            "level": level,
            "message": message,
            "batch_id": batch_id or self._current_batch_id,
        }
        with self._history_lock:
            self._history.append({"type": "log", "data": entry})
        self._publish({"type": "log", "data": entry})

    def emit_event(self, event_type: str, data: Any):
        """推送任意自定义事件(例如批次状态)。"""
        envelope = {"type": event_type, "data": data}
        # 自定义事件不进 history(避免和日志混在一起)
        self._publish(envelope)

    # ── pub/sub ───────────────────────────────────────────────────────

    def _publish(self, envelope: dict):
        loop = self._loop
        if loop is None:
            return
        try:
            loop.call_soon_threadsafe(self._dispatch, envelope)
        except RuntimeError:
            pass

    def _dispatch(self, envelope: dict):
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(envelope)
            except asyncio.QueueFull:
                pass

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue):
        self._subscribers.discard(queue)

    def history(self, limit: int = 200):
        with self._history_lock:
            items = list(self._history)
        if limit and len(items) > limit:
            items = items[-limit:]
        return items


log_bus = LogBus()
