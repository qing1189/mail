"""日志捕获器 - 拦截 print 输出并推送到前端"""
import sys
import asyncio
from typing import Callable, Optional


class LogCapture:
    """日志捕获器"""
    
    def __init__(self):
        self._original_stdout = sys.stdout
        self._original_stderr = sys.stderr
        self._callback: Optional[Callable] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._capturing = False
    
    def set_callback(self, callback: Callable):
        """设置日志回调函数"""
        self._callback = callback
    
    def set_event_loop(self, loop: asyncio.AbstractEventLoop):
        """设置事件循环"""
        self._loop = loop
    
    def start(self):
        """开始捕获"""
        if self._capturing:
            return
        self._capturing = True
        sys.stdout = self._create_proxy(self._original_stdout)
        sys.stderr = self._create_proxy(self._original_stderr)
    
    def stop(self):
        """停止捕获"""
        self._capturing = False
        sys.stdout = self._original_stdout
        sys.stderr = self._original_stderr
    
    def _create_proxy(self, original):
        """创建输出代理"""
        return StreamProxy(original, self)
    
    def _on_write(self, text: str, original):
        """写入时的回调"""
        # 写入原始输出
        original.write(text)
        original.flush()
        
        # 如果有回调，发送到前端
        if self._callback and text.strip():
            try:
                self._callback(text.strip())
            except Exception:
                pass


class StreamProxy:
    """流代理"""
    
    def __init__(self, original, capture: LogCapture):
        self._original = original
        self._capture = capture
    
    def write(self, text):
        if isinstance(text, str):
            self._capture._on_write(text, self._original)
        else:
            self._original.write(text)
            self._original.flush()
    
    def flush(self):
        self._original.flush()
    
    def __getattr__(self, name):
        return getattr(self._original, name)


# 全局日志捕获器
log_capture = LogCapture()
