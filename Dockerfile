# MS Mail Reg Tool — Docker 镜像
# 同时支持 Web 模式 (默认) 和 CLI 模式 (compose --profile cli up)

FROM python:3.11-slim-bookworm AS runtime

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=Asia/Shanghai \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    MAIL_DATA_DIR=/data \
    MOZ_HEADLESS=1

# ── 系统依赖 ────────────────────────────────────────────────
# - firefox-esr: ruyipage 驱动的浏览器
# - fonts-noto-cjk: 中文字体, outlook 注册页全是中文 UI
# - fonts-liberation: 通用衬线/无衬线
# - tini: 1 号进程, 接管信号、回收僵尸进程
# - tzdata + ca-certificates: 时区和 HTTPS
RUN apt-get update && apt-get install -y --no-install-recommends \
        firefox-esr \
        fonts-noto-cjk \
        fonts-noto-color-emoji \
        fonts-liberation \
        ca-certificates \
        tini \
        tzdata \
        procps \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先装 Python 依赖, 利用 layer cache
COPY requirements.txt ./
RUN pip install -r requirements.txt

# 拷贝源码 (.dockerignore 已排除运行时产物)
COPY . .

# entrypoint 负责把 /data 下的持久化文件软链到 /app
RUN chmod +x docker/entrypoint.sh

# 数据卷挂载点
RUN mkdir -p /data
VOLUME ["/data"]

# Web 控制台端口
EXPOSE 8787

ENTRYPOINT ["/usr/bin/tini", "--", "/app/docker/entrypoint.sh"]
CMD ["python", "web_main.py", "--host", "0.0.0.0", "--port", "8787"]
