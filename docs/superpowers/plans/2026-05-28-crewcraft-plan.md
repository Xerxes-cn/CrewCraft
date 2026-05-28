# CrewCraft Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a multi-agent collaboration platform with Web UI + CLI, where users configure agent crews through a visual interface and LangGraph orchestrates agent workflows powered by DeepSeek.

**Architecture:** FastAPI backend serves REST/WebSocket APIs, LangGraph compiles UI config into agent collaboration graphs, React frontend provides visual crew management and real-time task monitoring, CLI tool allows terminal-based execution.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy (async + aiosqlite), LangGraph, DeepSeek API (via openai SDK), React 18 + Vite + Zustand + React Router, Typer

---

## File Structure

```
CrewCraft/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app, CORS, lifespan
│   │   ├── config.py            # Settings via pydantic-settings
│   │   ├── database.py          # Async SQLAlchemy engine + session
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   └── orm.py           # Crew, Agent, Task SQLAlchemy models
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   └── api.py           # Pydantic request/response schemas
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── crews.py         # Crew CRUD routes
│   │   │   ├── agents.py        # Agent CRUD routes
│   │   │   └── tasks.py         # Task run + history routes
│   │   ├── engine/
│   │   │   ├── __init__.py
│   │   │   ├── compiler.py      # Config → LangGraph StateGraph
│   │   │   ├── agent_loop.py    # Single agent LLM invocation
│   │   │   └── workflows/
│   │   │       ├── __init__.py
│   │   │       ├── sequential.py
│   │   │       ├── hierarchical.py
│   │   │       └── roundtable.py
│   │   ├── llm/
│   │   │   ├── __init__.py
│   │   │   └── deepseek.py      # DeepSeek API client wrapper
│   │   └── ws/
│   │       ├── __init__.py
│   │       └── manager.py       # WebSocket connection manager
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── api/
│       │   └── client.ts        # Backend API fetch wrapper
│       ├── store/
│       │   └── index.ts         # Zustand stores
│       ├── components/
│       │   ├── Layout.tsx
│       │   ├── AgentCard.tsx
│       │   ├── AgentForm.tsx
│       │   ├── WorkflowConfig.tsx
│       │   └── MessageList.tsx
│       └── pages/
│           ├── CrewList.tsx
│           ├── CrewDetail.tsx
│           ├── CrewRun.tsx
│           └── TaskDetail.tsx
├── cli/
│   ├── main.py                  # Typer CLI entry
│   └── client.py                # HTTP client for backend API
└── docker-compose.yml
```

---

### Task 1: Backend Scaffolding

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`
- Create: `backend/app/database.py`
- Create: `backend/app/main.py`

- [ ] **Step 1: Create requirements.txt**

```
fastapi>=0.110.0
uvicorn[standard]>=0.27.0
sqlalchemy[asyncio]>=2.0.25
aiosqlite>=0.19.0
pydantic>=2.5.0
pydantic-settings>=2.1.0
langgraph>=0.0.40
openai>=1.12.0
typer>=0.9.0
httpx>=0.26.0
```

- [ ] **Step 2: Create app/__init__.py**

Empty file.

- [ ] **Step 3: Create app/config.py**

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///crewcraft.db"
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
```

- [ ] **Step 4: Create app/database.py**

```python
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
```

- [ ] **Step 5: Create app/main.py**

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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


