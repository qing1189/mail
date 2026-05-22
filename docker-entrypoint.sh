#!/bin/bash
set -e

# 启动虚拟显示
Xvfb :99 -screen 0 1280x1024x24 &
export DISPLAY=:99

# 启动窗口管理器
fluxbox &

# 如果启用 VNC，则启动 VNC 服务器
if [ "${ENABLE_VNC}" = "true" ]; then
    x11vnc -display :99 -forever -nopw &
    echo "VNC server started on port 5900"
fi

# 运行主程序
exec "$@"
