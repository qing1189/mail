#!/bin/sh
# 容器启动钩子:
# 1) 在 $MAIL_DATA_DIR (默认 /data) 下准备好 config.json / proxies.txt /
#    Results/ / Profiles/
# 2) 软链到 /app 下,让 Python 代码 不感知 数据目录
# 3) 默认 config.json 的初值由 .env 里的 DEFAULT_* 变量控制
# 4) exec 用户指定的 CMD (默认 web_main.py;CLI 模式则是 main.py)
set -e

DATA_DIR="${MAIL_DATA_DIR:-/data}"
mkdir -p "$DATA_DIR/Results" "$DATA_DIR/Profiles"

# ── 默认 config.json ──────────────────────────────────────────
# 仅当 文件不存在或为空 时才写入默认值。
# 之后用户在 Web 控制台里修改保存的设置,本脚本不会覆盖。
if [ ! -s "$DATA_DIR/config.json" ]; then
    DEFAULT_HEADLESS="${DEFAULT_HEADLESS:-true}"
    DEFAULT_BROWSER_PATH="${DEFAULT_BROWSER_PATH:-/usr/bin/firefox-esr}"
    DEFAULT_PROFILE_ROOT="${DEFAULT_PROFILE_ROOT:-Profiles}"
    WEB_PORT="${WEB_PORT:-8787}"

    # heredoc 不带引号,允许变量展开
    cat > "$DATA_DIR/config.json" <<EOF
{
    "ruyipage": {
        "headless": ${DEFAULT_HEADLESS},
        "browser_path": "${DEFAULT_BROWSER_PATH}",
        "profile_root": "${DEFAULT_PROFILE_ROOT}"
    },
    "web": {
        "host": "0.0.0.0",
        "port": ${WEB_PORT}
    }
}
EOF
    echo "[entrypoint] 已生成默认 $DATA_DIR/config.json"
    echo "[entrypoint]   - headless=${DEFAULT_HEADLESS}"
    echo "[entrypoint]   - browser_path=${DEFAULT_BROWSER_PATH}"
    echo "[entrypoint]   - web.port=${WEB_PORT}"
fi

# 空的 proxies.txt 占位,避免 file 模式找不到文件
[ -e "$DATA_DIR/proxies.txt" ] || touch "$DATA_DIR/proxies.txt"

# ── 软链到 /app ───────────────────────────────────────────────
# 删掉镜像里可能残留的同名文件/目录,再建 symlink
for name in config.json proxies.txt; do
    target="/app/$name"
    if [ -e "$target" ] && [ ! -L "$target" ]; then
        rm -f "$target"
    fi
    ln -sfn "$DATA_DIR/$name" "$target"
done

for name in Results Profiles; do
    target="/app/$name"
    if [ -e "$target" ] && [ ! -L "$target" ]; then
        rm -rf "$target"
    fi
    ln -sfn "$DATA_DIR/$name" "$target"
done

echo "[entrypoint] data dir = $DATA_DIR"
echo "[entrypoint] starting: $*"
exec "$@"