@app.get("/api/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 6: Verify backend starts**

Run: `cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload`
Expected: App starts, `GET /api/health` returns `{"status": "ok"}`

- [ ] **Step 7: Commit**

```bash
git add backend/
git commit -m "feat: scaffold backend with FastAPI, config, and database setup"
```

---

### Task 2: Database Models

**Files:**
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/models/orm.py`

- [ ] **Step 1: Create models/__init__.py**

Empty file.

- [ ] **Step 2: Create models/orm.py**

```python
import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Crew(Base):
    __tablename__ = "crews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    workflow_type: Mapped[str] = mapped_column(String(50), nullable=False, default="sequential")
    workflow_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    agents: Mapped[list["Agent"]] = relationship(
        "Agent", back_populates="crew", cascade="all, delete-orphan", order_by="Agent.order"
    )
    tasks: Mapped[list["Task"]] = relationship(
        "Task", back_populates="crew", cascade="all, delete-orphan"
    )


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    crew_id: Mapped[int] = mapped_column(ForeignKey("crews.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(500), nullable=False)
    system_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tools: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=list)
    model_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    depends_on: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=list)

    crew: Mapped["Crew"] = relationship("Crew", back_populates="agents")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    crew_id: Mapped[int] = mapped_column(ForeignKey("crews.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    input: Mapped[str] = mapped_column(Text, nullable=False)
    messages: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=list)
    result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    crew: Mapped["Crew"] = relationship("Crew", back_populates="tasks")
```

- [ ] **Step 3: Register models in database.py**

Edit `backend/app/database.py` — add import before `Base` usage:

```python
# Add after the Base class definition, before get_db:
import app.models.orm  # noqa: F401 - register models
```

- [ ] **Step 4: Verify models create tables**

Run: `cd backend && python -c "import asyncio; from app.database import init_db; asyncio.run(init_db())"`
Expected: `crewcraft.db` file created with three tables

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/ backend/app/database.py backend/crewcraft.db
git commit -m "feat: add Crew, Agent, Task database models"
```

---

### Task 3: DeepSeek LLM Client

**Files:**
- Create: `backend/app/llm/__init__.py`
- Create: `backend/app/llm/deepseek.py`

- [ ] **Step 1: Create llm/__init__.py**

Empty file.

- [ ] **Step 2: Create llm/deepseek.py**

```python
from openai import AsyncOpenAI

from app.config import settings

client = AsyncOpenAI(
    api_key=settings.deepseek_api_key,
    base_url=settings.deepseek_base_url,
)


async def chat_completion(
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> str:
    response = await client.chat.completions.create(
        model=model or settings.deepseek_model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content or ""


async def chat_completion_stream(
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
):
    stream = await client.chat.completions.create(
        model=model or settings.deepseek_model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
    )
    async for chunk in stream:
        if chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/llm/
git commit -m "feat: add DeepSeek LLM client with streaming support"
```

---

### Task 4: Agent Loop

**Files:**
- Create: `backend/app/engine/__init__.py`
- Create: `backend/app/engine/agent_loop.py`

- [ ] **Step 1: Create engine/__init__.py**

Empty file.

- [ ] **Step 2: Create engine/agent_loop.py**

```python
from collections.abc import AsyncGenerator

from app.llm.deepseek import chat_completion, chat_completion_stream


def build_messages(agent: dict, task_input: str, context: str = "") -> list[dict]:
    system_content = agent.get("system_prompt") or f"You are {agent['name']}, a {agent['role']}."
    messages = [{"role": "system", "content": system_content}]

    if context:
        messages.append({"role": "user", "content": f"Context from previous step:\n{context}"})

    messages.append({"role": "user", "content": task_input})
    return messages


async def run_agent(agent: dict, task_input: str, context: str = "") -> dict:
    messages = build_messages(agent, task_input, context)
    model_config = agent.get("model_config") or {}
    response = await chat_completion(
        messages=messages,
        temperature=model_config.get("temperature", 0.7),
        max_tokens=model_config.get("max_tokens", 4096),
    )
    return {"agent_name": agent["name"], "agent_role": agent["role"], "content": response}


async def run_agent_stream(
    agent: dict, task_input: str, context: str = ""
) -> AsyncGenerator[dict, None]:
    messages = build_messages(agent, task_input, context)
    model_config = agent.get("model_config") or {}
    full_response = ""
    async for chunk in chat_completion_stream(
        messages=messages,
        temperature=model_config.get("temperature", 0.7),
        max_tokens=model_config.get("max_tokens", 4096),
    ):
        full_response += chunk
        yield {"type": "chunk", "agent_name": agent["name"], "content": chunk}

    yield {"type": "done", "agent_name": agent["name"], "agent_role": agent["role"], "content": full_response}
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/engine/
git commit -m "feat: add agent loop with LLM invocation and streaming"
```

---

### Task 5: Workflow Implementations + Compiler

**Files:**
- Create: `backend/app/engine/workflows/__init__.py`
- Create: `backend/app/engine/workflows/sequential.py`
- Create: `backend/app/engine/workflows/hierarchical.py`
- Create: `backend/app/engine/workflows/roundtable.py`
- Create: `backend/app/engine/compiler.py`

- [ ] **Step 1: Create workflows/__init__.py**

Empty file.

- [ ] **Step 2: Create workflows/sequential.py**

```python
import json
from typing import Any

from langgraph.graph import StateGraph, END


class SequentialState(dict):
    task_input: str
    messages: list
    current_index: int
    agents: list
    final_result: str


async def run_agent_node(state: SequentialState) -> SequentialState:
    from app.engine.agent_loop import run_agent
    from app.models.orm import Agent

    agents = state["agents"]
    idx = state["current_index"]
    if idx >= len(agents):
        return state

    agent = agents[idx]
    result = await run_agent(agent, state["task_input"], state.get("final_result", ""))
    state["messages"].append(result)
    state["final_result"] = result["content"]
    state["current_index"] = idx + 1
    return state


def should_continue(state: SequentialState) -> str:
    if state["current_index"] >= len(state["agents"]):
        return "end"
    return "next"


def build_sequential_graph(agents: list[dict]) -> StateGraph:
    graph = StateGraph(SequentialState)
    graph.add_node("agent", run_agent_node)

    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", should_continue, {"next": "agent", "end": END})

    return graph.compile()
```

- [ ] **Step 3: Create workflows/hierarchical.py**

```python
from typing import Any

from langgraph.graph import StateGraph, END


class HierarchicalState(dict):
    task_input: str
    messages: list
    agents: list
    plan: list
    final_result: str


async def leader_node(state: HierarchicalState) -> HierarchicalState:
    from app.llm.deepseek import chat_completion

    agents = state["agents"]
    agent_descriptions = [f"- {a['name']} ({a['role']})" for a in agents]

    plan_prompt = f"""You are a team leader. Based on the task, create a plan delegating work to team members.

Available team members:
{chr(10).join(agent_descriptions)}

Task: {state['task_input']}

Respond in JSON format:
{{"plan": [{{"agent_index": 0, "instruction": "what to do"}}, ...]}}"""

    response = await chat_completion(
        messages=[{"role": "user", "content": plan_prompt}],
        temperature=0.3,
    )

    try:
        plan_data = json.loads(response)
        state["plan"] = plan_data.get("plan", [])
    except json.JSONDecodeError:
        state["plan"] = [{"agent_index": 0, "instruction": state["task_input"]}]

    state["messages"].append({"agent_name": "Leader", "agent_role": "Leader", "content": response})
    return state


async def worker_node(state: HierarchicalState) -> HierarchicalState:
    from app.engine.agent_loop import run_agent

    if not state["plan"]:
        return state

    step = state["plan"].pop(0)
    agent_data = state["agents"][step["agent_index"]]

    result = await run_agent(
        agent_data,
        step["instruction"],
        state.get("final_result", ""),
    )
    state["messages"].append(result)
    state["final_result"] = result["content"]
    return state


def should_continue_plan(state: HierarchicalState) -> str:
    return "worker" if state["plan"] else "end"


def build_hierarchical_graph(agents: list[dict]) -> StateGraph:
    graph = StateGraph(HierarchicalState)
    graph.add_node("leader", leader_node)
    graph.add_node("worker", worker_node)

    graph.set_entry_point("leader")
    graph.add_edge("leader", "worker")
    graph.add_conditional_edges("worker", should_continue_plan, {"worker": "worker", "end": END})

    return graph.compile()
```

- [ ] **Step 4: Create workflows/roundtable.py**

```python
from typing import Any

from langgraph.graph import StateGraph, END


class RoundtableState(dict):
    task_input: str
    messages: list
    agents: list
    current_round: int
    max_rounds: int
    final_result: str


async def discuss_node(state: RoundtableState) -> RoundtableState:
    from app.engine.agent_loop import run_agent
    from app.llm.deepseek import chat_completion

    agents = state["agents"]
    discussion = "\n".join(
        [m["content"] for m in state["messages"] if isinstance(m, dict) and "content" in m]
    )

    discussion_context = ""
    if discussion:
        discussion_context = f"Previous discussion:\n{discussion}\n\n"

    for agent in agents:
        prompt = f"{discussion_context}Task: {state['task_input']}\n\nShare your perspective on this task."
        result = await run_agent(agent, prompt)
        state["messages"].append(result)

    state["current_round"] += 1

    if state["current_round"] >= state["max_rounds"]:
        summary_prompt = f"Based on the discussion, summarize the consensus:\n{discussion}"
        summary = await chat_completion(
            messages=[{"role": "user", "content": summary_prompt}],
            temperature=0.3,
        )
        state["final_result"] = summary
        state["messages"].append(
            {"agent_name": "Summary", "agent_role": "Summarizer", "content": summary}
        )

    return state


def should_continue_roundtable(state: RoundtableState) -> str:
    return "end" if state["current_round"] >= state["max_rounds"] else "discuss"


def build_roundtable_graph(agents: list[dict], max_rounds: int = 2) -> StateGraph:
    graph = StateGraph(RoundtableState)
    graph.add_node("discuss", discuss_node)

    graph.set_entry_point("discuss")
    graph.add_conditional_edges("discuss", should_continue_roundtable, {"discuss": "discuss", "end": END})

    return graph.compile()
```

- [ ] **Step 5: Create compiler.py**

```python
from langgraph.graph import StateGraph

from app.engine.workflows.sequential import build_sequential_graph
from app.engine.workflows.hierarchical import build_hierarchical_graph
from app.engine.workflows.roundtable import build_roundtable_graph
from app.models.orm import Crew


def compile_crew_graph(crew: Crew) -> StateGraph:
    agents_data = [
        {
            "id": a.id,
            "name": a.name,
            "role": a.role,
            "system_prompt": a.system_prompt,
            "tools": a.tools or [],
            "model_config": a.model_config or {},
            "order": a.order,
        }
        for a in crew.agents
    ]

    workflow_type = crew.workflow_type
    if workflow_type == "sequential":
        return build_sequential_graph(agents_data)
    elif workflow_type == "hierarchical":
        return build_hierarchical_graph(agents_data)
    elif workflow_type == "roundtable":
        max_rounds = (crew.workflow_config or {}).get("max_rounds", 2)
        return build_roundtable_graph(agents_data, max_rounds)
    else:
        raise ValueError(f"Unknown workflow type: {workflow_type}")
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/engine/workflows/ backend/app/engine/compiler.py
git commit -m "feat: add sequential, hierarchical, roundtable workflows and compiler"
```

---

### Task 6: API Schemas

**Files:**
- Create: `backend/app/schemas/__init__.py`
- Create: `backend/app/schemas/api.py`

- [ ] **Step 1: Create schemas/__init__.py**

Empty file.

- [ ] **Step 2: Create schemas/api.py**

```python
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


# --- Crew ---

class CrewCreate(BaseModel):
    name: str
    description: Optional[str] = None
    workflow_type: str = "sequential"
    workflow_config: Optional[dict] = None


class CrewUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    workflow_type: Optional[str] = None
    workflow_config: Optional[dict] = None


class CrewResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    workflow_type: str
    workflow_config: Optional[dict]
    created_at: datetime
    agents: list["AgentResponse"] = []

    class Config:
        from_attributes = True


# --- Agent ---

class AgentCreate(BaseModel):
    name: str
    role: str
    system_prompt: Optional[str] = None
    tools: Optional[list] = None
    model_config: Optional[dict] = None
    order: int = 0
    depends_on: Optional[list] = None


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    system_prompt: Optional[str] = None
    tools: Optional[list] = None
    model_config: Optional[dict] = None
    order: Optional[int] = None
    depends_on: Optional[list] = None


class AgentResponse(BaseModel):
    id: int
    crew_id: int
    name: str
    role: str
    system_prompt: Optional[str]
    tools: Optional[list]
    model_config: Optional[dict]
    order: int
    depends_on: Optional[list]

    class Config:
        from_attributes = True


# --- Task ---

class TaskRunRequest(BaseModel):
    input: str


class TaskResponse(BaseModel):
    id: int
    crew_id: int
    status: str
    input: str
    messages: Optional[list]
    result: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/schemas/
git commit -m "feat: add Pydantic API schemas for Crew, Agent, Task"
```

---

### Task 7: Crew + Agent API Routes

**Files:**
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/crews.py`
- Create: `backend/app/api/agents.py`

- [ ] **Step 1: Create api/__init__.py**

Empty file.

- [ ] **Step 2: Create api/crews.py**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.orm import Crew
from app.schemas.api import CrewCreate, CrewResponse, CrewUpdate

router = APIRouter(prefix="/api/crews", tags=["crews"])


@router.post("", response_model=CrewResponse, status_code=201)
async def create_crew(data: CrewCreate, db: AsyncSession = Depends(get_db)):
    crew = Crew(**data.model_dump())
    db.add(crew)
    await db.commit()
    await db.refresh(crew)
    return crew


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
    await db.delete(crew)
    await db.commit()
```

- [ ] **Step 3: Create api/agents.py**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.orm import Crew, Agent
from app.schemas.api import AgentCreate, AgentResponse, AgentUpdate

router = APIRouter(prefix="/api/agents", tags=["agents"])


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


@router.put("/{agent_id}", response_model=AgentResponse)
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


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(agent_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    await db.delete(agent)
    await db.commit()
```

- [ ] **Step 4: Register routes in main.py**

Edit `backend/app/main.py` — add after middleware and before health endpoint:

```python
from app.api.crews import router as crews_router
from app.api.agents import router as agents_router

app.include_router(crews_router)
app.include_router(agents_router)
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/ backend/app/main.py
git commit -m "feat: add Crew and Agent CRUD API routes"
```

---

### Task 8: WebSocket Manager + Task Execution

**Files:**
- Create: `backend/app/ws/__init__.py`
- Create: `backend/app/ws/manager.py`
- Create: `backend/app/api/tasks.py`

- [ ] **Step 1: Create ws/__init__.py**

Empty file.

- [ ] **Step 2: Create ws/manager.py**

```python
import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self._connections: dict[int, list[WebSocket]] = {}

    async def connect(self, crew_id: int, ws: WebSocket):
        await ws.accept()
        self._connections.setdefault(crew_id, []).append(ws)

    def disconnect(self, crew_id: int, ws: WebSocket):
        if crew_id in self._connections:
            self._connections[crew_id].remove(ws)

    async def broadcast(self, crew_id: int, data: dict):
        for ws in self._connections.get(crew_id, []):
            try:
                await ws.send_json(data)
            except Exception:
                pass


manager = ConnectionManager()


async def stream_workflow(
    crew_id: int,
    task_id: int,
    compiled_graph,
    initial_state: dict,
) -> AsyncGenerator[dict, None]:
    full_messages: list[dict] = []

    async for event in compiled_graph.astream(initial_state):
        for node_name, node_output in event.items():
            if isinstance(node_output, dict) and "messages" in node_output:
                new_messages = node_output["messages"][len(full_messages):]
                for msg in new_messages:
                    full_messages.append(msg)
                    event_data = {
                        "type": "agent_message",
                        "task_id": task_id,
                        "data": msg,
                    }
                    await manager.broadcast(crew_id, event_data)
                    yield event_data

    final = {
        "type": "workflow_complete",
        "task_id": task_id,
        "final_result": node_output.get("final_result", ""),
        "messages": full_messages,
    }
    await manager.broadcast(crew_id, final)
    yield final
```

- [ ] **Step 3: Create api/tasks.py**

```python
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.engine.compiler import compile_crew_graph
from app.models.orm import Crew, Task
from app.schemas.api import TaskResponse, TaskRunRequest
from app.ws.manager import manager, stream_workflow

router = APIRouter(tags=["tasks"])


@router.post("/api/crews/{crew_id}/run", response_model=TaskResponse, status_code=201)
async def run_task(crew_id: int, data: TaskRunRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Crew).options(selectinload(Crew.agents)).where(Crew.id == crew_id)
    )
    crew = result.scalar_one_or_none()
    if not crew:
        raise HTTPException(status_code=404, detail="Crew not found")
    if not crew.agents:
        raise HTTPException(status_code=400, detail="Crew has no agents")

    task = Task(crew_id=crew_id, input=data.input, status="running")
    db.add(task)
    await db.commit()
    await db.refresh(task)

    graph = compile_crew_graph(crew)
    initial_state = {
        "task_input": data.input,
        "messages": [],
        "agents": crew.agents,
        "current_index": 0,
        "final_result": "",
        "current_round": 0,
        "max_rounds": (crew.workflow_config or {}).get("max_rounds", 2),
        "plan": [],
    }

    all_messages = []
    final_result = ""
    async for event in stream_workflow(crew_id, task.id, graph, initial_state):
        if event["type"] == "workflow_complete":
            final_result = event.get("final_result", "")
            all_messages = event.get("messages", [])

    task.status = "completed"
    task.messages = all_messages
    task.result = final_result
    await db.commit()
    await db.refresh(task)

    return task


@router.websocket("/api/crews/{crew_id}/stream")
async def stream_endpoint(ws: WebSocket, crew_id: int):
    await manager.connect(crew_id, ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(crew_id, ws)


@router.get("/api/crews/{crew_id}/tasks", response_model=list[TaskResponse])
async def list_tasks(crew_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Task)
        .where(Task.crew_id == crew_id)
        .order_by(Task.created_at.desc())
        .limit(50)
    )
    return result.scalars().all()


@router.get("/api/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task
```

- [ ] **Step 4: Register tasks router in main.py**

Edit `backend/app/main.py` — add:

```python
from app.api.tasks import router as tasks_router

app.include_router(tasks_router)
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/ws/ backend/app/api/tasks.py backend/app/main.py
git commit -m "feat: add WebSocket manager and task execution endpoints"
```

---

### Task 9: Frontend Scaffolding

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/index.html`
- Create: `frontend/tsconfig.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/store/index.ts`

- [ ] **Step 1: Create package.json**

```json
{
  "name": "crewcraft-frontend",
  "private": true,
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.22.0",
    "zustand": "^4.5.0"
  },
  "devDependencies": {
    "@types/react": "^18.3.1",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.2.1",
    "typescript": "^5.4.0",
    "vite": "^5.4.0"
  }
}
```

- [ ] **Step 2: Create index.html**

```html
<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>CrewCraft</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 3: Create tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true
  },
  "include": ["src"]
}
```

- [ ] **Step 4: Create vite.config.ts**

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        ws: true,
      },
    },
  },
})
```

- [ ] **Step 5: Create src/api/client.ts**

```typescript
const BASE = '/api';

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export interface Crew {
  id: number;
  name: string;
  description: string | null;
  workflow_type: string;
  workflow_config: Record<string, unknown> | null;
  created_at: string;
  agents: Agent[];
}

