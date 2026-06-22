from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.engine.builder import build_crew_and_tasks
from app.engine.runner import run_crew_stream
from app.engine.workflows.roundtable import run_roundtable_stream
from app.models.orm import Crew, Task
from app.schemas.api import TaskResponse, TaskRunRequest
from app.services.workspace import agent_dir

router = APIRouter(tags=["tasks"])


def _agents_to_dicts(agents, crew_name: str = "", crew_tools: list | None = None) -> list[dict]:
    result = []
    for a in agents:
        d = {
            "id": a.id,
            "name": a.name,
            "role": a.role,
            "system_prompt": a.system_prompt,
            "tools": crew_tools if crew_tools is not None else (a.tools or []),
            "llm_config": a.llm_config or {},
            "order": a.order,
        }
        if crew_name:
            d["workspace"] = str(agent_dir(a.crew_id, crew_name, a.name, a.order))
        result.append(d)
    return result


async def _stream_workflow(
    crewai_crew,
    initial_state: dict,
) -> AsyncGenerator[dict, None]:
    """Run a workflow and yield structured events."""
    workflow_type = initial_state.get("workflow_type", "sequential")

    if workflow_type == "roundtable":
        agents = initial_state["agents"]
        task_input = initial_state["task_input"]
        max_rounds = initial_state.get("max_rounds", 2)

        all_messages: list[dict] = []
        final_result = ""
        async for event in run_roundtable_stream(agents, task_input, max_rounds):
            if event["type"] == "done":
                msg = {
                    "agent_name": event["agent_name"],
                    "agent_role": event.get("agent_role", ""),
                    "content": event["content"],
                }
                all_messages.append(msg)
                if event["agent_name"] == "Summary":
                    final_result = event["content"]

        yield {
            "type": "workflow_complete",
            "final_result": final_result,
            "messages": all_messages,
        }
    else:
        all_messages, final_result = await run_crew_stream(crewai_crew, 0, 0)
        yield {
            "type": "workflow_complete",
            "final_result": final_result,
            "messages": all_messages,
        }


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

    agents_dicts = _agents_to_dicts(crew.agents, crew.name, crew.tools)

    workflow_type = crew.workflow_type

    if workflow_type == "roundtable":
        crewai_crew = None
    else:
        crewai_crew, _ = build_crew_and_tasks(crew, agents_dicts, data.input)

    initial_state = {
        "task_input": data.input,
        "messages": [],
        "agents": agents_dicts,
        "workflow_type": workflow_type,
        "max_rounds": (crew.workflow_config or {}).get("max_rounds", 2),
    }

    all_messages = []
    final_result = ""
    async for event in _stream_workflow(crewai_crew, initial_state):
        if event["type"] == "workflow_complete":
            final_result = event.get("final_result", "")
            all_messages = event.get("messages", [])

    task.status = "completed"
    task.messages = all_messages
    task.result = final_result
    await db.commit()
    await db.refresh(task)

    return task


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
