import builtins
import ctypes
import math
import os
import signal
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from config import get_config, update_config, save_config
from controllers.ruyipage_controller import RuyiPageController
from get_token import get_access_token
from utils import (
    generate_strong_password,
    get_next_proxy_assignment,
    get_proxy_source_config,
    random_email,
)


BANNER_LINES = [
    r"  __  __ ____    __  __    _    ___ _       ____  _____ ____   _____ ___   ___  _   ",
    r" |  \/  / ___|  |  \/  |  / \  |_ _| |     |  _ \| ____/ ___| |_   _/ _ \ / _ \| |  ",
    r" | |\/| \___ \  | |\/| | / _ \  | || |     | |_) |  _|| |  _    | || | | | | | | |  ",
    r" | |  | |___) | | |  | |/ ___ \ | || |___  |  _ <| |__| |_| |   | || |_| | |_| | |__",
    r" |_|  |_|____/  |_|  |_/_/   \_\___|_____| |_| \_\_____\____|   |_| \___/ \___/|____|",
]

DIM = "\033[2m"
RESET = "\033[0m"
CLEAR_LINE = "\033[2K"


def enable_windows_vt():
    if sys.platform == "win32":
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_ulong()
        kernel32.GetConsoleMode(handle, ctypes.byref(mode))
        kernel32.SetConsoleMode(handle, mode.value | 0x0004)


# ── smooth flowing color ──────────────────────────────────────────────

def _status_color(pos, t):
    """Cyan-blue gradient for status bar."""
    phase = pos * 0.3 - t
    r = int(30 + 20 * math.sin(phase + 2.0))
    g = int(180 + 75 * math.sin(phase + 0.5))
    b = int(220 + 35 * math.sin(phase))
    return f"\033[38;2;{max(0,min(255,r))};{max(0,min(255,g))};{max(0,min(255,b))}m"


def _banner_color(pos, t):
    """Purple-magenta to deep-blue gradient for banner."""
    phase = pos * 0.15 - t * 0.8
    r = int(160 + 80 * math.sin(phase + 0.8))
    g = int(30 + 40 * math.sin(phase + 3.0))
    b = int(180 + 70 * math.sin(phase))
    return f"\033[38;2;{max(0,min(255,r))};{max(0,min(255,g))};{max(0,min(255,b))}m"


def _flow_text(text, t, color_fn):
    out = []
    ci = 0
    for ch in text:
        if ch == ' ':
            out.append(ch)
        else:
            out.append(f"{color_fn(ci, t)}{ch}")
            ci += 1
    out.append(RESET)
    return "".join(out)


# ── status bar ────────────────────────────────────────────────────────

_tls = threading.local()