export interface Agent {
  id: number;
  crew_id: number;
  name: string;
  role: string;
  system_prompt: string | null;
  tools: unknown[] | null;
  model_config: Record<string, unknown> | null;
  order: number;
  depends_on: number[] | null;
}

export interface Task {
  id: number;
  crew_id: number;
  status: string;
  input: string;
  messages: unknown[] | null;
  result: string | null;
  created_at: string;
}

export const api = {
  // Crews
  listCrews: () => request<Crew[]>('/crews'),
  getCrew: (id: number) => request<Crew>(`/crews/${id}`),
  createCrew: (data: Partial<Crew>) => request<Crew>('/crews', { method: 'POST', body: JSON.stringify(data) }),
  updateCrew: (id: number, data: Partial<Crew>) => request<Crew>(`/crews/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteCrew: (id: number) => request<void>(`/crews/${id}`, { method: 'DELETE' }),

  // Agents
  createAgent: (crewId: number, data: Partial<Agent>) =>
    request<Agent>(`/crews/${crewId}/agents`, { method: 'POST', body: JSON.stringify(data) }),
  updateAgent: (id: number, data: Partial<Agent>) =>
    request<Agent>(`/agents/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteAgent: (id: number) => request<void>(`/agents/${id}`, { method: 'DELETE' }),

  // Tasks
  runTask: (crewId: number, input: string) =>
    request<Task>(`/crews/${crewId}/run`, { method: 'POST', body: JSON.stringify({ input }) }),
  listTasks: (crewId: number) => request<Task[]>(`/crews/${crewId}/tasks`),
  getTask: (taskId: number) => request<Task>(`/tasks/${taskId}`),
};
```

- [ ] **Step 6: Create src/store/index.ts**

```typescript
import { create } from 'zustand';
import type { Crew, Task } from '../api/client';

interface CrewStore {
  crews: Crew[];
  setCrews: (crews: Crew[]) => void;
  selectedCrew: Crew | null;
  setSelectedCrew: (crew: Crew | null) => void;
}

export const useCrewStore = create<CrewStore>((set) => ({
  crews: [],
  setCrews: (crews) => set({ crews }),
  selectedCrew: null,
  setSelectedCrew: (crew) => set({ selectedCrew: crew }),
}));

interface TaskStore {
  messages: Array<{ agent_name: string; agent_role: string; content: string }>;
  addMessage: (msg: { agent_name: string; agent_role: string; content: string }) => void;
  setMessages: (msgs: Array<{ agent_name: string; agent_role: string; content: string }>) => void;
  running: boolean;
  setRunning: (running: boolean) => void;
}

export const useTaskStore = create<TaskStore>((set) => ({
  messages: [],
  addMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),
  setMessages: (msgs) => set({ messages: msgs }),
  running: false,
  setRunning: (running) => set({ running }),
}));
```

- [ ] **Step 7: Create src/main.tsx**

```typescript
import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>
);
```

- [ ] **Step 8: Create src/App.tsx**

```typescript
import { Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import CrewList from './pages/CrewList';
import CrewDetail from './pages/CrewDetail';
import CrewRun from './pages/CrewRun';
import TaskDetail from './pages/TaskDetail';

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<CrewList />} />
        <Route path="/crews/:id" element={<CrewDetail />} />
        <Route path="/crews/:id/run" element={<CrewRun />} />
        <Route path="/tasks/:id" element={<TaskDetail />} />
      </Route>
    </Routes>
  );
}
```

- [ ] **Step 9: Verify frontend starts**

Run: `cd frontend && npm install && npm run dev`
Expected: Dev server starts on port 5173

- [ ] **Step 10: Commit**

```bash
git add frontend/
git commit -m "feat: scaffold React frontend with Vite, Zustand, and routing"
```

---

### Task 10: Frontend Components

**Files:**
- Create: `frontend/src/components/Layout.tsx`
- Create: `frontend/src/components/AgentCard.tsx`
- Create: `frontend/src/components/AgentForm.tsx`
- Create: `frontend/src/components/WorkflowConfig.tsx`
- Create: `frontend/src/components/MessageList.tsx`

- [ ] **Step 1: Create Layout.tsx**

```typescript
import { Link, Outlet } from 'react-router-dom';

