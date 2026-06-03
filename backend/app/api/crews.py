from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db, async_session
from app.models.orm import Crew, Agent
from app.schemas.api import CrewCreate, CrewResponse, CrewUpdate
from app.services.workspace import init_crew_workspace, init_agent_workspace, remove_crew_workspace

router = APIRouter(prefix="/api/crews", tags=["crews"])


@router.post("", response_model=CrewResponse, status_code=201)
async def create_crew(data: CrewCreate, db: AsyncSession = Depends(get_db)):
    crew = Crew(**data.model_dump())
    db.add(crew)
    await db.commit()
    init_crew_workspace(crew.id, crew.name)
    result = await db.execute(
        select(Crew).options(selectinload(Crew.agents)).where(Crew.id == crew.id)
    )
    return result.scalar_one()


@router.get("", response_model=list[CrewResponse])
async def list_crews(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Crew).options(selectinload(Crew.agents)).order_by(Crew.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{crew_id}", response_model=CrewResponse)
async def get_crew(crew_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Crew).options(selectinload(Crew.agents)).where(Crew.id == crew_id)
    )
    crew = result.scalar_one_or_none()
    if not crew:
        raise HTTPException(status_code=404, detail="Crew not found")
    return crew


@router.put("/{crew_id}", response_model=CrewResponse)
async def update_crew(crew_id: int, data: CrewUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Crew).options(selectinload(Crew.agents)).where(Crew.id == crew_id)
    )
    crew = result.scalar_one_or_none()
    if not crew:
        raise HTTPException(status_code=404, detail="Crew not found")

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(crew, key, value)

    await db.commit()
    await db.refresh(crew)
    return crew


@router.delete("/{crew_id}", status_code=204)
async def delete_crew(crew_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Crew).where(Crew.id == crew_id))
    crew = result.scalar_one_or_none()
    if not crew:
        raise HTTPException(status_code=404, detail="Crew not found")
    remove_crew_workspace(crew.id, crew.name)
    await db.delete(crew)
    await db.commit()
