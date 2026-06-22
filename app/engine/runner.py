"""CrewAI execution runner."""
from __future__ import annotations

from typing import Any

from crewai import Crew
from crewai.types.streaming import StreamChunkType


async def _noop(*args, **kwargs):
    pass


async def run_crew_stream(
    crew: Crew,
    crew_id: int,
    task_id: int,
    broadcast=None,
) -> tuple[list[dict], str]:
    """Run a CrewAI crew, optionally streaming via a broadcast callback.

    Returns (all_messages, final_result).
    """
    if broadcast is None:
        broadcast = _noop

    all_messages: list[dict] = []
    current_agent: str | None = None
    content_buf: str = ""

    try:
        streaming_output = await crew.kickoff_async()
    except Exception as e:
        error_msg = f"工作流执行失败: {e}"
        await broadcast(crew_id, {"type": "error", "task_id": task_id, "message": error_msg})
        return [], error_msg

    async for chunk in streaming_output:
        agent_role = chunk.agent_role or ""

        # Track agent transitions to emit structured messages
        if agent_role and agent_role != current_agent:
            if current_agent and content_buf.strip():
                msg = {"agent_name": current_agent, "agent_role": "", "content": content_buf.strip()}
                all_messages.append(msg)
                await broadcast(crew_id, {"type": "agent_message", "task_id": task_id, "data": msg})
            current_agent = agent_role
            content_buf = ""

        if chunk.chunk_type == StreamChunkType.TEXT:
            content_buf += chunk.content
            await broadcast(crew_id, {
                "type": "agent_chunk",
                "agent_name": agent_role,
                "agent_role": "",
                "content": chunk.content,
            })
        elif chunk.chunk_type == StreamChunkType.TOOL_CALL and chunk.tool_call:
            await broadcast(crew_id, {
                "type": "tool_call",
                "agent_name": agent_role,
                "tool_name": chunk.tool_call.tool_name,
                "arguments": chunk.tool_call.arguments or {},
            })

    # Flush last agent content
    if current_agent and content_buf.strip():
        msg = {"agent_name": current_agent, "agent_role": "", "content": content_buf.strip()}
        all_messages.append(msg)
        await broadcast(crew_id, {"type": "agent_message", "task_id": task_id, "data": msg})

    try:
        result = streaming_output.result
        final = str(result) if result else ""
    except Exception:
        final = "\n".join(m["content"] for m in all_messages)

    await broadcast(crew_id, {
        "type": "workflow_complete",
        "task_id": task_id,
        "final_result": final,
        "messages": all_messages,
    })

    return all_messages, final
