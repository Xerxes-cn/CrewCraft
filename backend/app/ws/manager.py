import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import WebSocket

from app.llm.deepseek import chat_completion_stream


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
        system_prompt = agent.get("system_prompt") or f"你是{agent['name']}，{agent['role']}。"
        if agent.get("workspace"):
            system_prompt += f"\n\n你的独立工作目录为：{agent['workspace']}。你可以在此目录中读写文件，该目录与其他智能体隔离。"
        messages = [{"role": "system", "content": system_prompt}]

        if context:
            messages.append({"role": "user", "content": f"历史对话：\n{context}"})

        messages.append({"role": "user", "content": f"用户的后续消息：{followup_input}\n\n请根据你的角色和对话历史，对用户的消息做出回应。"})

        # Stream agent response character by character
        full_content = ""
        async for chunk in chat_completion_stream(messages=messages):
            full_content += chunk
            await manager.broadcast(crew_id, {
                "type": "agent_chunk",
                "agent_name": agent["name"],
                "agent_role": agent["role"],
                "content": chunk,
            })

        result = {"agent_name": agent["name"], "agent_role": agent["role"], "content": full_content}
        await manager.broadcast(crew_id, {
            "type": "agent_message",
            "data": result,
        })
        results.append(result)

    return results
