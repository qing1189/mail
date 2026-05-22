"""Web 控制台启动入口。

使用:
    python web_main.py                    # 默认从 config.json 读取 host/port
    python web_main.py --host 0.0.0.0 --port 8080
"""

import argparse

import uvicorn

from config import get_config


def main():
    cfg = get_config()
    web_cfg = cfg.get("web", {})

    parser = argparse.ArgumentParser(description="MS Mail Reg Tool — Web Console")
    parser.add_argument("--host", default=web_cfg.get("host", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(web_cfg.get("port", 8787)))
    parser.add_argument("--reload", action="store_true", help="开发模式自动重载")
    args = parser.parse_args()

    print(f"[Info] - 启动 Web 控制台: http://{args.host}:{args.port}")
    print("[Info] - 首次访问需要在 Web 界面设置登录密码")

    uvicorn.run(
        "web.server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