export default function Layout() {
  return (
    <div style={{ maxWidth: 960, margin: '0 auto', padding: 24 }}>
      <header style={{ marginBottom: 24 }}>
        <h1>
          <Link to="/" style={{ textDecoration: 'none', color: '#1a1a2e' }}>
            CrewCraft
          </Link>
        </h1>
      </header>
      <main>
        <Outlet />
      </main>
    </div>
  );
}
```

- [ ] **Step 2: Create AgentCard.tsx**

```typescript
import type { Agent } from '../api/client';

interface Props {
  agent: Agent;
  onDelete: (id: number) => void;
}

const cardStyle: React.CSSProperties = {
  border: '1px solid #e0e0e0',
  borderRadius: 8,
  padding: 16,
  marginBottom: 12,
};

export default function AgentCard({ agent, onDelete }: Props) {
  return (
    <div style={cardStyle}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <strong>{agent.name}</strong>
          <span style={{ color: '#888', marginLeft: 8 }}>{agent.role}</span>
        </div>
        <button onClick={() => onDelete(agent.id)} style={btnDanger}>Delete</button>
      </div>
      {agent.system_prompt && (
        <p style={{ color: '#666', fontSize: 14, marginTop: 8 }}>{agent.system_prompt}</p>
      )}
    </div>
  );
}

