from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.orm import Crew, Agent
from app.schemas.api import AgentCreate, AgentResponse, AgentUpdate

router = APIRouter(prefix="/api", tags=["agents"])


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
    await db.delete(agent)
    await db.commit()
