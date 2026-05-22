#!/bin/sh
# 容器启动钩子:
# 1) 在 $MAIL_DATA_DIR (默认 /data) 下准备好 config.json / proxies.txt /
#    Results/ / Profiles/
# 2) 软链到 /app 下,让 Python 代码 不感知 数据目录
# 3) exec 用户指定的 CMD (默认 web_main.py;CLI 模式则是 main.py)
set -e

DATA_DIR="${MAIL_DATA_DIR:-/data}"
mkdir -p "$DATA_DIR/Results" "$DATA_DIR/Profiles"

# ── 默认 config.json ──────────────────────────────────────────
# 仅当 文件不存在或为空 时写入默认值
# - 默认 headless=true (容器无图形界面)
# - browser_path 指向 Debian 包安装的 firefox-esr
# - web.host=0.0.0.0 让 Web 控制台能从宿主机访问
if [ ! -s "$DATA_DIR/config.json" ]; then
    cat > "$DATA_DIR/config.json" <<'EOF'
{
    "ruyipage": {
        "headless": true,
        "browser_path": "/usr/bin/firefox-esr",
        "profile_root": "Profiles"
    },
    "web": {
        "host": "0.0.0.0",
        "port": 8787
    }
}
EOF
    echo "[entrypoint] 已生成默认 $DATA_DIR/config.json (headless + 系统 Firefox)"
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
