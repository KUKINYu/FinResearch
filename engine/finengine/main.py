"""FinEngine 服务入口。

设计（见 CLAUDE.md 技术决策）：
- 仅监听 127.0.0.1，端口随机（或调用方指定），启动时向 stdout 打印一行 JSON：
  {"event": "ready", "port": <端口>, "token": "<随机令牌>"}
- 所有 API 请求需带 X-FinEngine-Token 头，令牌即启动时打印的值
- 由 Electron 主进程拉起（开发模式用 .venv 的 python，打包后用 finengine.exe）
"""

import json
import secrets
import socket

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from . import __version__
from .api import router as api_router
from .db import init_db

app = FastAPI(title="FinEngine", version=__version__)
app.include_router(api_router)

# 模块级令牌：serve() 启动时生成，通过 ready 行告知调用方
TOKEN = secrets.token_hex(16)

init_db()  # 启动时确保数据库表就绪


@app.middleware("http")
async def require_token(request: Request, call_next):
    """本地服务也要令牌：防止本机其他程序冒用（本机 HTTP 无 TLS）。"""
    if request.headers.get("X-FinEngine-Token") != TOKEN:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return await call_next(request)


@app.get("/api/health")
async def health():
    """健康检查：Electron 启动后用它确认引擎就绪。"""
    return {"status": "ok", "version": __version__}


@app.get("/api/info")
async def info():
    """引擎信息（数据目录等，供界面设置页显示）。"""
    from . import config

    return {
        "version": __version__,
        "data_dir": str(config.data_dir()),
        "db_path": str(config.db_path()),
    }


def _pick_port() -> int:
    """随机找一个空闲端口（bind 0 后立即释放，本机场景竞态可忽略）。"""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def serve(host: str = "127.0.0.1", port: int = 0) -> None:
    """启动引擎。port=0 表示随机端口。ready 行是调用方与引擎的握手协议。"""
    global TOKEN
    TOKEN = secrets.token_hex(16)
    if port == 0:
        port = _pick_port()
    print(json.dumps({"event": "ready", "port": port, "token": TOKEN}), flush=True)
    uvicorn.run(app, host=host, port=port, log_level="warning")
