from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


import app.models.orm  # noqa: F401 - register models
from app.models.orm import Crew

DEFAULT_CREW_ID = 1
DEFAULT_CREW_NAME = "默认团队"
DEFAULT_WORKFLOW = "roundtable"


async def get_db() -> AsyncSession:
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Ensure default crew exists
    async with async_session() as session:
        from sqlalchemy import select
        result = await session.execute(select(Crew).where(Crew.id == DEFAULT_CREW_ID))
        if not result.scalar_one_or_none():
            default = Crew(
                id=DEFAULT_CREW_ID,
                name=DEFAULT_CREW_NAME,
                workflow_type=DEFAULT_WORKFLOW,
                workflow_config={"max_rounds": 2},
            )
            session.add(default)
            await session.commit()