class StatusBar:
    def __init__(self):
        self._lock = threading.Lock()
        self._active = False
        self._time = 0.0
        self.show_logs = True
        self.total_tasks = 0
        self.submitted = 0
        self.active_threads = 0
        self.succeeded = 0
        self.failed = 0
        self.oauth_succeeded = 0
        self.oauth_failed = 0
        self.enable_oauth2 = False
        self.stopping = False
        self._original_print = builtins.print
        self._original_stdout_write = None
        self._original_stderr_write = None
        self._refresh_thread = None
        self._success_messages = []
        self._max_success_lines = 0

    def _raw(self, data):
        _tls.in_raw = True
        try:
            self._original_stdout_write(data)
        finally:
            _tls.in_raw = False

    def _term_size(self):
        try:
            sz = os.get_terminal_size()
            return sz.columns, sz.lines
        except (OSError, ValueError):
            return 80, 24

    def start(self):
        self._original_stdout_write = sys.stdout.write
        self._original_stderr_write = sys.stderr.write
        self._active = True
        self._patch_print()
        self._patch_streams()
        if self.show_logs:
            w, _ = self._term_size()
            self._raw(f"\n{DIM}{'─' * w}{RESET}\n")
            self._draw_status_inline()
        else:
            self._init_quiet_screen()
        self._refresh_thread = threading.Thread(target=self._animation_loop, daemon=True)
        self._refresh_thread.start()

    def stop(self):
        self._active = False
        if self._refresh_thread:
            self._refresh_thread.join(timeout=0.5)
        self._restore_streams()
        self._restore_print()
        with self._lock:
            if self.show_logs:
                self._raw("\r" + CLEAR_LINE + "\n")
            else:
                self._raw("\033[?25h\n")

    def _patch_print(self):
        bar = self

        def patched_print(*args, **kwargs):
            file = kwargs.get("file", None)
            if file is not None and file is not sys.stdout and file is not sys.stderr:
                bar._original_print(*args, **kwargs)
                return
            end = kwargs.get("end", "\n")
            sep = kwargs.get("sep", " ")
            msg = sep.join(str(a) for a in args) + end
            bar.log(msg)

        builtins.print = patched_print

    def _restore_print(self):
        builtins.print = self._original_print

    def _patch_streams(self):
        bar = self

        def make_patched(original_write):
            def patched_write(data):
                if getattr(_tls, 'in_raw', False) or not bar._active or not data:
                    return original_write(data)
                bar.log(data)
                return len(data)
            return patched_write

        sys.stdout.write = make_patched(self._original_stdout_write)
        sys.stderr.write = make_patched(self._original_stderr_write)

    def _restore_streams(self):
        if self._original_stdout_write:
            sys.stdout.write = self._original_stdout_write
        if self._original_stderr_write:
            sys.stderr.write = self._original_stderr_write

    def log(self, msg):
        if not self._active:
            self._original_print(msg, end="" if msg.endswith("\n") else "\n")
            return
        if self.show_logs:
            with self._lock:
                self._raw("\r" + CLEAR_LINE)
                self._raw(msg)
                if not msg.endswith("\n"):
                    self._raw("\n")
                self._draw_status_inline()
        else:
            if "[Success" not in msg:
                return
            with self._lock:
                line = msg.rstrip("\n")
                self._success_messages.append(line)
                if len(self._success_messages) > self._max_success_lines:
                    self._success_messages = self._success_messages[-self._max_success_lines:]
                self._redraw_quiet_screen()

    def refresh(self):
        if not self._active:
            return
        with self._lock:
            if self.show_logs:
                self._draw_status_inline()
            else:
                self._redraw_quiet_screen()

    def _animation_loop(self):
        while self._active:
            time.sleep(0.05)
            self._time += 0.15
            self.refresh()

    # ── log mode (Y) ──────────────────────────────────────────────────

    def _draw_status_inline(self):
        line = self._build_status_line()
        self._raw("\r" + CLEAR_LINE + " " + line)

    # ── quiet mode (N) ────────────────────────────────────────────────

    def _init_quiet_screen(self):
        cols, lines = self._term_size()
        self._max_success_lines = max(1, lines - len(BANNER_LINES) - 5)
        self._raw("\033[?25l")
        self._raw("\033[2J\033[H")
        self._redraw_quiet_screen()

    def _redraw_quiet_screen(self):
        cols, lines = self._term_size()
        self._max_success_lines = max(1, lines - len(BANNER_LINES) - 5)

        out = ["\033[H\033[J"]
        for i, raw_line in enumerate(BANNER_LINES):
            colored = _flow_text(raw_line, self._time + i * 0.6, _banner_color)
            out.append(colored + "\n")

        out.append(DIM + "─" * cols + RESET + "\n")

        green = "\033[38;2;120;230;160m"
        for line in self._success_messages[-self._max_success_lines:]:
            out.append(green + line + RESET + "\n")

        out.append(f"\033[{lines};1H")
        out.append("\033[2K " + self._build_status_line())

        self._raw("".join(out))

    # ── status line builder ───────────────────────────────────────────

    def _build_status_line(self):
        remaining = max(0, self.total_tasks - self.submitted)
        total_done = self.succeeded + self.failed
        rate = (self.succeeded / total_done * 100) if total_done > 0 else 0.0

        parts = [
            f"总任务: {self.total_tasks}",
            f"剩余: {remaining}",
            f"运行中: {self.active_threads}",
            f"成功: {self.succeeded}",
            f"失败: {self.failed}",
            f"成功率: {rate:.1f}%",
        ]
        if self.enable_oauth2:
            parts.append(f"授权成功: {self.oauth_succeeded}")
            parts.append(f"授权失败: {self.oauth_failed}")
        if self.stopping:
            parts.append("[正在停止...]")

        plain = "  │  ".join(parts)
        return _flow_text(plain, self._time, _status_color)


