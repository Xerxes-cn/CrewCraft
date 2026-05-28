from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.engine.compiler import compile_crew_graph
from app.models.orm import Crew, Task
from app.schemas.api import TaskResponse, TaskRunRequest
from app.ws.manager import manager, stream_workflow

router = APIRouter(tags=["tasks"])


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
        "agents": crew.agents,
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
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(crew_id, ws)


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
