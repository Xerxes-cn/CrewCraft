"""人机交互 API — Agent 向用户请求确认、选择或输入。

支持三种交互类型：
- confirm: 是/否确认
- select: 多选一，用户从选项中挑选
- input: 自由文本输入
"""

import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/interactions", tags=["interactions"])


# ── 内存队列 ────────────────────────────────────────────────────────

_pending: list[dict] = []
_lock = threading.Lock()


def add_interaction(
    agent: str, session_id: str, type: str, prompt: str = "",
    options: list[str] | None = None, metadata: dict | None = None,
) -> str:
    """添加一条交互请求。返回 request_id。"""
    rid = f"itx_{uuid.uuid4().hex[:12]}"
    item = {
        "request_id": rid,
        "agent": agent,
        "session_id": session_id,
        "type": type,
        "prompt": prompt,
        "options": options or [],
        "metadata": metadata or {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    with _lock:
        _pending.append(item)
    logger.info(f"HITL {type}: {agent} [{rid[:16]}]")
    return rid


def get_pending(session_id: Optional[str] = None) -> list[dict]:
    with _lock:
        if session_id:
            return [p for p in _pending if p["session_id"] == session_id]
        return list(_pending)


def resolve_interaction(request_id: str, response: str) -> dict | None:
    """解决一条交互。返回已处理的请求，或 None。"""
    with _lock:
        for i, p in enumerate(_pending):
            if p["request_id"] == request_id:
                _pending.pop(i)
                p["response"] = response
                logger.info(f"HITL resolved: {request_id[:16]} → {response}")
                return p
    return None


def get_queue_size() -> int:
    with _lock:
        return len(_pending)


def clear_queue():
    with _lock:
        _pending.clear()


# ── 路由 ────────────────────────────────────────────────────────────


class SubmitRequest(BaseModel):
    agent: str
    session_id: str
    type: str = "confirm"
    prompt: str = ""
    options: list[str] = []
    metadata: dict = {}


@router.post("/submit", status_code=201)
async def submit(body: SubmitRequest):
    """Agent 提交交互请求。"""
    rid = add_interaction(body.agent, body.session_id, body.type, body.prompt, body.options, body.metadata)
    return {"request_id": rid, "status": "pending"}


@router.get("/pending")
async def list_pending(session: str = Query(None)):
    return get_pending(session)


class ResolveRequest(BaseModel):
    response: str


@router.post("/{request_id}/resolve")
async def resolve(request_id: str, body: ResolveRequest):
    """解决交互 — response 值取决于 type：
    - confirm: "approved" 或 "denied"
    - select: 选中的选项字符串
    - input: 用户输入的文本
    """
    if not body.response:
        raise HTTPException(status_code=400, detail="需要 response 字段")
    result = resolve_interaction(request_id, body.response)
    if result is None:
        raise HTTPException(status_code=404, detail="交互请求未找到或已处理")
    return result