const btnDanger: React.CSSProperties = {
  background: '#e74c3c',
  color: '#fff',
  border: 'none',
  borderRadius: 4,
  padding: '4px 12px',
  cursor: 'pointer',
};
```

- [ ] **Step 3: Create AgentForm.tsx**

```typescript
import { useState, type FormEvent } from 'react';

interface Props {
  onSubmit: (data: { name: string; role: string; system_prompt: string; order: number }) => void;
}

const formStyle: React.CSSProperties = {
  border: '1px solid #e0e0e0',
  borderRadius: 8,
  padding: 16,
  marginBottom: 16,
};

const fieldStyle: React.CSSProperties = {
  display: 'block',
  width: '100%',
  padding: '8px 12px',
  marginBottom: 12,
  border: '1px solid #ddd',
  borderRadius: 4,
  fontSize: 14,
  boxSizing: 'border-box',
};

const btnPrimary: React.CSSProperties = {
  background: '#3498db',
  color: '#fff',
  border: 'none',
  borderRadius: 4,
  padding: '8px 20px',
  cursor: 'pointer',
  fontSize: 14,
};

export default function AgentForm({ onSubmit }: Props) {
  const [name, setName] = useState('');
  const [role, setRole] = useState('');
  const [systemPrompt, setSystemPrompt] = useState('');
  const [order, setOrder] = useState(0);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    onSubmit({ name, role, system_prompt: systemPrompt, order });
    setName('');
    setRole('');
    setSystemPrompt('');
    setOrder((n) => n + 1);
  };

  return (
    <form onSubmit={handleSubmit} style={formStyle}>
      <h3>Add Agent</h3>
      <input style={fieldStyle} placeholder="Name" value={name} onChange={(e) => setName(e.target.value)} required />
      <input style={fieldStyle} placeholder="Role (e.g. Researcher)" value={role} onChange={(e) => setRole(e.target.value)} required />
      <textarea
        style={{ ...fieldStyle, minHeight: 80 }}
        placeholder="System prompt (optional)"
        value={systemPrompt}
        onChange={(e) => setSystemPrompt(e.target.value)}
      />
      <button type="submit" style={btnPrimary}>Add Agent</button>
    </form>
  );
}
```

- [ ] **Step 4: Create WorkflowConfig.tsx**

```typescript
interface Props {
  workflowType: string;
  maxRounds: number;
  onChangeType: (type: string) => void;
  onChangeMaxRounds: (rounds: number) => void;
}

