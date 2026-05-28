"""
Agent V2 API 路由。
提供 /agent/start、/chat、/upload、/parse、/cleanup 等端点。
"""

import json
import shutil
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agent_v2.agent_session import (
    stream_agent_start,
    stream_agent_chat,
    delete_session,
)
from app.services.mineru_service import MinerUService


router = APIRouter(prefix="/agent", tags=["agent_v2"])

# ---------- 配置 ----------

UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent.parent / "files"
ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

MINERU_OUTPUT_DIR = UPLOAD_DIR / "mineru_output"
DISCLOSURE_OUTPUT_DIR = UPLOAD_DIR / "disclosure_output"
_mineru = MinerUService()


# ---------- 请求模型 ----------

class StartRequest(BaseModel):
    document: str
    thread_id: Optional[str] = None


class PanelAction(BaseModel):
    type: str   # "confirm_features" | "select_solution" | "regenerate"
    data: dict = {}


class ChatRequest(BaseModel):
    thread_id: str
    message: str
    panel_action: Optional[PanelAction] = None


class ParseRequest(BaseModel):
    thread_id: str
    file_path: str
    filename: str
    model_version: Optional[str] = "vlm"


class CleanupRequest(BaseModel):
    thread_id: str


# ---------- SSE 辅助 ----------

async def _sse_generator(session_gen):
    """将 session 的 dict payload 包装为 SSE 格式。"""
    try:
        async for payload in session_gen:
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
    except Exception as e:
        error_payload = {"type": "error", "name": "", "data": {"message": str(e)}}
        yield f"data: {json.dumps(error_payload, ensure_ascii=False)}\n\n"


# ---------- 文件上传端点 ----------

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """上传文件到服务器，返回 thread_id 和 file_path。"""
    filename = Path(file.filename).name
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型: {ext}，支持: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    thread_id = f"agent-{uuid.uuid4().hex[:12]}"
    save_dir = UPLOAD_DIR / thread_id
    save_dir.mkdir(parents=True, exist_ok=True)

    save_path = save_dir / filename

    file_size = 0
    with open(save_path, "wb") as f:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            file_size += len(chunk)
            if file_size > MAX_FILE_SIZE:
                save_path.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="文件大小超过 50MB 限制")
            f.write(chunk)

    return {
        "thread_id": thread_id,
        "filename": filename,
        "file_path": str(save_path),
        "file_size": file_size,
    }


# ---------- MinerU 解析端点 ----------

@router.post("/parse")
async def parse_file(req: ParseRequest):
    """提交文件到 MinerU 进行 Markdown 转换，以 SSE 返回进度和结果。"""
    async def gen():
        async for payload in _mineru.process_file(
            file_path=req.file_path,
            filename=req.filename,
            model_version=req.model_version or "vlm",
            thread_id=req.thread_id,
        ):
            if payload.get("type") == "heartbeat":
                yield ": keepalive\n\n"
            else:
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------- 启动会话端点 ----------

@router.post("/start")
async def start_agent(req: StartRequest):
    """启动 Agent 会话，以 SSE 形式流式返回事件。"""
    thread_id = req.thread_id or f"agent-{uuid.uuid4().hex[:12]}"

    async def gen():
        async for chunk in _sse_generator(stream_agent_start(req.document, thread_id)):
            yield chunk

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------- 继续对话端点 ----------

@router.post("/chat")
async def chat_agent(req: ChatRequest):
    """继续 Agent 对话，以 SSE 形式流式返回事件。"""
    if not req.thread_id:
        raise HTTPException(status_code=400, detail="thread_id is required")

    panel_action_dict = None
    if req.panel_action:
        panel_action_dict = {"type": req.panel_action.type, "data": req.panel_action.data}

    async def gen():
        async for chunk in _sse_generator(
            stream_agent_chat(req.thread_id, req.message, panel_action_dict)
        ):
            yield chunk

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------- 清理端点 ----------

@router.post("/cleanup")
async def cleanup_session(req: CleanupRequest):
    """清理会话：删除上传文件、MinerU 输出、交底书输出、Agent 会话状态。"""
    thread_id = req.thread_id
    if not thread_id.startswith("agent-"):
        raise HTTPException(status_code=400, detail="无效的 thread_id")

    cleaned = []

    # 1. 上传的原始文件
    upload_dir = UPLOAD_DIR / thread_id
    if upload_dir.is_dir():
        shutil.rmtree(upload_dir, ignore_errors=True)
        cleaned.append("upload")

    # 2. MinerU 解析输出
    mineru_dir = MINERU_OUTPUT_DIR / thread_id
    if mineru_dir.is_dir():
        shutil.rmtree(mineru_dir, ignore_errors=True)
        cleaned.append("mineru_output")

    # 3. 交底书输出
    disclosure_file = DISCLOSURE_OUTPUT_DIR / f"{thread_id}.md"
    if disclosure_file.is_file():
        disclosure_file.unlink(missing_ok=True)
        cleaned.append("disclosure_output")

    # 4. Agent 会话状态
    delete_session(thread_id)
    cleaned.append("agent_session")

    return {"thread_id": thread_id, "cleaned": cleaned}
