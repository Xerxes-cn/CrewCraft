from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.engine.skills import load_skills
from app.engine.tools import Tool
from app.models.orm import Crew, Agent
from app.schemas.api import AgentCreate, AgentResponse, AgentUpdate
from app.services.workspace import init_agent_workspace, remove_agent_workspace

router = APIRouter(prefix="/api", tags=["agents"])


@router.get("/tools")
async def list_tools():
    """List all available tools with name and description."""
    return [
        {"name": name, "description": cls.description}
        for name, cls in Tool._tools.items()
    ]


@router.get("/skills")
async def list_skills():
    """List all skill presets from skills/*.md files."""
    return load_skills()


@router.post("/crews/{crew_id}/agents", response_model=AgentResponse, status_code=201)
async def create_agent(crew_id: int, data: AgentCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Crew).where(Crew.id == crew_id))
    crew = result.scalar_one_or_none()
    if not crew:
        raise HTTPException(status_code=404, detail="Crew not found")

    agent = Agent(crew_id=crew_id, **data.model_dump())
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    init_agent_workspace(crew.id, crew.name, agent.name, agent.order)
    return agent


@router.put("/agents/{agent_id}", response_model=AgentResponse)
async def update_agent(agent_id: int, data: AgentUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(agent, key, value)

    await db.commit()
    await db.refresh(agent)
    return agent


@router.delete("/agents/{agent_id}", status_code=204)
async def delete_agent(agent_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    crew_result = await db.execute(select(Crew).where(Crew.id == agent.crew_id))
    crew = crew_result.scalar_one_or_none()
    if crew:
        remove_agent_workspace(crew.id, crew.name, agent.name, agent.order)

    await db.delete(agent)
    await db.commit()
