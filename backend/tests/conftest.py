import os
import sys
from pathlib import Path

# Override settings BEFORE any app code is imported
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///test_crewcraft.db"
os.environ["WORKSPACE_ROOT"] = "./test_workspace"

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

# Now safe to import app
from app.database import engine, async_session, init_db
from app.main import app
from app.models.orm import Base


@pytest_asyncio.fixture(scope="session", autouse=True)
async def global_setup():
    """Create test DB tables once per session, clean up at end."""
    await init_db()
    yield
    # Drop all tables and clean up files
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

    # Remove test files
    db_file = Path("test_crewcraft.db")
    if db_file.exists():
        db_file.unlink()

    ws_dir = Path("test_workspace")
    if ws_dir.exists():
        import shutil
        shutil.rmtree(ws_dir)


@pytest_asyncio.fixture(autouse=True)
async def cleanup_data():
    """Clean all table data between tests, preserve workspace dirs."""
    yield
    from app.models.orm import Agent, Task, Crew
    async with async_session() as db:
        await db.execute(text("DELETE FROM agents"))
        await db.execute(text("DELETE FROM tasks"))
        await db.execute(text("DELETE FROM crews"))
        await db.commit()


@pytest_asyncio.fixture
async def client():
    """Async HTTP client for testing the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_llm():
    """Fixture that patches LLM calls to return canned responses."""
    from unittest.mock import AsyncMock, patch

    async def fake_completion(messages, model=None, temperature=0.7, max_tokens=4096):
        return "Mock LLM response for testing."

    async def fake_stream(messages, model=None, temperature=0.7, max_tokens=4096):
        for chunk in ["Mock ", "streamed ", "response."]:
            yield chunk

    with patch("app.llm.deepseek.chat_completion", side_effect=fake_completion), \
         patch("app.llm.deepseek.chat_completion_stream", side_effect=fake_stream), \
         patch("app.engine.agent_loop.chat_completion", side_effect=fake_completion), \
         patch("app.engine.agent_loop.chat_completion_stream", side_effect=fake_stream), \
         patch("app.ws.manager.chat_completion_stream", side_effect=fake_stream), \
         patch("app.engine.workflows.hierarchical.chat_completion", side_effect=fake_completion), \
         patch("app.engine.workflows.roundtable.chat_completion", side_effect=fake_completion):
        yield
