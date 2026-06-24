"""Agent server process.

Each agent runs as an independent subprocess:
1. Connects to Gateway via WebSocket
2. Registers with its agent name
3. Receives tasks and executes them via deepagents
4. Sends progress updates and results back to Gateway
5. Handles heartbeat and idle shutdown
6. Saves conversation history to sessions/{name}/
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone

import websockets

from app.config import config

logging.basicConfig(
    level=config.log_level,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── Configuration from environment ─────────────────────────────────────

AGENT_NAME = os.getenv("CREWCRAFT_AGENT_NAME", "default")
AGENT_PORT = int(os.getenv("CREWCRAFT_AGENT_PORT", "9001"))

TOOL_RESULT_TRUNCATE = 100  # characters to keep in sessions.json

SESSION_DIR = config.data_dir / "sessions" / AGENT_NAME


# ── Session persistence ────────────────────────────────────────────────


def save_message(session_id: str, role: str, content: str, tool_name: str = ""):
    """Append a message to the sessions.json file."""
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    session_file = SESSION_DIR / "sessions.json"

    # Load existing
    messages = []
    if session_file.exists():
        try:
            messages = json.loads(session_file.read_text())
        except json.JSONDecodeError:
            messages = []

    msg = {
        "session_id": session_id,
        "role": role,
        "content": content,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if tool_name:
        msg["tool_name"] = tool_name

    messages.append(msg)
    session_file.write_text(json.dumps(messages, indent=2, ensure_ascii=False))


def save_tool_log(session_id: str, tool_name: str, input_data: dict, output_data: str):
    """Save tool call details to tool_logs.json."""
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    tool_file = SESSION_DIR / "tool_logs.json"

    logs = []
    if tool_file.exists():
        try:
            logs = json.loads(tool_file.read_text())
        except json.JSONDecodeError:
            logs = []

    logs.append({
        "session_id": session_id,
        "tool_name": tool_name,
        "input": input_data,
        "output": output_data,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    tool_file.write_text(json.dumps(logs, indent=2, ensure_ascii=False))


# ── Agent runner (wraps deepagents) ────────────────────────────────────

async def run_task(session_id: str, content: str, ws, config: dict) -> str:
    """Run a task using deepagents and stream results via WebSocket.

    Args:
        session_id: Unique session identifier.
        content: User's message content.
        ws: WebSocket connection to gateway.
        config: Agent configuration received from gateway (model, system_prompt, tools).
    """
    model = config.get("model", "openai:gpt-4o")
    system_prompt = config.get("system_prompt", "")
    tools_list = config.get("tools", [])

    # Save the user message
    save_message(session_id, "user", content)

    try:
        # Try to use deepagents
        from deepagents import create_deep_agent

        agent = create_deep_agent(
            model=model,
            system_prompt=system_prompt,
            tools=_build_tools(tools_list),
        )

        # Stream execution
        full_response = ""
        async for event in agent.astream_events(
            {"messages": [{"role": "user", "content": content}]},
            version="v2",
        ):
            kind = event.get("event")

            # Collect assistant messages
            if kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    full_response += chunk.content

            # Log tool calls
            elif kind == "on_tool_end":
                tool_input = event.get("data", {}).get("input", {})
                tool_output = str(event.get("data", {}).get("output", ""))
                tool_name = event.get("name", "unknown")

                # Save truncated version to sessions
                truncated = tool_output[:TOOL_RESULT_TRUNCATE]
                if len(tool_output) > TOOL_RESULT_TRUNCATE:
                    truncated += "..."
                save_message(session_id, "tool", truncated, tool_name=tool_name)

                # Save full version to tool_logs
                save_tool_log(session_id, tool_name, tool_input, tool_output)

                # Send progress update
                await ws.send(json.dumps({
                    "type": "task_update",
                    "task_id": _current_task_id,
                    "session_id": session_id,
                    "status": "running",
                    "progress": f"Tool {tool_name} completed",
                }))

        # Save assistant message
        if full_response:
            save_message(session_id, "assistant", full_response)

        return full_response

    except ImportError:
        logger.warning("deepagents not installed, using fallback")
        return await _fallback_run(session_id, content, model, system_prompt, ws, config)


def _build_tools(tools_list: list[str]) -> list:
    """Build tool list from configuration names using the tool registry."""
    from .tools import get_tool_callable, registry

    if not tools_list:
        return []

    # Validate that all requested tools exist
    available = set(registry.list_names())
    tools = []
    for name in tools_list:
        if name not in available:
            logger.warning(f"Tool '{name}' not found. Available: {', '.join(sorted(available))}")
            continue
        fn = get_tool_callable(name)
        if fn:
            tools.append(fn)
            logger.info(f"Tool '{name}' loaded")

    return tools


_current_task_id = ""


async def _fallback_run(
    session_id: str, content: str, model: str, system_prompt: str, ws, config: dict
) -> str:
    """Fallback when deepagents is not available: simple echo/reflection."""
    tools = config.get("tools", [])
    response = f"[Fallback mode] Agent {AGENT_NAME} received: {content}"
    if tools:
        response += f"\n[Available tools: {', '.join(tools)}]"
    save_message(session_id, "assistant", response)
    return response


# ── WebSocket client ───────────────────────────────────────────────────

async def agent_loop():
    """Main agent loop: connect to gateway, bidirectional register, handle messages."""
    global _current_task_id

    # Agent starts with empty config — gateway will provide it on registration
    agent_config: dict = {}
    idle_timeout = config.agent_idle_timeout
    last_task_time = asyncio.get_event_loop().time()

    gateway_ws_url = os.getenv("CREWCRAFT_GATEWAY_WS", config.ws_url)
    logger.info(f"Agent {AGENT_NAME} connecting to gateway at {gateway_ws_url}")

    async for ws in websockets.connect(gateway_ws_url):
        try:
            # ── Phase 1: Bidirectional registration ──────────────────────
            await ws.send(json.dumps({
                "type": "register",
                "name": AGENT_NAME,
            }))
            logger.info(f"Agent {AGENT_NAME} sent registration request")

            # Wait for gateway to confirm and send config
            raw = await asyncio.wait_for(ws.recv(), timeout=10)
            msg = json.loads(raw)

            if msg.get("type") == "error":
                logger.error(f"Registration rejected: {msg.get('message')}")
                return  # Exit — agent not in registry

            if msg.get("type") != "registered":
                logger.error(f"Expected 'registered', got '{msg.get('type')}'")
                return

            agent_config = msg.get("config", {})
            idle_timeout = agent_config.get("idle_timeout", config.agent_idle_timeout)
            logger.info(f"Agent {AGENT_NAME} registered (model={agent_config.get('model')}, "
                        f"tools={agent_config.get('tools')}, idle_timeout={idle_timeout}s)")

            # ── Phase 2: Main message loop ───────────────────────────────
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                msg_type = msg.get("type")

                if msg_type == "ping":
                    await ws.send(json.dumps({"type": "pong"}))

                elif msg_type == "task":
                    _current_task_id = msg.get("task_id", "")
                    session_id = msg.get("session_id", str(uuid.uuid4()))
                    content = msg.get("content", "")

                    logger.info(f"Received task {_current_task_id}")
                    last_task_time = asyncio.get_event_loop().time()

                    # Send running status
                    await ws.send(json.dumps({
                        "type": "task_update",
                        "task_id": _current_task_id,
                        "session_id": session_id,
                        "status": "running",
                    }))

                    try:
                        result = await run_task(session_id, content, ws, agent_config)

                        # Send completion
                        await ws.send(json.dumps({
                            "type": "task_update",
                            "task_id": _current_task_id,
                            "session_id": session_id,
                            "status": "completed",
                            "result": result,
                        }))
                    except Exception as e:
                        logger.exception(f"Task {_current_task_id} failed")
                        await ws.send(json.dumps({
                            "type": "task_update",
                            "task_id": _current_task_id,
                            "session_id": session_id,
                            "status": "failed",
                            "error": str(e),
                        }))

                    _current_task_id = ""

                elif msg_type == "shutdown":
                    logger.info("Gateway requested shutdown")
                    return

                # Idle check
                elapsed = asyncio.get_event_loop().time() - last_task_time
                if _current_task_id == "" and elapsed > idle_timeout:
                    logger.info(f"Idle timeout ({idle_timeout}s), shutting down")
                    await ws.send(json.dumps({
                        "type": "idle_shutdown",
                        "name": AGENT_NAME,
                    }))
                    return

        except websockets.exceptions.ConnectionClosed:
            logger.warning("Connection to gateway lost, reconnecting...")
            await asyncio.sleep(2)
        except Exception:
            logger.exception("Unexpected error in agent loop")
            await asyncio.sleep(2)


def main():
    """Entry point for agent process."""
    logger.info(f"Starting agent {AGENT_NAME} on port {AGENT_PORT}")
    asyncio.run(agent_loop())


if __name__ == "__main__":
    main()
