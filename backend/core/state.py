"""全局状态管理"""
import threading
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TaskStatus:
    """任务状态"""
    total_tasks: int = 0
    submitted: int = 0
    succeeded: int = 0
    failed: int = 0
    active_threads: int = 0
    oauth_succeeded: int = 0
    oauth_failed: int = 0
    is_running: bool = False
    is_stopping: bool = False
    start_time: Optional[float] = None

    @property
    def remaining(self) -> int:
        return max(0, self.total_tasks - self.submitted)

    @property
    def success_rate(self) -> float:
        total_done = self.succeeded + self.failed
        return (self.succeeded / total_done * 100) if total_done > 0 else 0.0

    def to_dict(self) -> dict:
        return {
            "total_tasks": self.total_tasks,
            "submitted": self.submitted,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "remaining": self.remaining,
            "active_threads": self.active_threads,
            "success_rate": round(self.success_rate, 1),
            "oauth_succeeded": self.oauth_succeeded,
            "oauth_failed": self.oauth_failed,
            "is_running": self.is_running,
            "is_stopping": self.is_stopping,
        }


class GlobalState:
    """全局状态单例"""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init_state()
        return cls._instance

    def _init_state(self):
        self.task_status = TaskStatus()
        self.logs: list[str] = []
        self.success_emails: list[str] = []
        self._max_logs = 500
        self._max_success = 200

    def add_log(self, message: str):
        with self._lock:
            self.logs.append(message)
            if len(self.logs) > self._max_logs:
                self.logs = self.logs[-self._max_logs:]

    def add_success(self, email: str):
        with self._lock:
            self.success_emails.append(email)
            if len(self.success_emails) > self._max_success:
                self.success_emails = self.success_emails[-self._max_success:]

    def get_status(self) -> dict:
        return self.task_status.to_dict()

    def get_logs(self, limit: int = 100) -> list[str]:
        with self._lock:
            return self.logs[-limit:]

    def get_success_emails(self, limit: int = 100) -> list[str]:
        with self._lock:
            return self.success_emails[-limit:]

    def reset(self):
        with self._lock:
            self.task_status = TaskStatus()
            self.logs.clear()
            self.success_emails.clear()


# 全局状态实例
state = GlobalState()
