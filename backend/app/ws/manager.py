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
