"""审批 API — REPL 轮询待审批操作。"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/approvals", tags=["approvals"])


class ApprovalRequest(BaseModel):
    request_id: str
    agent: str
    session_id: str
    tool: str
    action: str
    permission: str
    timestamp: str


# ── 内存队列 ────────────────────────────────────────────────────────

_pending: list[dict] = []
_lock = asyncio.Lock()


def add_approval(agent: str, session_id: str, tool: str, action: str, permission: str) -> str:
    """添加一条审批请求到队列。返回 request_id。"""
    rid = f"approval_{uuid.uuid4().hex[:12]}"
    item = {
        "request_id": rid,
        "agent": agent,
        "session_id": session_id,
        "tool": tool,
        "action": action,
        "permission": permission,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _pending.append(item)
    logger.info(f"审批请求: {agent}/{tool} [{rid[:16]}]")
    return rid


def get_pending(session_id: str = None) -> list[dict]:
    """获取待审批列表。可过滤 session。"""
    if session_id:
        return [p for p in _pending if p["session_id"] == session_id]
    return list(_pending)


def resolve_approval(request_id: str, decision: str) -> dict | None:
    """批准或拒绝。返回被处理的请求，或 None。"""
    for i, p in enumerate(_pending):
        if p["request_id"] == request_id:
            _pending.pop(i)
            p["decision"] = decision
            logger.info(f"审批 {decision}: {request_id[:16]}")
            return p
    return None


def get_queue_size() -> int:
    return len(_pending)


def clear_queue():
    """清空队列（测试用）。"""
    _pending.clear()


# ── 路由 ────────────────────────────────────────────────────────────

class SubmitRequest(BaseModel):
    agent: str
    session_id: str
    tool: str
    action: str
    permission: str


@router.post("/submit", status_code=201)
async def submit_approval(body: SubmitRequest):
    """Agent 提交审批请求。"""
    rid = add_approval(body.agent, body.session_id, body.tool, body.action, body.permission)
    return {"request_id": rid, "status": "pending"}


@router.get("/pending")
async def list_pending(session: str = Query(None)):
    """REPL 轮询此端点获取待审批请求。"""
    return get_pending(session)


@router.post("/{request_id}/approve")
async def approve(request_id: str):
    """批准一个审批请求。"""
    result = resolve_approval(request_id, "approved")
    if result is None:
        raise HTTPException(status_code=404, detail="审批请求未找到或已处理")
    return result


@router.post("/{request_id}/deny")
async def deny(request_id: str):
    """拒绝一个审批请求。"""
    result = resolve_approval(request_id, "denied")
    if result is None:
        raise HTTPException(status_code=404, detail="审批请求未找到或已处理")
    return result
