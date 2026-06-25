"""网关 FastAPI 应用。

网关是中心枢纽：
- REST API 供 CLI / IM 平台客户端使用
- 内部 WebSocket 服务器供 Agent 进程连接
- 管理 Agent 生命周期和任务分派
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import config
from .api.agents import router as agents_router
from .api.tasks import router as tasks_router
from .api.tools import router as tools_router
from .api.approvals import router as approvals_router
from .manager.agent_manager import agent_manager
from .manager.ws_manager import ws_manager

logging.basicConfig(
    level=config.log_level,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """网关的启动和关闭生命周期。"""
    logger.info("Starting gateway...")
    await ws_manager.start_server(config.ws_host, config.ws_port)
    logger.info(f"Agent WebSocket server at {config.ws_url}")

    from .orchestrator import get_orchestrator
    get_orchestrator(agent_manager, ws_manager)

    # 启动 Channels（IM 平台）
    from app.channels import channel_manager
    asyncio.create_task(channel_manager.start_all())

    yield
    logger.info("Shutting down gateway...")
    await channel_manager.stop_all()
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
app.include_router(approvals_router)


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "active_agents": ws_manager.active_agents,
    }


def start_gateway(host: str = None, port: int = None):
    """入口点：使用 uvicorn 启动网关。"""
    import uvicorn
    uvicorn.run(
        app,
        host=host or config.gateway_host,
        port=port or config.gateway_port,
        log_level=config.log_level.lower(),
    )
