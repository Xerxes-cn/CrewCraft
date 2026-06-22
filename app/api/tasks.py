from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import DEFAULT_CREW_ID, get_db
from app.engine.builder import build_crew_and_tasks
from app.engine.runner import run_crew_stream
from app.engine.workflows.roundtable import run_roundtable_stream
from app.models.orm import Crew, Task
from app.schemas.api import TaskResponse, TaskRunRequest

router = APIRouter(tags=["tasks"])


def _agents_to_dicts(agents) -> list[dict]:
    result = []
    for a in agents:
        result.append({
            "id": a.id,
            "name": a.name,
            "role": a.role,
            "system_prompt": a.system_prompt,
            "tools": a.tools or [],
            "llm_config": a.llm_config or {},
            "order": a.order,
        })
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


@router.post("/api/run", response_model=TaskResponse, status_code=201)
async def run_task(data: TaskRunRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Crew).options(selectinload(Crew.agents)).where(Crew.id == DEFAULT_CREW_ID)
    )
    crew = result.scalar_one_or_none()
    if not crew or not crew.agents:
        raise HTTPException(status_code=400, detail="没有可用的 Agent，请先添加 Agent")

    task = Task(crew_id=DEFAULT_CREW_ID, input=data.input, status="running")
    db.add(task)
    await db.commit()
    await db.refresh(task)

    agents_dicts = _agents_to_dicts(crew.agents)
    workflow_type = crew.workflow_type

    if workflow_type == "roundtable":
        crewai_crew = None
    else:
        crewai_crew, _ = build_crew_and_tasks(
            agents_dicts, data.input, workflow_type, crew.tools
        )

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


@router.get("/api/tasks", response_model=list[TaskResponse])
async def list_tasks(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Task)
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
