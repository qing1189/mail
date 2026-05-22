# MS Mail Reg Tool

Outlook & Hotmail 浏览器自动化注册工具。

支持两种使用方式:
- **CLI**:`python main.py`,交互式终端,带流光状态条
- **Web 控制台**:`python web_main.py`,浏览器图形界面 + 实时日志 + 多批次队列管理

## 本地直接跑

```bash
pip install -r requirements.txt
python web_main.py        # Web 模式: http://localhost:8787
# 或
python main.py            # CLI 模式
```

首次访问 Web 时会要求设置一个登录密码,后续用此密码登录。

## Docker 运行 🐳

镜像已经把 Firefox ESR + 中文字体 + 默认 headless 配置好,开箱即用。

```bash
# 第一次:复制环境变量模板,按需修改
cp .env.example .env

# 启动 Web 控制台 (默认服务)
docker compose up -d

# 浏览器访问 http://<宿主机IP>:8787

# 看实时日志
docker compose logs -f web

# 停止
docker compose down
```

如果想用交互式 CLI(`main.py` 的彩色菜单),用专门的 `cli` profile:

```bash
docker compose --profile cli run --rm cli
```

### 环境变量(`.env` 文件)

所有 Docker 相关的可调参数都在 `.env` 里集中管理。常用:

| 变量 | 默认值 | 说明 |
|---|---|---|
| `HOST_PORT` | `8787` | 宿主机暴露的端口 |
| `WEB_PORT` | `8787` | 容器内 uvicorn 监听端口 |
| `TZ` | `Asia/Shanghai` | 容器时区 |
| `SHM_SIZE` | `1gb` | Firefox 共享内存(默认 64M 必崩) |
| `RESTART_POLICY` | `unless-stopped` | 容器重启策略 |
| `IMAGE_TAG` | `ms-mail-reg-tool:latest` | 镜像 tag |
| `CONTAINER_NAME_WEB` | `ms-mail-web` | Web 容器名 |
| `DEFAULT_HEADLESS` | `true` | 首次生成 config.json 时的 headless 默认值 |
| `DEFAULT_BROWSER_PATH` | `/usr/bin/firefox-esr` | 同上,Firefox 路径 |

不修改 `.env` 也能跑(全部都有兜底值),只是改端口/时区/容器名时方便些。

### 持久化数据

所有运行时数据都落在宿主机 `./data/` 目录,**首次启动会自动生成默认 config.json**:

| 路径 | 用途 |
|---|---|
| `./data/config.json` | 配置文件,在 Web 控制台修改后自动写回 |
| `./data/proxies.txt` | 代理列表,可在 Web 控制台「代理」标签上传/编辑 |
| `./data/Results/` | 注册成功的账号、OAuth Token 输出 |
| `./data/Profiles/` | 浏览器临时 profile(每次注册结束会清理) |

升级镜像时只要保留 `./data/` 即可保留全部数据。

### 自定义端口 / 主机名

直接改 `.env` 里的 `HOST_PORT`(宿主机) 或 `WEB_PORT`(容器内)即可:

```bash
# .env
HOST_PORT=9000
WEB_PORT=8787
```

然后 `docker compose up -d` 重启即可。

### 关于代理来源

Web 控制台支持四种代理模式,都可以在 Docker 里用:
- `api`:从代理 API 拉取(注意容器需能访问该 API)
- `file`:从 `proxies.txt` 读 `HOST:PORT:USER:PASS`
- `freefile`:从 `proxies.txt` 读 `HOST:PORT`
- `none`:**直连无代理**(适合本机或服务器已经在境外的场景)
