"""Agent CRUD API routes."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..manager.agent_manager import AgentConfig, agent_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/agents", tags=["agents"])


# ── Request/Response schemas ──────────────────────────────────────────

class AgentCreate(BaseModel):
    name: str
    model: str
    description: str = ""
    idle_timeout: int = 300


class AgentResponse(BaseModel):
    name: str
    model: str
    description: str
    system_prompt: str
    tools: list[str]
    port: int
    idle_timeout: int
    online: bool
    created_at: str


def _agent_to_response(config: AgentConfig) -> AgentResponse:
    return AgentResponse(
        name=config.name,
        model=config.model,
        description=config.description,
        system_prompt=config.system_prompt,
        tools=config.tools,
        port=config.port,
        idle_timeout=config.idle_timeout,
        online=agent_manager.is_online(config.name),
        created_at=config.created_at,
    )


# ── Routes ────────────────────────────────────────────────────────────

@router.post("", status_code=201)
async def create_agent(body: AgentCreate):
    """Create a new agent configuration.

    Automatically generates system_prompt from description using LLM.
    Saves prompt to data/agents/{name}.prompt.md for user customization.
    """
    if agent_manager.load_config(body.name):
        raise HTTPException(status_code=409, detail=f"Agent '{body.name}' already exists")

    port = agent_manager.next_port()
    config = AgentConfig(
        name=body.name,
        model=body.model,
        description=body.description,
        port=port,
        idle_timeout=body.idle_timeout,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    agent_manager.save_config(config)

    # Generate and save system prompt
    if body.description:
        from app.agent.prompt_generator import generate_prompt, save_prompt
        prompt = generate_prompt(body.description, body.model)
        save_prompt(body.name, prompt)
        logger.info(f"Generated system prompt for '{body.name}' ({len(prompt)} chars)")

    logger.info(f"Created agent '{body.name}' (port {port})")
    return _agent_to_response(config)


@router.get("")
async def list_agents():
    """List all configured agents."""
    configs = agent_manager.list_configs()
    return [_agent_to_response(c) for c in configs]


@router.get("/{name}")
async def get_agent(name: str):
    """Get a single agent's configuration."""
    config = agent_manager.load_config(name)
    if not config:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")
    return _agent_to_response(config)


class PromptRegenerate(BaseModel):
    description: str


@router.post("/{name}/generate-prompt")
async def regenerate_prompt(name: str, body: PromptRegenerate):
    """Regenerate the system prompt from a new description."""
    config = agent_manager.load_config(name)
    if not config:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")

    from app.agent.prompt_generator import generate_prompt, save_prompt
    prompt = generate_prompt(body.description, config.model)
    save_prompt(name, prompt)

    # Update description in config
    config.description = body.description
    agent_manager.save_config(config)

    logger.info(f"Regenerated prompt for '{name}' ({len(prompt)} chars)")
    return {"name": name, "description": body.description, "prompt": prompt}


@router.delete("/{name}")
async def delete_agent(name: str):
    """Delete an agent and its configuration."""
    if not agent_manager.load_config(name):
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")

    # Stop if running
    await agent_manager.stop_agent(name)

    agent_manager.delete_config(name)
    logger.info(f"Deleted agent '{name}'")
    return {"deleted": name}


# ── Session history routes ────────────────────────────────────────────

SESSION_BASE = agent_manager.data_dir / "sessions"


@router.get("/{name}/sessions")
async def list_sessions(name: str):
    """List all sessions for an agent."""
    config = agent_manager.load_config(name)
    if not config:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")

    session_file = SESSION_BASE / name / "sessions.json"
    if not session_file.exists():
        return []

    data = json.loads(session_file.read_text())

    # Return session summaries grouped by session_id
    sessions = {}
    for msg in data:
        sid = msg.get("session_id")
        if sid not in sessions:
            sessions[sid] = {
                "session_id": sid,
                "message_count": 0,
                "first_message": msg.get("timestamp", ""),
                "last_message": msg.get("timestamp", ""),
                "preview": msg.get("content", "")[:100],
            }
        sessions[sid]["message_count"] += 1
        sessions[sid]["last_message"] = msg.get("timestamp", "")

    return sorted(sessions.values(), key=lambda s: s["first_message"], reverse=True)


@router.get("/{name}/sessions/{session_id}")
async def get_session(name: str, session_id: str):
    """Get full conversation history for a session."""
    config = agent_manager.load_config(name)
    if not config:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")

    session_file = SESSION_BASE / name / "sessions.json"
    if not session_file.exists():
        return []

    data = json.loads(session_file.read_text())
    messages = [m for m in data if m.get("session_id") == session_id]
    return messages


@router.get("/{name}/sessions/{session_id}/tools")
async def get_session_tools(name: str, session_id: str):
    """Get tool call logs for a session."""
    config = agent_manager.load_config(name)
    if not config:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")

    tool_file = SESSION_BASE / name / "tool_logs.json"
    if not tool_file.exists():
        return []

    data = json.loads(tool_file.read_text())
    return [t for t in data if t.get("session_id") == session_id]
