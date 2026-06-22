from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.agents import router as agents_router
from app.api.tasks import router as tasks_router
from app.database import init_db
from app.services.workspace import init_all_workspaces


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    init_all_workspaces()
    yield


app = FastAPI(title="CrewCraft", lifespan=lifespan)


app.include_router(agents_router)
app.include_router(tasks_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
