FROM python:3.11-slim AS backend

# 设置非交互模式
ENV DEBIAN_FRONTEND=noninteractive

# 安装系统依赖和 Firefox
RUN apt-get update && apt-get install -y --no-install-recommends \
    firefox-esr \
    wget \
    gnupg2 \
    xvfb \
    x11vnc \
    fluxbox \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 复制依赖文件并安装 Python 依赖
COPY requirements.txt backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r backend/requirements.txt

# 复制项目文件
COPY . .

# 创建必要的目录
RUN mkdir -p Profiles Results

# 前端构建阶段
FROM node:20-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ .
RUN npm run build

# 最终镜像
FROM python:3.11-slim

# 安装运行时依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    firefox-esr \
    xvfb \
    fluxbox \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 复制后端依赖
COPY requirements.txt backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r backend/requirements.txt

# 复制后端代码
COPY *.py ./
COPY controllers/ ./controllers/
COPY backend/ ./backend/

# 复制前端构建产物
COPY --from=frontend-build /app/frontend/dist ./static

# 创建必要的目录
RUN mkdir -p Profiles Results

# 复制启动脚本
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# 暴露端口
EXPOSE 8000

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
