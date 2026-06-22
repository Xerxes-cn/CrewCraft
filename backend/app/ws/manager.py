"""WebSocket connection manager and streaming helpers."""
from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from fastapi import WebSocket

from app.engine.runner import run_crew_stream
from app.engine.workflows.roundtable import run_roundtable_stream
from app.engine.agent_loop import run_agent_stream


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
    crewai_crew,
    initial_state: dict,
) -> AsyncGenerator[dict, None]:
    """Run workflow with CrewAI and stream outputs via broadcast and yield."""
    workflow_type = initial_state.get("workflow_type", "sequential")

    if workflow_type == "roundtable":
        agents = initial_state["agents"]
        task_input = initial_state["task_input"]
        max_rounds = initial_state.get("max_rounds", 2)

        all_messages: list[dict] = []
        final_result = ""
        async for event in run_roundtable_stream(agents, task_input, max_rounds):
            if event["type"] == "chunk":
                await manager.broadcast(crew_id, {
                    "type": "agent_chunk",
                    "agent_name": event["agent_name"],
                    "agent_role": event.get("agent_role", ""),
                    "content": event["content"],
                })
            elif event["type"] == "done":
                msg = {
                    "agent_name": event["agent_name"],
                    "agent_role": event.get("agent_role", ""),
                    "content": event["content"],
                }
                all_messages.append(msg)
                await manager.broadcast(crew_id, {
                    "type": "agent_message",
                    "task_id": task_id,
                    "data": msg,
                })
                if event["agent_name"] == "Summary":
                    final_result = event["content"]

        yield {
            "type": "workflow_complete",
            "task_id": task_id,
            "final_result": final_result,
            "messages": all_messages,
        }
    else:
        all_messages, final_result = await run_crew_stream(
            crewai_crew, crew_id, task_id, manager.broadcast
        )
        yield {
            "type": "workflow_complete",
            "task_id": task_id,
            "final_result": final_result,
            "messages": all_messages,
        }


async def stream_agent_round(
    crew_id: int,
    agents: list[dict],
    followup_input: str,
    history: list[dict],
) -> list[dict]:
    """Run an interactive round: all agents respond to user follow-up with conversation context."""
    results: list[dict] = []

    # Build conversation context from history
    context_parts: list[str] = []
    for msg in history:
        name = msg.get("agent_name", "")
        role = msg.get("agent_role", "")
        content = msg.get("content", "")
        label = f"{name}（{role}）" if role else name
        context_parts.append(f"[{label}]: {content}")
    context = "\n".join(context_parts)

    for agent in agents:
        async for event in run_agent_stream(agent, followup_input, context):
            event_type = event["type"]

            if event_type == "chunk":
                await manager.broadcast(crew_id, {
                    "type": "agent_chunk",
                    "agent_name": agent["name"],
                    "agent_role": agent["role"],
                    "content": event["content"],
                })
            elif event_type == "tool_call":
                await manager.broadcast(crew_id, {
                    "type": "tool_call",
                    "agent_name": agent["name"],
                    "tool_name": event["tool_name"],
                    "arguments": event["arguments"],
                })
            elif event_type == "tool_result":
                await manager.broadcast(crew_id, {
                    "type": "tool_result",
                    "agent_name": agent["name"],
                    "tool_name": event["tool_name"],
                    "result": event["result"],
                })
            elif event_type == "done":
                result = {"agent_name": agent["name"], "agent_role": agent["role"], "content": event["content"]}
                await manager.broadcast(crew_id, {
                    "type": "agent_message",
                    "data": result,
                })
                results.append(result)

    return results
