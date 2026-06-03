from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db, async_session
from app.engine.compiler import compile_crew_graph
from app.models.orm import Crew, Task
from app.schemas.api import TaskResponse, TaskRunRequest
from app.services.workspace import agent_dir
from app.ws.manager import manager, stream_workflow, stream_agent_round

router = APIRouter(tags=["tasks"])


def _agents_to_dicts(agents, crew_name: str = "") -> list[dict]:
    result = []
    for a in agents:
        d = {
            "id": a.id,
            "name": a.name,
            "role": a.role,
            "system_prompt": a.system_prompt,
            "tools": a.tools or [],
            "llm_config": a.llm_config or {},
            "order": a.order,
        }
        if crew_name:
            d["workspace"] = str(agent_dir(a.crew_id, crew_name, a.name, a.order))
        result.append(d)
    return result


@router.post("/api/crews/{crew_id}/run", response_model=TaskResponse, status_code=201)
async def run_task(crew_id: int, data: TaskRunRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Crew).options(selectinload(Crew.agents)).where(Crew.id == crew_id)
    )
    crew = result.scalar_one_or_none()
    if not crew:
        raise HTTPException(status_code=404, detail="Crew not found")
    if not crew.agents:
        raise HTTPException(status_code=400, detail="Crew has no agents")

    task = Task(crew_id=crew_id, input=data.input, status="running")
    db.add(task)
    await db.commit()
    await db.refresh(task)

    graph = compile_crew_graph(crew)
    initial_state = {
        "task_input": data.input,
        "messages": [],
        "agents": _agents_to_dicts(crew.agents, crew.name),
        "current_index": 0,
        "final_result": "",
        "current_round": 0,
        "max_rounds": (crew.workflow_config or {}).get("max_rounds", 2),
        "plan": [],
    }

    all_messages = []
    final_result = ""
    async for event in stream_workflow(crew_id, task.id, graph, initial_state):
        if event["type"] == "workflow_complete":
            final_result = event.get("final_result", "")
            all_messages = event.get("messages", [])

    task.status = "completed"
    task.messages = all_messages
    task.result = final_result
    await db.commit()
    await db.refresh(task)

    return task


@router.websocket("/api/crews/{crew_id}/stream")
async def stream_endpoint(ws: WebSocket, crew_id: int):
    await manager.connect(crew_id, ws)

    try:
        while True:
            data = await ws.receive_json()
            msg_type = data.get("type", "task")
            user_input = data.get("input", "")

            if not user_input.strip():
                continue

            if msg_type == "task":
                # Initial task: load crew, run full workflow
                async with async_session() as db:
                    result = await db.execute(
                        select(Crew).options(selectinload(Crew.agents)).where(Crew.id == crew_id)
                    )
                    crew = result.scalar_one_or_none()
                    if not crew or not crew.agents:
                        await ws.send_json({"type": "error", "message": "团队不存在或没有智能体"})
                        continue

                    agents_dicts = _agents_to_dicts(crew.agents, crew.name)
                    task = Task(crew_id=crew_id, input=user_input, status="running")
                    db.add(task)
                    await db.commit()
                    await db.refresh(task)

                    graph = compile_crew_graph(crew)
                    initial_state = {
                        "task_input": user_input,
                        "messages": [],
                        "agents": agents_dicts,
                        "current_index": 0,
                        "final_result": "",
                        "current_round": 0,
                        "max_rounds": (crew.workflow_config or {}).get("max_rounds", 2),
                        "plan": [],
                    }

                    all_messages = []
                    final_result = ""
                    async for event in stream_workflow(crew_id, task.id, graph, initial_state):
                        if event["type"] == "agent_message":
                            all_messages.append(event["data"])
                        if event["type"] == "workflow_complete":
                            final_result = event.get("final_result", "")

                    task.status = "completed"
                    task.messages = all_messages
                    task.result = final_result
                    await db.commit()

            elif msg_type == "followup":
                # Follow-up: run interactive discussion round
                async with async_session() as db:
                    result = await db.execute(
                        select(Crew).options(selectinload(Crew.agents)).where(Crew.id == crew_id)
                    )
                    crew = result.scalar_one_or_none()
                    if not crew or not crew.agents:
                        await ws.send_json({"type": "error", "message": "团队不存在或没有智能体"})
                        continue

                    agents_dicts = _agents_to_dicts(crew.agents, crew.name)

                    # Send user message to frontend
                    user_msg = {"agent_name": "用户", "agent_role": "用户", "content": user_input}
                    await ws.send_json({"type": "agent_message", "data": user_msg})

                    # Get conversation history (exclude user messages for now)
                    history = await _get_recent_history(crew_id, limit=20)

                    await stream_agent_round(crew_id, agents_dicts, user_input, history)
                    await ws.send_json({"type": "followup_complete"})

    except WebSocketDisconnect:
        manager.disconnect(crew_id, ws)


async def _get_recent_history(crew_id: int, limit: int = 20) -> list[dict]:
    """Load recent conversation history from past tasks for context continuity."""
    async with async_session() as db:
        result = await db.execute(
            select(Task)
            .where(Task.crew_id == crew_id, Task.status == "completed")
            .order_by(Task.created_at.desc())
            .limit(3)
        )
        tasks = result.scalars().all()
        history: list[dict] = []
        for t in reversed(tasks):
            msgs = t.messages or []
            history.extend(msgs)
        return history[-limit:]


@router.get("/api/crews/{crew_id}/tasks", response_model=list[TaskResponse])
async def list_tasks(crew_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Task)
        .where(Task.crew_id == crew_id)
        .order_by(Task.created_at.desc())
        .limit(50)
    )
    return result.scalars().all()


@router.get("/api/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task
