"""人机交互 API — Agent 向用户请求确认、选择或输入。

支持三种交互类型：
- confirm: 是/否确认（二元审批）
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

# 向后兼容旧 /api/approvals 路径
approvals_router = APIRouter(prefix="/api/approvals", tags=["approvals"])


class InteractionRequest(BaseModel):
    request_id: str
    agent: str
    session_id: str
    type: str  # confirm | select | input
    prompt: str = ""        # 展示给用户的问题
    options: list[str] = [] # select 类型的选项
    metadata: dict = {}


# ── 内存队列 ────────────────────────────────────────────────────────

_pending: list[dict] = []
_lock = threading.Lock()


def add_interaction(
    agent: str, session_id: str, type: str, prompt: str = "",
    options: list[str] | None = None, metadata: dict | None = None,
) -> str:
    """添加一条交互请求。返回 request_id。

    type: confirm | select | input
    """
    rid = f"hq_{uuid.uuid4().hex[:12]}"
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


# 向后兼容
def add_approval(agent: str, session_id: str, tool: str, action: str, permission: str) -> str:
    return add_interaction(
        agent=agent, session_id=session_id, type="confirm",
        prompt=f"Agent '{agent}' wants to execute:\n\n{tool}: {action}\n\nPermission: {permission}",
        metadata={"tool": tool, "action": action, "permission": permission},
    )


def get_pending(session_id: Optional[str] = None) -> list[dict]:
    with _lock:
        if session_id:
            return [p for p in _pending if p["session_id"] == session_id]
        return list(_pending)


def resolve_interaction(request_id: str, response: str) -> dict | None:
    """解决一条交互。返回已处理的请求，或 None。

    对于 confirm 类型，response 应为 "approved" 或 "denied"。
    """
    with _lock:
        for i, p in enumerate(_pending):
            if p["request_id"] == request_id:
                _pending.pop(i)
                p["response"] = response
                logger.info(f"HITL resolved: {request_id[:16]} → {response}")
                return p
    return None


# 向后兼容
def resolve_approval(request_id: str, decision: str) -> dict | None:
    return resolve_interaction(request_id, decision)


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
    # 向后兼容字段
    tool: str = ""
    action: str = ""
    permission: str = ""


@router.post("/submit", status_code=201)
async def submit(body: SubmitRequest):
    """Agent 提交交互请求。"""
    if body.tool or body.action:
        # 向后兼容旧的 approve 请求
        prompt = body.prompt or f"Agent '{body.agent}' wants:\n\n{body.tool}: {body.action}"
        metadata = body.metadata or {"tool": body.tool, "action": body.action, "permission": body.permission}
        rid = add_interaction(body.agent, body.session_id, body.type or "confirm", prompt, body.options, metadata)
    else:
        rid = add_interaction(body.agent, body.session_id, body.type, body.prompt, body.options, body.metadata)
    return {"request_id": rid, "status": "pending"}


@router.get("/pending")
async def list_pending(session: str = Query(None)):
    return get_pending(session)


@router.post("/{request_id}/resolve")
async def resolve(request_id: str, body: dict = {}):
    """统一解决交互 — response 值取决于 type：
    - confirm: "approved" 或 "denied"
    - select: 选中的选项字符串
    - input: 用户输入的文本
    """
    response = body.get("response", body.get("decision", ""))
    if not response:
        raise HTTPException(status_code=400, detail="需要 response 字段")
    result = resolve_interaction(request_id, response)
    if result is None:
        raise HTTPException(status_code=404, detail="交互请求未找到或已处理")
    return result


# ── 向后兼容路由（deprecated，映射到 /api/approvals）──────────────────


class LegacySubmitRequest(BaseModel):
    agent: str
    session_id: str
    tool: str
    action: str
    permission: str


@approvals_router.post("/submit", status_code=201)
async def legacy_submit(body: LegacySubmitRequest):
    """已弃用：请使用 /api/interactions/submit。"""
    rid = add_approval(body.agent, body.session_id, body.tool, body.action, body.permission)
    return {"request_id": rid, "status": "pending"}


@approvals_router.get("/pending")
async def legacy_pending(session: str = Query(None)):
    return get_pending(session)


@approvals_router.post("/{request_id}/approve")
async def legacy_approve(request_id: str):
    result = resolve_approval(request_id, "approved")
    if result is None:
        raise HTTPException(status_code=404, detail="审批请求未找到或已处理")
    return result


@approvals_router.post("/{request_id}/deny")
async def legacy_deny(request_id: str):
    result = resolve_approval(request_id, "denied")
    if result is None:
        raise HTTPException(status_code=404, detail="审批请求未找到或已处理")
    return result