status_bar = StatusBar()
stop_event = threading.Event()
_signal_count = 0


def signal_handler(sig, frame):
    global _signal_count
    _signal_count += 1
    if _signal_count == 1:
        stop_event.set()
        status_bar.stopping = True
        status_bar.refresh()
    else:
        status_bar.stop()
        sys.stdout.write("\n[Warn] - 再次收到中断信号，强制退出\n")
        os._exit(1)


# ── interactive prompts ───────────────────────────────────────────────


def prompt_choice(prompt, choices, default=None):
    while True:
        suffix = f" (默认: {default})" if default else ""
        raw = input(f"{prompt}{suffix}: ").strip()
        if not raw and default is not None:
            return default
        if raw in choices:
            return raw
        print(f"  无效输入，请输入 {'/'.join(choices)}")


def prompt_int(prompt, default, min_value=1):
    while True:
        raw = input(f"{prompt} (默认: {default}): ").strip()
        if not raw:
            return default
        try:
            value = int(raw)
            if value < min_value:
                print(f"  数值必须 >= {min_value}")
                continue
            return value
        except ValueError:
            print("  请输入整数")


def prompt_yes_no(prompt, default=True):
    default_str = "y" if default else "n"
    while True:
        raw = input(f"{prompt} (y/n, 默认: {default_str}): ").strip().lower()
        if not raw:
            return default
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        print("  请输入 y 或 n")


def prompt_str(prompt, default=""):
    display = default if default else "无"
    raw = input(f"{prompt} (默认: {display}): ").strip()
    if not raw:
        return default
    return raw


