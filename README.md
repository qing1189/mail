# Outlook & Hotmail 浏览器自动化注册

基于 ruyipage 的 Outlook/Hotmail 邮箱自动注册工具，支持 OAuth2 Token 获取，提供 Web 控制面板。

## 功能特性

- 自动注册 Outlook/Hotmail 邮箱
- 支持多种代理来源（文件/API）
- 并发注册，可配置线程数
- OAuth2 授权获取 Token
- **Web 控制面板** - 可视化管理
- Docker 容器化部署

## 快速开始

### 方式一：Docker 一键部署（推荐）

```bash
# 复制配置文件
cp .env.example .env

# 构建并启动
docker-compose up -d

# 访问 Web 控制面板
# http://localhost:8000
```

### 方式二：Docker + VNC 调试

```bash
# 启动带 VNC 的版本
docker-compose --profile debug up -d outlook-register-vnc

# 访问 Web 控制面板: http://localhost:8000
# VNC 客户端连接: localhost:5900
```

### 方式三：开发模式

```bash
# 启动开发环境
docker-compose --profile dev up -d

# 后端: http://localhost:8000
# 前端: http://localhost:3000
```

### 方式四：本地运行

```bash
# 安装后端依赖
pip install -r requirements.txt

# 安装前端依赖
cd frontend && npm install && npm run build && cd ..

# 启动后端（会自动服务前端静态文件）
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

## Web 控制面板

访问 `http://localhost:8000` 打开 Web 控制面板。

### 功能模块

| 模块 | 功能 |
|------|------|
| **仪表盘** | 实时统计、成功率图表、任务进度、日志流 |
| **任务控制** | 启动/停止任务、配置参数、实时状态 |
| **配置管理** | 代理配置、OAuth2 设置、浏览器参数 |
| **结果查看** | 账号列表、Token 列表、导出功能 |

### API 文档

启动后访问 `http://localhost:8000/docs` 查看 API 文档。

## 配置说明

首次运行时通过 Web 界面配置，配置会保存到 `config.json`。

主要配置项：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| email_suffix | 邮箱后缀 | @outlook.com |
| proxy_source | 代理来源 | api |
| concurrent_flows | 并发线程数 | 10 |
| max_tasks | 最大任务数 | 20 |
| enable_oauth2 | 启用 OAuth2 | false |

## 环境变量

创建 `.env` 文件配置环境变量：

```bash
cp .env.example .env
```

| 变量 | 说明 | 默认值 |
|------|------|--------|
| TZ | 时区 | Asia/Shanghai |
| ENABLE_VNC | 启用 VNC | false |
| PYTHONUNBUFFERED | Python 输出不缓冲 | 1 |

## 代理配置

### 文件模式

创建 `proxies.txt`，每行一个代理：

```
# 格式：HOST:PORT:USER:PASS
192.168.1.1:8080:user:pass
```

### API 模式

配置 `proxy_api_url` 为代理 API 地址。

## 结果输出

注册成功的账号保存在 `Results/` 目录：

- `unlogged_email.txt` - 未启用 OAuth2 的账号
- `logged_email.txt` - 启用 OAuth2 的账号
- `outlook_token.txt` - OAuth2 Token

可通过 Web 界面直接导出。

## 项目结构

```
.
├── backend/                    # FastAPI 后端
│   ├── api/                   # API 端点
│   ├── core/                  # 核心逻辑
│   └── main.py                # 后端入口
├── frontend/                   # Vue 前端
│   ├── src/
│   │   ├── views/             # 页面组件
│   │   ├── components/        # 通用组件
│   │   ├── api/               # API 封装
│   │   └── stores/            # 状态管理
│   └── package.json
├── controllers/                # 浏览器控制器
├── config.py                   # 配置管理
├── utils.py                    # 工具函数
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## 注意事项

1. 代理质量直接影响注册成功率
2. 建议使用高质量的住宅代理
3. 并发数不宜过高，建议 5-15
4. Docker 运行时默认使用 headless 模式

## 许可证

仅供学习研究使用，请遵守相关服务条款。
