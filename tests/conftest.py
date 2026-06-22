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
    from app.models.orm import Agent, Task
    async with async_session() as db:
        await db.execute(text("DELETE FROM agents"))
        await db.execute(text("DELETE FROM tasks"))
        await db.commit()


@pytest_asyncio.fixture
async def client():
    """Async HTTP client for testing the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class _FakeMessage:
    """Simulates openai.types.chat.ChatCompletionMessage."""
    def __init__(self, content="Mock LLM response for testing.", tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls


class _FakeDelta:
    """Simulates the delta in a streaming chunk."""
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or []


class _FakeChunkChoice:
    def __init__(self, delta):
        self.delta = delta


class _FakeChunk:
    """Simulates a streaming chunk from the OpenAI SDK."""
    def __init__(self, content=None, tool_calls=None):
        self.choices = [_FakeChunkChoice(_FakeDelta(content=content, tool_calls=tool_calls))] if (content or tool_calls) else []


@pytest.fixture
def mock_llm():
    """Fixture that mocks LLM calls — covers both our LLM Manager and CrewAI's AsyncOpenAI."""
    from unittest.mock import patch, AsyncMock, MagicMock
    from app.llm.manager import llm
    import openai

    async def fake_completion(messages, model=None, temperature=0.7, max_tokens=4096):
        return "Mock LLM response for testing."

    async def fake_raw_completion(messages, model=None, temperature=0.7, max_tokens=4096, tools=None):
        return _FakeMessage()

    async def fake_stream(messages, model=None, temperature=0.7, max_tokens=4096):
        for chunk in ["Mock ", "streamed ", "response."]:
            yield chunk

    async def fake_raw_stream(messages, model=None, temperature=0.7, max_tokens=4096, tools=None):
        for content in ["Mock ", "streamed ", "response."]:
            yield _FakeChunk(content=content)

    # Mock the AsyncOpenAI client that CrewAI uses internally
    mock_openai_client = MagicMock()
    mock_completions = MagicMock()
    mock_openai_client.chat = MagicMock()
    mock_openai_client.chat.completions = mock_completions

    # Mock async create (non-streaming)
    mock_msg = MagicMock()
    mock_msg.content = "Mock CrewAI LLM response for testing."
    mock_msg.tool_calls = None
    mock_choice = MagicMock()
    mock_choice.message = mock_msg
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    async def fake_crewai_create(*args, **kwargs):
        if kwargs.get("stream"):
            return _FakeAsyncStream(kwargs.get("messages", []))
        return mock_response

    mock_completions.create = fake_crewai_create

    def fake_openai_client(*args, **kwargs):
        return mock_openai_client

    with patch.object(llm, "chat_completion", side_effect=fake_completion), \
         patch.object(llm, "chat_completion_stream", side_effect=fake_stream), \
         patch.object(llm, "chat_completion_raw", side_effect=fake_raw_completion), \
         patch.object(llm, "chat_completion_stream_raw", side_effect=fake_raw_stream), \
         patch("openai.AsyncOpenAI", side_effect=fake_openai_client):
        yield


class _FakeAsyncStream:
    """Simulates an async streaming response from OpenAI."""
    def __init__(self, messages):
        self._chunks = [
            _FakeChunk(content="Mock "),
            _FakeChunk(content="CrewAI "),
            _FakeChunk(content="streamed "),
            _FakeChunk(content="response."),
        ]
        self._index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._index >= len(self._chunks):
            raise StopAsyncIteration
        chunk = self._chunks[self._index]
        self._index += 1
        return chunk
