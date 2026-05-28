"""
FastAPI 入口。
提供 V2 Agent 的 HTTP API 服务 + 静态前端托管。
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes.agent_v2 import router as agent_v2_router

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "app" / "api" / "static"
FILES_DIR = BASE_DIR / "files"

app = FastAPI(
    title="Patent Analysis API",
    description="AI 驱动的专利方案分析与交底书生成系统",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 路由
app.include_router(agent_v2_router)

# 静态文件（前端页面、交底书下载等）
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/files", StaticFiles(directory=str(FILES_DIR)), name="files")


@app.get("/")
async def root():
    """首页重定向到前端页面。"""
    return RedirectResponse(url="/static/agent_v2.html")


@app.get("/health")
async def health():
    return {"status": "ok"}