def collect_user_inputs():
    cfg = get_config()
    oauth2_cfg = cfg.get("oauth2", {})

    print("\n================================================================================\n")
    for line in BANNER_LINES:
        print(line)
    print("\n================================================================================\n")
    print("  欢迎使用 MS MAIL REG TOOL，请按提示输入配置参数：")
    print("  （直接回车使用上次保存的值）\n")

    # [1] 邮箱后缀
    print("  [1] 邮箱后缀:")
    print("      1. @outlook.com")
    print("      2. @hotmail.com")
    saved_suffix = cfg.get("email_suffix", "@outlook.com")
    default_suffix_choice = "2" if saved_suffix == "@hotmail.com" else "1"
    suffix_choice = prompt_choice("      请选择", ["1", "2"], default=default_suffix_choice)
    email_suffix = "@outlook.com" if suffix_choice == "1" else "@hotmail.com"
    print(f"      -> {email_suffix}\n")

    # [2] 代理来源
    print("  [2] 代理来源:")
    print("      1. file (从文件读取 HOST:PORT:USER:PASS)")
    print("      2. freefile (从文件读取 HOST:PORT)")
    print("      3. api (从 API 获取)")
    source_map = {"file": "1", "freefile": "2", "api": "3"}
    default_proxy_choice = source_map.get(cfg.get("proxy_source", "api"), "3")
    proxy_choice = prompt_choice("      请选择", ["1", "2", "3"], default=default_proxy_choice)
    proxy_source_map = {"1": "file", "2": "freefile", "3": "api"}
    proxy_source = proxy_source_map[proxy_choice]
    print(f"      -> {proxy_source}\n")

    # [3] 代理文件 / API 地址
    proxy_file = cfg.get("proxy_file", "proxies.txt")
    proxy_api_url = cfg.get("proxy_api_url", "")
    if proxy_source in ("file", "freefile"):
        print("  [3] 代理文件路径:")
        proxy_file = prompt_str("      请输入", default=proxy_file)
        print(f"      -> {proxy_file}\n")
    else:
        print("  [3] 代理 API 地址:")
        proxy_api_url = prompt_str("      请输入", default=proxy_api_url)
        print(f"      -> {proxy_api_url}\n")

    # [4] 并发线程数
    print("  [4] 并发线程数:")
    concurrent_flows = prompt_int("      请输入", default=cfg.get("concurrent_flows", 10))
    print(f"      -> {concurrent_flows}\n")

    # [5] 最大任务数
    print("  [5] 最大任务数:")
    max_tasks = prompt_int("      请输入", default=cfg.get("max_tasks", 20))
    print(f"      -> {max_tasks}\n")

    # [6] OAuth2
    print("  [6] 注册成功后是否授权 OAuth2 获取 Token:")
    print("      Y = 授权（需填写 Client ID 和 Redirect URL）")
    print("      N = 不授权，注册成功后直接保存账号密码")
    enable_oauth2 = prompt_yes_no("      请选择", default=oauth2_cfg.get("enable_oauth2", False))
    print(f"      -> {'授权' if enable_oauth2 else '不授权'}\n")

    client_id = oauth2_cfg.get("client_id", "")
    redirect_url = oauth2_cfg.get("redirect_url", "http://localhost:8000")
    if enable_oauth2:
        print("  [6a] OAuth2 Client ID:")
        client_id = prompt_str("       请输入", default=client_id)
        print(f"       -> {client_id}\n")

        print("  [6b] OAuth2 Redirect URL:")
        redirect_url = prompt_str("       请输入", default=redirect_url)
        print(f"       -> {redirect_url}\n")

    # [7] 显示日志
    print("  [7] 是否显示日志:")
    print("      Y = 显示全部日志")
    print("      N = 仅显示注册成功信息（带流光 Banner）")
    show_logs = prompt_yes_no("      请选择", default=True)
    print(f"      -> {'显示全部日志' if show_logs else '仅显示成功信息'}\n")

    return {
        "email_suffix": email_suffix,
        "proxy_source": proxy_source,
        "proxy_file": proxy_file,
        "proxy_api_url": proxy_api_url,
        "concurrent_flows": concurrent_flows,
        "max_tasks": max_tasks,
        "enable_oauth2": enable_oauth2,
        "client_id": client_id,
        "redirect_url": redirect_url,
        "show_logs": show_logs,
    }


def apply_user_inputs_to_config(user_inputs):
    config = get_config()
    config["email_suffix"] = user_inputs["email_suffix"]
    config["proxy_source"] = user_inputs["proxy_source"]
    config["proxy_file"] = user_inputs["proxy_file"]
    config["proxy_api_url"] = user_inputs["proxy_api_url"]
    config["concurrent_flows"] = user_inputs["concurrent_flows"]
    config["max_tasks"] = user_inputs["max_tasks"]

    oauth2_config = dict(config.get("oauth2", {}))
    oauth2_config["enable_oauth2"] = user_inputs["enable_oauth2"]
    oauth2_config["client_id"] = user_inputs["client_id"]
    oauth2_config["redirect_url"] = user_inputs["redirect_url"]
    config["oauth2"] = oauth2_config

    update_config(config)
    save_config()


# ── task runner ────────────────────────────────────────────────────────


