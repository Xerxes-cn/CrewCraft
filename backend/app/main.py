from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.crews import router as crews_router
from app.api.agents import router as agents_router
from app.api.tasks import router as tasks_router
from app.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="CrewCraft", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(crews_router)
app.include_router(agents_router)
app.include_router(tasks_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
