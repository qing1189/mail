"""任务管理器 - 封装注册任务的执行逻辑"""
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Callable

# 添加项目根目录到 path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from config import get_config, update_config, save_config
from controllers.ruyipage_controller import RuyiPageController
from get_token import get_access_token
from utils import (
    generate_strong_password,
    get_next_proxy_assignment,
    get_proxy_source_config,
    random_email,
)
from backend.core.state import state


class TaskManager:
    """任务管理器"""

    def __init__(self):
        self._executor: Optional[ThreadPoolExecutor] = None
        self._stop_event = threading.Event()
        self._controller: Optional[RuyiPageController] = None
        self._status_callback: Optional[Callable] = None
        self._lock = threading.Lock()

    def set_status_callback(self, callback: Callable):
        """设置状态变更回调（用于 WebSocket 广播）"""
        self._status_callback = callback

    def _notify_status(self):
        """通知状态变更"""
        if self._status_callback:
            try:
                self._status_callback(state.get_status())
            except Exception:
                pass

    def _process_single_flow(self, task_id: int, assigned_proxy=None) -> dict:
        """处理单个注册任务"""
        page = None
        email = None
        try:
            # 生成邮箱
            email = random_email()
            password = generate_strong_password()
            full_email = f"{email}{self._controller.email_suffix}"
            
            print(f"[Task-{task_id}] 开始注册: {full_email}")
            
            # 获取浏览器页面
            if assigned_proxy:
                print(f"[Task-{task_id}] 使用代理: {assigned_proxy.get('server', 'unknown')}")
            
            page = self._controller.get_thread_page(assigned_proxy)
            if not page:
                print(f"[Task-{task_id}] 浏览器启动失败")
                return {"success": False, "oauth_success": False}

            print(f"[Task-{task_id}] 浏览器已启动，开始注册流程...")
            
            # 执行注册
            result = self._controller.outlook_register(page, email, password)
            
            if not result:
                print(f"[Task-{task_id}] 注册失败: {full_email}")
                return {"success": False, "oauth_success": False}
            
            print(f"[Task-{task_id}] 注册成功: {full_email}")
            
            # 如果不需要 OAuth2，直接返回
            if not self._controller.enable_oauth2:
                state.add_success(full_email)
                return {"success": True, "oauth_success": False}

            # 获取 OAuth2 Token
            print(f"[Task-{task_id}] 开始获取 OAuth2 Token...")
            config = get_config()
            client_id = config["oauth2"]["client_id"]
            token_result = get_access_token(page, email)
            
            if token_result[0]:
                refresh_token, access_token, expire_at = token_result
                results_dir = os.path.join(os.path.dirname(__file__), "../..", "Results")
                os.makedirs(results_dir, exist_ok=True)
                with open(
                    os.path.join(results_dir, "outlook_token.txt"),
                    "a",
                    encoding="utf-8",
                ) as f2:
                    f2.write(
                        f"{full_email}----{password}----"
                        f"{client_id}----{refresh_token}\n"
                    )
                print(f"[Task-{task_id}] Token 获取成功: {full_email}")
                state.add_success(full_email)
                return {"success": True, "oauth_success": True}
            else:
                print(f"[Task-{task_id}] Token 获取失败: {full_email}")
                state.add_success(full_email)
                return {"success": True, "oauth_success": False}
                
        except Exception as e:
            print(f"[Task-{task_id}] 发生错误: {str(e)}")
            return {"success": False, "oauth_success": False}
        finally:
            if page:
                try:
                    self._controller.clean_up(page, "done_browser")
                except Exception:
                    pass

    def _run_concurrent_flows(self, concurrent_flows: int, max_tasks: int):
        """并发执行任务"""
        task_counter = 0
        proxy_source = get_proxy_source_config().get("proxy_source", "file")

        state.task_status.total_tasks = max_tasks
        state.task_status.is_running = True
        state.task_status.is_stopping = False
        self._notify_status()

        print(f"[TaskManager] 启动任务: 并发={concurrent_flows}, 总数={max_tasks}, 代理模式={proxy_source}")

        with ThreadPoolExecutor(max_workers=concurrent_flows) as executor:
            self._executor = executor
            running_futures = {}

            while True:
                should_submit = task_counter < max_tasks and not self._stop_event.is_set()
                if not should_submit and not running_futures:
                    break

                # 检查完成的任务
                done_futures = [f for f in running_futures if f.done()]
                for future in done_futures:
                    task_id = running_futures.pop(future)
                    try:
                        result = future.result()
                        if result["success"]:
                            state.task_status.succeeded += 1
                            if self._controller.enable_oauth2:
                                if result["oauth_success"]:
                                    state.task_status.oauth_succeeded += 1
                                else:
                                    state.task_status.oauth_failed += 1
                        else:
                            state.task_status.failed += 1
                    except Exception as e:
                        state.task_status.failed += 1
                        print(f"[Task-{task_id}] 异常: {str(e)}")
                    self._notify_status()

                # 提交新任务
                while (
                    len(running_futures) < concurrent_flows
                    and task_counter < max_tasks
                    and not self._stop_event.is_set()
                ):
                    assigned_proxy = None
                    if proxy_source != "none":
                        assigned_proxy = get_next_proxy_assignment()
                        if proxy_source == "api" and not assigned_proxy:
                            print("[TaskManager] 等待代理...")
                            time.sleep(1.0)
                            break
                    
                    task_counter += 1
                    future = executor.submit(self._process_single_flow, task_counter, assigned_proxy)
                    running_futures[future] = task_counter
                    state.task_status.submitted = task_counter
                    self._notify_status()

                state.task_status.active_threads = len(running_futures)
                time.sleep(0.3)

            state.task_status.active_threads = 0
            self._executor = None

        state.task_status.is_running = False
        print(f"[TaskManager] 任务完成: 成功={state.task_status.succeeded}, 失败={state.task_status.failed}")
        self._notify_status()

    def start(self, config: dict) -> bool:
        """启动任务"""
        with self._lock:
            if state.task_status.is_running:
                return False

            # 重置状态
            state.task_status = type(state.task_status)()
            self._stop_event.clear()

            # 更新配置
            if config:
                update_config(config)
                save_config()

            # 启动控制器
            print("[TaskManager] 初始化浏览器控制器...")
            self._controller = RuyiPageController()

            # 启动任务线程
            concurrent_flows = config.get("concurrent_flows", 10)
            max_tasks = config.get("max_tasks", 20)

            thread = threading.Thread(
                target=self._run_concurrent_flows,
                args=(concurrent_flows, max_tasks),
                daemon=True,
            )
            thread.start()

            print("[TaskManager] 任务已启动")
            return True

    def stop(self) -> bool:
        """停止任务"""
        if not state.task_status.is_running:
            return False

        self._stop_event.set()
        state.task_status.is_stopping = True
        self._notify_status()
        print("[TaskManager] 正在停止任务...")
        return True

    def get_status(self) -> dict:
        """获取任务状态"""
        return state.get_status()

    def cleanup(self):
        """清理资源"""
        if self._controller:
            try:
                self._controller.clean_up(type="all_browser")
            except Exception:
                pass


# 全局任务管理器实例
task_manager = TaskManager()