def process_single_flow(controller, assigned_proxy=None):
    page = None
    try:
        page = controller.get_thread_page(assigned_proxy)
        if not page:
            return {"success": False, "oauth_success": False}

        email = random_email()
        password = generate_strong_password()

        result = controller.outlook_register(page, email, password)
        if result and not controller.enable_oauth2:
            return {"success": True, "oauth_success": False}
        if not result:
            return {"success": False, "oauth_success": False}

        config = get_config()
        client_id = config["oauth2"]["client_id"]
        token_result = get_access_token(page, email)
        if token_result[0]:
            refresh_token, access_token, expire_at = token_result
            with open(
                os.path.join(os.path.dirname(__file__), "Results", "outlook_token.txt"),
                "a",
                encoding="utf-8",
            ) as f2:
                f2.write(
                    f"{email}{controller.email_suffix}----{password}----"
                    f"{client_id}----{refresh_token}\n"
                )
            print(f"[Success: TokenAuth] - {email}{controller.email_suffix}")
            return {"success": True, "oauth_success": True}
        else:
            return {"success": True, "oauth_success": False}
    except Exception as e:
        print(e)
        return {"success": False, "oauth_success": False}
    finally:
        controller.clean_up(page, "done_browser")


def run_concurrent_flows(controller, concurrent_flows=10, max_tasks=100):
    task_counter = 0
    proxy_source = get_proxy_source_config().get("proxy_source", "file")

    status_bar.total_tasks = max_tasks
    status_bar.enable_oauth2 = controller.enable_oauth2

    with ThreadPoolExecutor(max_workers=concurrent_flows) as executor:
        running_futures = set()

        while True:
            should_submit = task_counter < max_tasks and not stop_event.is_set()
            if not should_submit and not running_futures:
                break

            done_futures = {f for f in running_futures if f.done()}
            for future in done_futures:
                try:
                    result = future.result()
                    if result["success"]:
                        status_bar.succeeded += 1
                        if controller.enable_oauth2:
                            if result["oauth_success"]:
                                status_bar.oauth_succeeded += 1
                            else:
                                status_bar.oauth_failed += 1
                    else:
                        status_bar.failed += 1
                except Exception as e:
                    status_bar.failed += 1
                    print(e)
                running_futures.remove(future)

            while (
                len(running_futures) < concurrent_flows
                and task_counter < max_tasks
                and not stop_event.is_set()
            ):
                assigned_proxy = get_next_proxy_assignment()
                if proxy_source == "api" and not assigned_proxy:
                    time.sleep(1.0)
                    break
                future = executor.submit(process_single_flow, controller, assigned_proxy)
                running_futures.add(future)
                task_counter += 1
                status_bar.submitted = task_counter

            status_bar.active_threads = len(running_futures)
            time.sleep(0.3)

    status_bar.active_threads = 0


# ── entry point ────────────────────────────────────────────────────────

if __name__ == "__main__":
    enable_windows_vt()

    user_inputs = collect_user_inputs()
    apply_user_inputs_to_config(user_inputs)

    config = get_config()
    if config.get("choose_browser", "ruyipage") != "ruyipage":
        raise SystemExit("当前版本仅支持 ruyipage，请将 choose_browser 设置为 ruyipage。")

    signal.signal(signal.SIGINT, signal_handler)

    os.makedirs("Results", exist_ok=True)
    controller = RuyiPageController()

    status_bar.show_logs = user_inputs["show_logs"]

    if user_inputs["show_logs"]:
        print("\n  [Info] - 开始执行任务（按 Ctrl+C 优雅停止）\n")
    status_bar.start()

    try:
        run_concurrent_flows(
            controller,
            user_inputs["concurrent_flows"],
            user_inputs["max_tasks"],
        )
    finally:
        controller.clean_up(type="all_browser")
        status_bar.stop()
        if stop_event.is_set():
            print("[Info] - 所有存活线程已完成，程序停止。")
        print(
            f"[Result] - 总计提交 {status_bar.submitted}, "
            f"成功 {status_bar.succeeded}, 失败 {status_bar.failed}"
        )
        if controller.enable_oauth2:
            print(
                f"[Result: TokenAuth] - OAuth2 授权成功 {status_bar.oauth_succeeded}, "
                f"授权失败 {status_bar.oauth_failed}"
            )
