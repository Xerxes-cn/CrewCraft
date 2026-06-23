"""Task creation and status API routes."""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..manager.agent_manager import agent_manager
from ..manager.ws_manager import ws_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/tasks", tags=["tasks"])


# ── Request/Response schemas ──────────────────────────────────────────

class TaskCreate(BaseModel):
    agent_name: str
    content: str


class TaskResponse(BaseModel):
    task_id: str
    session_id: str = ""
    agent_name: str = ""
    status: str  # pending / running / completed / failed
    result: str = ""
    error: str = ""


# ── Routes ────────────────────────────────────────────────────────────

@router.post("", status_code=202)
async def create_task(body: TaskCreate):
    """Create a new task and dispatch to the specified agent."""
    config = agent_manager.load_config(body.agent_name)
    if not config:
        raise HTTPException(status_code=404, detail=f"Agent '{body.agent_name}' not found")

    # Ensure agent is running
    if not agent_manager.is_online(body.agent_name):
        port = await agent_manager.start_agent(body.agent_name)
        if port is None:
            raise HTTPException(status_code=500, detail=f"Failed to start agent '{body.agent_name}'")

        # Wait for agent to connect
        import asyncio
        for _ in range(20):  # 10 seconds max
            if agent_manager.is_online(body.agent_name):
                break
            await asyncio.sleep(0.5)
        else:
            raise HTTPException(status_code=500, detail=f"Agent '{body.agent_name}' did not connect in time")

    # Dispatch task via WebSocket
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


@router.get("/{task_id}")
async def get_task_status(task_id: str):
    """Get the status of a task."""
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
    """List all task IDs and their statuses."""
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
