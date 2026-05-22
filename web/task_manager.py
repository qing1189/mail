"""多批次任务调度器。

行为:
- 用户通过 enqueue_batch() 提交批次,带上 concurrent_flows / max_tasks 等运行时参数
- 同一时刻只跑一个批次。当前批次完成后才会取下一个
- 支持 cancel(batch_id):排队中的直接移除;运行中的发停止信号(等线程跑完)
- 通过 LogBus + on_state_change 回调向前端推送实时统计
"""

import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, asdict, field
from typing import Callable, Dict, List, Optional

from config import get_config
from utils import get_next_proxy_assignment, get_proxy_source_config

from .log_bus import log_bus


@dataclass
class BatchStats:
    total: int = 0
    submitted: int = 0
    active: int = 0
    succeeded: int = 0
    failed: int = 0
    oauth_succeeded: int = 0
    oauth_failed: int = 0


@dataclass
class Batch:
    id: str
    label: str
    status: str  # queued | running | stopping | completed | cancelled | failed
    config_snapshot: dict
    stats: BatchStats = field(default_factory=BatchStats)
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    error: Optional[str] = None

    def to_dict(self):
        d = asdict(self)
        # 不把完整 config_snapshot 全发送,只发关键字段
        snap = self.config_snapshot or {}
        d["config_summary"] = {
            "concurrent_flows": snap.get("concurrent_flows"),
            "max_tasks": snap.get("max_tasks"),
            "email_suffix": snap.get("email_suffix"),
            "proxy_source": snap.get("proxy_source"),
            "enable_oauth2": snap.get("oauth2", {}).get("enable_oauth2"),
        }
        return d


StateCallback = Callable[[str, dict], None]


class TaskManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._queue: List[Batch] = []
        self._batches: Dict[str, Batch] = {}
        self._current: Optional[Batch] = None
        self._stop_current = threading.Event()
        self._scheduler_thread: Optional[threading.Thread] = None
        self._scheduler_started = False
        self._wake = threading.Event()
        self._on_state: List[StateCallback] = []
        # 持有 controller 实例,确保 cancel 时能强制清理浏览器
        self._controller = None

    # ── public API ────────────────────────────────────────────────────

    def start_scheduler(self):
        with self._lock:
            if self._scheduler_started:
                return
            self._scheduler_started = True
            self._scheduler_thread = threading.Thread(
                target=self._scheduler_loop, name="batch-scheduler", daemon=True
            )
            self._scheduler_thread.start()

    def add_state_listener(self, cb: StateCallback):
        self._on_state.append(cb)

    def list_batches(self) -> List[dict]:
        with self._lock:
            ordered = list(self._batches.values())
        ordered.sort(key=lambda b: b.created_at, reverse=True)
        return [b.to_dict() for b in ordered]

    def get_batch(self, batch_id: str) -> Optional[dict]:
        with self._lock:
            batch = self._batches.get(batch_id)
        return batch.to_dict() if batch else None

    def enqueue_batch(self, label: str, overrides: Optional[dict] = None) -> dict:
        """创建一个批次。overrides 仅可覆盖运行时字段:
        concurrent_flows, max_tasks, email_suffix, proxy_source。
        """
        snapshot = self._build_snapshot(overrides or {})
        batch = Batch(
            id=f"batch-{int(time.time() * 1000)}-{uuid.uuid4().hex[:6]}",
            label=label or f"批次 #{len(self._batches) + 1}",
            status="queued",
            config_snapshot=snapshot,
            stats=BatchStats(total=int(snapshot.get("max_tasks", 0))),
        )
        with self._lock:
            self._batches[batch.id] = batch
            self._queue.append(batch)
        self._notify("batch_added", batch)
        self._wake.set()
        return batch.to_dict()

    def cancel_batch(self, batch_id: str) -> dict:
        with self._lock:
            batch = self._batches.get(batch_id)
            if not batch:
                return {"ok": False, "reason": "not_found"}

            if batch.status == "queued":
                self._queue = [b for b in self._queue if b.id != batch_id]
                batch.status = "cancelled"
                batch.finished_at = time.time()
                self._notify("batch_updated", batch)
                return {"ok": True, "reason": "removed_from_queue"}

            if batch.status == "running":
                batch.status = "stopping"
                self._stop_current.set()
                self._notify("batch_updated", batch)
                return {"ok": True, "reason": "stop_signal_sent"}

            return {"ok": False, "reason": f"cannot_cancel_in_state:{batch.status}"}

    def force_stop_all(self):
        with self._lock:
            for batch in list(self._queue):
                batch.status = "cancelled"
                batch.finished_at = time.time()
                self._notify("batch_updated", batch)
            self._queue.clear()
            if self._current:
                self._current.status = "stopping"
                self._stop_current.set()
                self._notify("batch_updated", self._current)

    # ── snapshot ──────────────────────────────────────────────────────

    def _build_snapshot(self, overrides: dict) -> dict:
        cfg = get_config()
        # 浅拷贝
        snap = dict(cfg)
        snap["oauth2"] = dict(cfg.get("oauth2", {}))
        snap["ruyipage"] = dict(cfg.get("ruyipage", {}))

        allowed = (
            "concurrent_flows",
            "max_tasks",
            "email_suffix",
            "proxy_source",
        )
        for key in allowed:
            if key in overrides and overrides[key] is not None:
                snap[key] = overrides[key]
        return snap

    # ── scheduler ─────────────────────────────────────────────────────

    def _scheduler_loop(self):
        while True:
            self._wake.wait(timeout=1.0)
            self._wake.clear()

            with self._lock:
                batch = None
                while self._queue:
                    candidate = self._queue.pop(0)
                    if candidate.status == "queued":
                        batch = candidate
                        break

            if not batch:
                continue

            self._run_batch(batch)

    def _run_batch(self, batch: Batch):
        with self._lock:
            self._current = batch
            self._stop_current.clear()
            batch.status = "running"
            batch.started_at = time.time()
        log_bus.set_current_batch(batch.id)
        self._notify("batch_updated", batch)
        log_bus.emit("info", f"[Info] - 批次 {batch.label} 开始执行 (id={batch.id})")

        try:
            self._run_batch_flows(batch)
            with self._lock:
                if batch.status == "stopping":
                    batch.status = "cancelled"
                else:
                    batch.status = "completed"
        except Exception as e:
            log_bus.emit("error", f"[Error: Batch] - 批次执行异常: {e}")
            with self._lock:
                batch.status = "failed"
                batch.error = str(e)
        finally:
            with self._lock:
                batch.finished_at = time.time()
                self._current = None
            log_bus.set_current_batch(None)
            self._notify("batch_updated", batch)
            log_bus.emit(
                "info",
                f"[Info] - 批次 {batch.label} 结束: status={batch.status}, "
                f"成功 {batch.stats.succeeded}, 失败 {batch.stats.failed}",
            )

    def _ensure_controller(self):
        if self._controller is not None:
            return self._controller
        # 只在跑批次时才 import,避免 web server 启动时强依赖 ruyipage
        from controllers.ruyipage_controller import RuyiPageController

        self._controller = RuyiPageController()
        return self._controller

    def _run_batch_flows(self, batch: Batch):
        snapshot = batch.config_snapshot
        concurrent_flows = max(1, int(snapshot.get("concurrent_flows", 1)))
        max_tasks = max(1, int(snapshot.get("max_tasks", 1)))

        # 该批次执行期间,把全局 config 临时改成 snapshot 的关键字段,
        # 让 base_controller / utils 看到的是该批次的设置。
        from config import get_config as _get_config

        original_cfg = _get_config()
        backup = {
            "email_suffix": original_cfg.get("email_suffix"),
            "proxy_source": original_cfg.get("proxy_source"),
            "concurrent_flows": original_cfg.get("concurrent_flows"),
            "max_tasks": original_cfg.get("max_tasks"),
        }
        original_cfg["email_suffix"] = snapshot["email_suffix"]
        original_cfg["proxy_source"] = snapshot["proxy_source"]
        original_cfg["concurrent_flows"] = concurrent_flows
        original_cfg["max_tasks"] = max_tasks

        try:
            controller = self._ensure_controller()
            # 重新读取关键字段
            controller.email_suffix = snapshot["email_suffix"]
            controller.enable_oauth2 = snapshot.get("oauth2", {}).get("enable_oauth2", False)

            os.makedirs(
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Results"),
                exist_ok=True,
            )

            self._run_concurrent_flows(controller, batch, concurrent_flows, max_tasks)

            # 批次结束:清理本批次启动的浏览器
            controller.clean_up(type="all_browser")
        finally:
            # 还原全局 config
            for key, value in backup.items():
                if value is not None:
                    original_cfg[key] = value

    def _run_concurrent_flows(
        self, controller, batch: Batch, concurrent_flows: int, max_tasks: int
    ):
        from .flow_runner import process_single_flow

        proxy_source = get_proxy_source_config().get("proxy_source", "file")
        batch.stats.total = max_tasks

        task_counter = 0
        last_emit = 0.0

        def maybe_emit_stats():
            nonlocal last_emit
            now = time.time()
            if now - last_emit > 0.5:
                last_emit = now
                self._notify("batch_updated", batch)

        with ThreadPoolExecutor(max_workers=concurrent_flows) as executor:
            running_futures = set()

            while True:
                should_submit = task_counter < max_tasks and not self._stop_current.is_set()
                if not should_submit and not running_futures:
                    break

                done_futures = {f for f in running_futures if f.done()}
                for future in done_futures:
                    try:
                        result = future.result()
                        if result["success"]:
                            batch.stats.succeeded += 1
                            if controller.enable_oauth2:
                                if result["oauth_success"]:
                                    batch.stats.oauth_succeeded += 1
                                else:
                                    batch.stats.oauth_failed += 1
                        else:
                            batch.stats.failed += 1
                    except Exception as e:
                        batch.stats.failed += 1
                        log_bus.emit("error", f"[Error: Flow] - {e}")
                    running_futures.discard(future)

                while (
                    len(running_futures) < concurrent_flows
                    and task_counter < max_tasks
                    and not self._stop_current.is_set()
                ):
                    assigned_proxy = get_next_proxy_assignment()
                    if proxy_source == "api" and not assigned_proxy:
                        time.sleep(1.0)
                        break
                    future = executor.submit(process_single_flow, controller, assigned_proxy)
                    running_futures.add(future)
                    task_counter += 1
                    batch.stats.submitted = task_counter

                batch.stats.active = len(running_futures)
                maybe_emit_stats()
                time.sleep(0.3)

        batch.stats.active = 0
        self._notify("batch_updated", batch)

    # ── notify ────────────────────────────────────────────────────────

    def _notify(self, event: str, batch: Batch):
        payload = batch.to_dict()
        # 通过 log_bus 推送给所有 WebSocket 订阅者
        log_bus.emit_event(event, payload)
        for cb in self._on_state:
            try:
                cb(event, payload)
            except Exception as e:
                log_bus.emit("warn", f"[Warn: Notify] - {e}")


task_manager = TaskManager()