const selectStyle: React.CSSProperties = {
  padding: '8px 12px',
  border: '1px solid #ddd',
  borderRadius: 4,
  fontSize: 14,
  marginRight: 12,
};

const containerStyle: React.CSSProperties = {
  padding: 16,
  background: '#f8f9fa',
  borderRadius: 8,
  marginBottom: 16,
};

export default function WorkflowConfig({ workflowType, maxRounds, onChangeType, onChangeMaxRounds }: Props) {
  return (
    <div style={containerStyle}>
      <h3 style={{ marginTop: 0 }}>Workflow</h3>
      <label style={{ marginRight: 12 }}>
        Type:
        <select value={workflowType} onChange={(e) => onChangeType(e.target.value)} style={{ ...selectStyle, marginLeft: 8 }}>
          <option value="sequential">Sequential</option>
          <option value="hierarchical">Hierarchical</option>
          <option value="roundtable">Roundtable</option>
        </select>
      </label>
      {workflowType === 'roundtable' && (
        <label>
          Max rounds:
          <input
            type="number"
            min={1}
            max={5}
            value={maxRounds}
            onChange={(e) => onChangeMaxRounds(Number(e.target.value))}
            style={{ ...selectStyle, width: 60, marginLeft: 8 }}
          />
        </label>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Create MessageList.tsx**

```typescript
interface Message {
  agent_name: string;
  agent_role: string;
  content: string;
}

interface Props {
  messages: Message[];
  running: boolean;
}

const msgStyle: React.CSSProperties = {
  border: '1px solid #e0e0e0',
  borderRadius: 8,
  padding: 16,
  marginBottom: 12,
};

export default function MessageList({ messages, running }: Props) {
  return (
    <div>
      {messages.map((msg, i) => (
        <div key={i} style={msgStyle}>
          <div style={{ marginBottom: 8 }}>
            <strong>{msg.agent_name}</strong>
            <span style={{ color: '#888', marginLeft: 8, fontSize: 14 }}>{msg.agent_role}</span>
          </div>
          <p style={{ whiteSpace: 'pre-wrap', margin: 0, lineHeight: 1.6 }}>{msg.content}</p>
        </div>
      ))}
      {running && <p style={{ color: '#888' }}>Working...</p>}
    </div>
  );
}
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/
git commit -m "feat: add shared UI components"
```

---

### Task 11: Frontend Pages

**Files:**
- Create: `frontend/src/pages/CrewList.tsx`
- Create: `frontend/src/pages/CrewDetail.tsx`
- Create: `frontend/src/pages/CrewRun.tsx`
- Create: `frontend/src/pages/TaskDetail.tsx`

- [ ] **Step 1: Create CrewList.tsx**

```typescript
import { useEffect, useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, type Crew } from '../api/client';
import { useCrewStore } from '../store';

const cardStyle: React.CSSProperties = {
  border: '1px solid #e0e0e0',
  borderRadius: 8,
  padding: 16,
  marginBottom: 12,
  cursor: 'pointer',
};

const btnStyle: React.CSSProperties = {
  background: '#3498db',
  color: '#fff',
  border: 'none',
  borderRadius: 4,
  padding: '8px 20px',
  cursor: 'pointer',
  fontSize: 14,
};

const inputStyle: React.CSSProperties = {
  display: 'block',
  width: '100%',
  padding: '8px 12px',
  marginBottom: 12,
  border: '1px solid #ddd',
  borderRadius: 4,
  fontSize: 14,
  boxSizing: 'border-box',
};

export default function CrewList() {
  const { crews, setCrews } = useCrewStore();
  const navigate = useNavigate();
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [showForm, setShowForm] = useState(false);

  useEffect(() => {
    api.listCrews().then(setCrews).catch(console.error);
  }, [setCrews]);

  const handleCreate = async (e: FormEvent) => {
    e.preventDefault();
    const crew = await api.createCrew({ name, description });
    setCrews([crew, ...crews]);
    setName('');
    setDescription('');
    setShowForm(false);
  };

  const handleDelete = async (id: number) => {
    await api.deleteCrew(id);
    setCrews(crews.filter((c) => c.id !== id));
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <h2>Crews</h2>
        <button style={btnStyle} onClick={() => setShowForm(!showForm)}>
          {showForm ? 'Cancel' : 'New Crew'}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} style={{ marginBottom: 24, padding: 16, border: '1px solid #e0e0e0', borderRadius: 8 }}>
          <input style={inputStyle} placeholder="Crew name" value={name} onChange={(e) => setName(e.target.value)} required />
          <input style={inputStyle} placeholder="Description (optional)" value={description} onChange={(e) => setDescription(e.target.value)} />
          <button type="submit" style={btnStyle}>Create</button>
        </form>
      )}

      {crews.length === 0 && <p style={{ color: '#888' }}>No crews yet. Create one to get started.</p>}

      {crews.map((crew) => (
        <div key={crew.id} style={cardStyle} onClick={() => navigate(`/crews/${crew.id}`)}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <strong>{crew.name}</strong>
              <span style={{ color: '#888', marginLeft: 8, fontSize: 13 }}>{crew.workflow_type}</span>
            </div>
            <button
              onClick={(e) => { e.stopPropagation(); handleDelete(crew.id); }}
              style={{ background: '#e74c3c', color: '#fff', border: 'none', borderRadius: 4, padding: '4px 12px', cursor: 'pointer' }}
            >
              Delete
            </button>
          </div>
          {crew.description && <p style={{ color: '#666', fontSize: 14, marginTop: 8 }}>{crew.description}</p>}
          <p style={{ color: '#aaa', fontSize: 12, marginTop: 8 }}>
            {crew.agents.length} agent{crew.agents.length !== 1 ? 's' : ''}
          </p>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Create CrewDetail.tsx**

```typescript
import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api, type Crew } from '../api/client';
import AgentCard from '../components/AgentCard';
import AgentForm from '../components/AgentForm';
import WorkflowConfig from '../components/WorkflowConfig';

const btnStyle: React.CSSProperties = {
  background: '#2ecc71',
  color: '#fff',
  border: 'none',
  borderRadius: 4,
  padding: '10px 24px',
  cursor: 'pointer',
  fontSize: 15,
  marginTop: 16,
};

export default function CrewDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [crew, setCrew] = useState<Crew | null>(null);

  const load = () => {
    if (!id) return;
    api.getCrew(Number(id)).then(setCrew).catch(console.error);
  };

  useEffect(load, [id]);

  if (!crew) return <p>Loading...</p>;

  const handleAddAgent = async (data: { name: string; role: string; system_prompt: string; order: number }) => {
    await api.createAgent(crew.id, data);
    load();
  };

  const handleDeleteAgent = async (agentId: number) => {
    await api.deleteAgent(agentId);
    load();
  };

  const handleUpdateWorkflow = async (type: string, maxRounds?: number) => {
    const config = type === 'roundtable' ? { max_rounds: maxRounds || 2 } : null;
    const updated = await api.updateCrew(crew.id, {
      workflow_type: type,
      workflow_config: config,
    });
    setCrew(updated);
  };

  return (
    <div>
      <button onClick={() => navigate('/')} style={{ ...btnStyle, background: '#95a5a6', marginBottom: 16, marginTop: 0 }}>
        &larr; Back
      </button>

      <h2>{crew.name}</h2>
      {crew.description && <p style={{ color: '#666' }}>{crew.description}</p>}

      <WorkflowConfig
        workflowType={crew.workflow_type}
        maxRounds={(crew.workflow_config as Record<string, unknown>)?.max_rounds as number || 2}
        onChangeType={(type) => handleUpdateWorkflow(type)}
        onChangeMaxRounds={(rounds) => handleUpdateWorkflow(crew.workflow_type, rounds)}
      />

      <h3>Agents ({crew.agents.length})</h3>
      {crew.agents.map((agent) => (
        <AgentCard key={agent.id} agent={agent} onDelete={handleDeleteAgent} />
      ))}

      <AgentForm onSubmit={handleAddAgent} />

      {crew.agents.length > 0 && (
        <button style={btnStyle} onClick={() => navigate(`/crews/${crew.id}/run`)}>
          Run Task &rarr;
        </button>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Create CrewRun.tsx**

```typescript
import { useEffect, useState, useRef, type FormEvent } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api, type Crew, type Task } from '../api/client';
import MessageList from '../components/MessageList';

const inputStyle: React.CSSProperties = {
  display: 'block',
  width: '100%',
  padding: '12px',
  border: '1px solid #ddd',
  borderRadius: 8,
  fontSize: 15,
  boxSizing: 'border-box',
  marginBottom: 12,
};

const btnStyle: React.CSSProperties = {
  background: '#3498db',
  color: '#fff',
  border: 'none',
  borderRadius: 4,
  padding: '10px 24px',
  cursor: 'pointer',
  fontSize: 15,
};

export default function CrewRun() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [crew, setCrew] = useState<Crew | null>(null);
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<Array<{ agent_name: string; agent_role: string; content: string }>>([]);
  const [running, setRunning] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!id) return;
    api.getCrew(Number(id)).then(setCrew).catch(console.error);
  }, [id]);

  useEffect(() => {
    if (!id || !running) return;

    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const ws = new WebSocket(`${protocol}://${window.location.host}/api/crews/${id}/stream`);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'agent_message' && data.data) {
        setMessages((prev) => [...prev, data.data]);
      } else if (data.type === 'workflow_complete') {
        setRunning(false);
      }
    };

    ws.onerror = () => setRunning(false);

    return () => { ws.close(); };
  }, [id, running]);

  const handleRun = async (e: FormEvent) => {
    e.preventDefault();
    if (!input.trim() || !id) return;

    setMessages([]);
    setRunning(true);

    try {
      const task: Task = await api.runTask(Number(id), input);
      if (task.messages) {
        setMessages(task.messages as Array<{ agent_name: string; agent_role: string; content: string }>);
      }
    } catch (err) {
      console.error(err);
    }
    setRunning(false);
  };

  if (!crew) return <p>Loading...</p>;

  return (
    <div>
      <button onClick={() => navigate(`/crews/${id}`)} style={{ ...btnStyle, background: '#95a5a6', marginBottom: 16 }}>
        &larr; Back
      </button>

      <h2>Run: {crew.name}</h2>

      <form onSubmit={handleRun}>
        <input
          style={inputStyle}
          placeholder="Enter your task..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={running}
        />
        <button type="submit" style={btnStyle} disabled={running || !input.trim()}>
          {running ? 'Running...' : 'Run'}
        </button>
      </form>

      <div style={{ marginTop: 24 }}>
        <h3>Conversation</h3>
        <MessageList messages={messages} running={running} />
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Create TaskDetail.tsx**

```typescript
import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api, type Task } from '../api/client';
import MessageList from '../components/MessageList';

const btnStyle: React.CSSProperties = {
  background: '#95a5a6',
  color: '#fff',
  border: 'none',
  borderRadius: 4,
  padding: '10px 24px',
  cursor: 'pointer',
  fontSize: 15,
  marginBottom: 16,
};

export default function TaskDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [task, setTask] = useState<Task | null>(null);

  useEffect(() => {
    if (!id) return;
    api.getTask(Number(id)).then(setTask).catch(console.error);
  }, [id]);

  if (!task) return <p>Loading...</p>;

  const msgs = (task.messages as Array<{ agent_name: string; agent_role: string; content: string }>) || [];

  return (
    <div>
      <button onClick={() => navigate(`/crews/${task.crew_id}`)} style={btnStyle}>
        &larr; Back to Crew
      </button>

      <h2>Task #{task.id}</h2>
      <div style={{ padding: 16, background: '#f8f9fa', borderRadius: 8, marginBottom: 24 }}>
        <strong>Input:</strong>
        <p>{task.input}</p>
        <span style={{ color: '#888', fontSize: 13 }}>
          Status: {task.status} | {new Date(task.created_at).toLocaleString()}
        </span>
      </div>

      {task.result && (
        <div style={{ padding: 16, background: '#e8f8f5', borderRadius: 8, marginBottom: 24 }}>
          <strong>Final Result:</strong>
          <p style={{ whiteSpace: 'pre-wrap' }}>{task.result}</p>
        </div>
      )}

      <h3>Messages</h3>
      <MessageList messages={msgs} running={false} />
    </div>
  );
}
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/
git commit -m "feat: add all frontend pages"
```

---

### Task 12: CLI Tool

**Files:**
- Create: `cli/client.py`
- Create: `cli/main.py`

- [ ] **Step 1: Create cli/client.py**

```python
import httpx


class CrewCraftClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self._client = httpx.AsyncClient(base_url=base_url, timeout=300.0)

    async def list_crews(self) -> list[dict]:
        r = await self._client.get("/api/crews")
        r.raise_for_status()
        return r.json()

    async def get_crew(self, crew_id: int) -> dict:
        r = await self._client.get(f"/api/crews/{crew_id}")
        r.raise_for_status()
        return r.json()

    async def run_task(self, crew_id: int, task_input: str) -> dict:
        r = await self._client.post(
            f"/api/crews/{crew_id}/run",
            json={"input": task_input},
        )
        r.raise_for_status()
        return r.json()

    async def run_task_stream(self, crew_id: int, task_input: str):
        import json

        async with self._client.stream(
            "POST",
            f"/api/crews/{crew_id}/run",
            json={"input": task_input},
        ) as r:
            r.raise_for_status()
            buffer = b""
            async for chunk in r.aiter_bytes():
                buffer += chunk
                try:
                    data = json.loads(buffer)
                    buffer = b""
                    yield data
                except json.JSONDecodeError:
                    pass

    async def close(self):
        await self._client.aclose()
```

- [ ] **Step 2: Create cli/main.py**

```python
import asyncio

import typer

from client import CrewCraftClient

app = typer.Typer(name="crewcraft", help="CrewCraft CLI - Multi-Agent Collaboration Tool")


@app.command("ls")
def list_crews():
    """List all crews."""

    async def _run():
        async with CrewCraftClient() as client:
            crews = await client.list_crews()
            if not crews:
                typer.echo("No crews found.")
                return
            for c in crews:
                agent_count = len(c.get("agents", []))
                typer.echo(f"  [{c['id']}] {c['name']} ({c['workflow_type']}) - {agent_count} agents")

    asyncio.run(_run())


@app.command("run")
def run_task(
    crew_id: int = typer.Argument(..., help="Crew ID to execute"),
    task: str = typer.Option(..., "--task", "-t", help="Task input text"),
):
    """Run a task with a crew."""

    async def _run():
        async with CrewCraftClient() as client:
            crew = await client.get_crew(crew_id)
            typer.echo(f"\nRunning task with crew: {crew['name']}\n")
            typer.echo(f"Task: {task}\n")
            typer.echo("-" * 60)

            result = await client.run_task(crew_id, task)
            messages = result.get("messages", [])
            for msg in messages:
                name = msg.get("agent_name", "Unknown")
                role = msg.get("agent_role", "")
                content = msg.get("content", "")
                typer.echo(f"\n[{name}] ({role}):\n{content}\n")
                typer.echo("-" * 60)

            if result.get("result"):
                typer.echo(f"\nFinal Result:\n{result['result']}")

    asyncio.run(_run())


if __name__ == "__main__":
    app()
```

- [ ] **Step 3: Commit**

```bash
git add cli/
git commit -m "feat: add CLI tool with ls and run commands"
```

---

### Task 13: Docker Compose

**Files:**
- Create: `docker-compose.yml`

- [ ] **Step 1: Create docker-compose.yml**

```yaml
version: "3.9"

services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
    volumes:
      - ./backend/crewcraft.db:/app/crewcraft.db

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "5173:5173"
    depends_on:
      - backend
```

- [ ] **Step 2: Create backend/Dockerfile**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 3: Create frontend/Dockerfile**

```dockerfile
FROM node:20-alpine as build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

- [ ] **Step 4: Create frontend/nginx.conf**

```nginx
server {
    listen 80;
    server_name localhost;

    location / {
        root /usr/share/nginx/html;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }

    location /api/crews/ {
        proxy_pass http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

- [ ] **Step 5: Commit**

```bash
git add docker-compose.yml backend/Dockerfile frontend/Dockerfile frontend/nginx.conf
git commit -m "feat: add Docker Compose and Dockerfiles"
```

---

### Task 14: Integration Verification

- [ ] **Step 1: Start backend with test API key**

```bash
cd backend && DEEPSEEK_API_KEY=test uvicorn app.main:app --port 8000 &
```

- [ ] **Step 2: Create a crew via API**

```bash
curl -X POST http://localhost:8000/api/crews \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Crew", "description": "Testing", "workflow_type": "sequential"}'
```

Expected: JSON response with crew id, status 201

- [ ] **Step 3: Add an agent**

```bash
curl -X POST http://localhost:8000/api/crews/1/agents \
  -H "Content-Type: application/json" \
  -d '{"name": "Researcher", "role": "researcher", "system_prompt": "You are a helpful researcher."}'
```

Expected: JSON response with agent, status 201

- [ ] **Step 4: Verify frontend dev server connects**

```bash
cd frontend && npm run dev &
# Open http://localhost:5173, verify CrewCraft app loads
```

- [ ] **Step 5: Clean up**

Kill background uvicorn and vite processes.

- [ ] **Step 6: Commit any final adjustments**

```bash
git add -A && git diff --staged
git commit -m "chore: integration verification and final adjustments"
```
