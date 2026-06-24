"""Gateway FastAPI application.

The gateway is the central hub:
- REST API for CLI / IM platform clients
- Internal WebSocket server for agent processes
- Manages agent lifecycle and task dispatching
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import config
from .api.agents import router as agents_router
from .api.tasks import router as tasks_router
from .api.tools import router as tools_router
from .manager.agent_manager import agent_manager
from .manager.ws_manager import ws_manager

logging.basicConfig(
    level=config.log_level,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle for the gateway."""
    logger.info("Starting gateway...")
    await ws_manager.start_server(config.ws_host, config.ws_port)
    logger.info(f"Agent WebSocket server at {config.ws_url}")
    yield
    # Shutdown: stop all agents and WS server
    logger.info("Shutting down gateway...")
    await agent_manager.shutdown_all()
    await ws_manager.stop_server()
    logger.info("Gateway stopped")


app = FastAPI(
    title="CrewCraft Gateway",
    version="2.0.0",
    lifespan=lifespan,
)

app.include_router(agents_router)
app.include_router(tasks_router)
app.include_router(tools_router)


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "active_agents": ws_manager.active_agents,
    }


def start_gateway(host: str = None, port: int = None):
    """Entry point: start the gateway with uvicorn."""
    import uvicorn
    uvicorn.run(
        app,
        host=host or config.gateway_host,
        port=port or config.gateway_port,
        log_level=config.log_level.lower(),
    )
