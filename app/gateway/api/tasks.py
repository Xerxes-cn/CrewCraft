"""任务创建和状态查询 API 路由。"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..manager.agent_manager import agent_manager
from ..manager.ws_manager import ws_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/tasks", tags=["tasks"])


# ── 请求/响应 Schema ──────────────────────────────────────────────────

class TaskCreate(BaseModel):
    agent_name: str = ""  # 可选 — 省略则由编排器自动分配
    content: str


class TaskResponse(BaseModel):
    task_id: str
    session_id: str = ""
    agent_name: str = ""
    status: str  # pending / running / completed / failed
    result: str = ""
    error: str = ""
    plan: list = []


async def _ensure_agent_online(agent_name: str):
    """确保一个 Agent 正在运行并已连接。"""
    if not agent_manager.is_online(agent_name):
        await agent_manager.start_agent(agent_name)
        import asyncio
        for _ in range(20):
            if agent_manager.is_online(agent_name):
                return
            await asyncio.sleep(0.5)
        raise HTTPException(status_code=500, detail=f"Agent '{agent_name}' did not connect in time")


# ── 路由 ────────────────────────────────────────────────────────────────

@router.post("", status_code=202)
async def create_task(body: TaskCreate):
    """创建新任务。不带 agent_name 时，编排器自动分配。"""
    if body.agent_name:
        # ── 直接分派 ──────────────────────────────────────────────────
        config = agent_manager.load_config(body.agent_name)
        if not config:
            raise HTTPException(status_code=404, detail=f"Agent '{body.agent_name}' not found")

        await _ensure_agent_online(body.agent_name)

        try:
            info = await ws_manager.dispatch_task(body.agent_name, body.content)
        except RuntimeError as e:
            raise HTTPException(status_code=503, detail=str(e))

        logger.info(f"Task {info['task_id']} dispatched to {body.agent_name}")
        return TaskResponse(
            task_id=info["task_id"],
            session_id=info["session_id"],
            agent_name=body.agent_name,
            status=info["status"],
        )
    else:
        # ── 编排器自动分配 ───────────────────────────────────────────
        from app.gateway.orchestrator import get_orchestrator
        orch = get_orchestrator(agent_manager, ws_manager)
        result = await orch.handle_task(body.content)

        if result["status"] == "failed":
            return TaskResponse(
                task_id=result["task_id"],
                session_id=result["session_id"],
                status="failed",
                error=result.get("error", "Orchestration failed"),
            )

        logger.info(f"Task {result['task_id']} orchestrated → {len(result.get('plan', []))} sub-tasks")
        return TaskResponse(
            task_id=result["task_id"],
            session_id=result["session_id"],
            status="pending",
            plan=result.get("plan", []),
        )


@router.get("/{task_id}")
async def get_task_status(task_id: str):
    """获取任务状态。"""
    result = ws_manager.get_task_result(task_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")

    return TaskResponse(
        task_id=result.get("task_id", task_id),
        session_id=result.get("session_id", ""),
        status=result.get("status", "pending"),
        result=result.get("result", ""),
        error=result.get("error"),
    )


@router.get("")
async def list_tasks():
    """列出所有任务 ID 及其状态。"""
    tasks = []
    for task_id in ws_manager.all_task_ids():
        result = ws_manager.get_task_result(task_id)
        if result:
            tasks.append(TaskResponse(
                task_id=result.get("task_id", task_id),
                session_id=result.get("session_id", ""),
                status=result.get("status", "pending"),
                result=result.get("result", ""),
            ))
    return tasks
