"""WebSocket connection pool and heartbeat management.

Gateway runs an internal WebSocket server that agent processes connect to.
This module manages the connection pool, heartbeat, and message routing.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

import websockets
from websockets.asyncio.server import ServerConnection

from app.config import config
from .agent_manager import agent_manager as _am

logger = logging.getLogger(__name__)

TASK_TIMEOUT = 300  # seconds


class WSManager:
    """Manages WebSocket connections from agent processes."""

    def __init__(self):
        # agent_name → ServerConnection
        self._connections: dict[str, ServerConnection] = {}
        # agent_name → heartbeat task
        self._heartbeats: dict[str, asyncio.Task] = {}
        # task_id → asyncio.Future (for waiting on task results)
        self._pending_tasks: dict[str, asyncio.Future] = {}
        # agent_name → last heartbeat time
        self._last_beat: dict[str, float] = {}
        # Server instance
        self._server = None

    @property
    def active_agents(self) -> list[str]:
        return list(self._connections.keys())

    def is_connected(self, name: str) -> bool:
        return name in self._connections

    # ── Connection handler ───────────────────────────────────────────

    async def handle_agent(self, ws: ServerConnection):
        """Handle an incoming agent WebSocket connection."""
        agent_name: Optional[str] = None

        try:
            # First message must be a registration
            raw = await asyncio.wait_for(ws.recv(), timeout=10)
            msg = json.loads(raw)

            if msg.get("type") != "register":
                await ws.send(json.dumps({"type": "error", "message": "Expected register"}))
                return

            agent_name = msg["name"]
            logger.info(f"Agent {agent_name} connecting...")

            # Verify agent config exists
            config = _am.load_config(agent_name)
            if not config:
                await ws.send(json.dumps({
                    "type": "error",
                    "message": f"Agent '{agent_name}' not found in registry. Create it first with: crewcraft agent create --name {agent_name} ...",
                }))
                logger.warning(f"Rejected unregistered agent: {agent_name}")
                return

            # Close previous connection if exists
            old = self._connections.get(agent_name)
            if old is not None:
                try:
                    await old.close()
                except Exception:
                    pass

            # Send registration confirmation + full config
            await ws.send(json.dumps({
                "type": "registered",
                "name": agent_name,
                "config": config.to_dict(),
            }))
            logger.info(f"Agent {agent_name} registered (model={config.model})")

            self._connections[agent_name] = ws
            self._last_beat[agent_name] = loop_time()
            _am.set_online(agent_name, True)

            # Start heartbeat
            self._heartbeats[agent_name] = asyncio.create_task(
                self._heartbeat_loop(agent_name, ws)
            )

            # Listen for messages from agent
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                msg_type = msg.get("type")

                if msg_type == "pong":
                    self._last_beat[agent_name] = loop_time()

                elif msg_type == "task_update":
                    task_id = msg.get("task_id")
                    if task_id and task_id in self._pending_tasks:
                        future = self._pending_tasks[task_id]
                        if not future.done():
                            if msg.get("status") in ("completed", "failed"):
                                future.set_result(msg)
                            else:
                                # Progress update — store for status queries
                                future._result = msg

                elif msg_type == "idle_shutdown":
                    logger.info(f"Agent {agent_name} reports idle shutdown")
                    break

        except asyncio.TimeoutError:
            logger.warning(f"Agent {agent_name or 'unknown'} registration timeout")
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Agent {agent_name} disconnected")
        except Exception:
            logger.exception(f"Error handling agent {agent_name}")
        finally:
            if agent_name:
                self._unregister(agent_name)

    def _unregister(self, name: str):
        """Clean up agent connection."""
        self._connections.pop(name, None)
        self._last_beat.pop(name, None)
        _am.set_online(name, False)

        hb = self._heartbeats.pop(name, None)
        if hb and not hb.done():
            hb.cancel()

    # ── Heartbeat ────────────────────────────────────────────────────

    async def _heartbeat_loop(self, name: str, ws: ServerConnection):
        """Send periodic pings and detect dead connections."""
        try:
            while name in self._connections:
                await asyncio.sleep(config.agent_heartbeat_interval)
                if name not in self._connections:
                    break

                try:
                    await ws.send(json.dumps({"type": "ping"}))
                except websockets.exceptions.ConnectionClosed:
                    logger.warning(f"Heartbeat failed for {name}")
                    break
        except asyncio.CancelledError:
            pass

    # ── Task dispatching ─────────────────────────────────────────────

    async def dispatch_task(
        self, agent_name: str, content: str
    ) -> dict:
        """Send a task to an agent and return a future for the result."""
        ws = self._connections.get(agent_name)
        if ws is None:
            raise RuntimeError(f"Agent {agent_name} is not connected")

        task_id = f"task_{uuid.uuid4().hex[:12]}"
        session_id = str(uuid.uuid4())

        msg = {
            "type": "task",
            "task_id": task_id,
            "session_id": session_id,
            "content": content,
        }
        await ws.send(json.dumps(msg))

        # Create a future to await the task result
        future: asyncio.Future = asyncio.Future()
        self._pending_tasks[task_id] = future

        return {
            "task_id": task_id,
            "session_id": session_id,
            "status": "pending",
        }

    def get_task_result(self, task_id: str) -> Optional[dict]:
        """Get the current status of a task.

        Returns None if task not found, or a status dict with fields:
        task_id, session_id, status (pending/running/completed/failed)
        """
        future = self._pending_tasks.get(task_id)
        if future is None:
            return None

        status_info = {
            "task_id": task_id,
            "status": "pending",
        }

        if future.done():
            result = future.result()
            status_info.update({
                "task_id": task_id,
                "session_id": result.get("session_id", ""),
                "status": result.get("status", "completed"),
                "result": result.get("result", ""),
                "error": result.get("error"),
            })
        elif hasattr(future, "_result"):
            status_info.update(future._result)

        return status_info

    def all_task_ids(self) -> list[str]:
        return list(self._pending_tasks.keys())

    # ── Server lifecycle ──────────────────────────────────────────────

    async def start_server(self, host: str = "127.0.0.1", port: int = 8765):
        """Start the WebSocket server for agents to connect to."""
        if self._server is not None:
            return

        self._server = await websockets.serve(
            self.handle_agent, host, port
        )
        logger.info(f"WebSocket server listening on ws://{host}:{port}")

    async def stop_server(self):
        """Stop the WebSocket server."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

        # Close all agent connections
        for name, ws in list(self._connections.items()):
            try:
                await ws.close()
            except Exception:
                pass
            self._unregister(name)


def loop_time() -> float:
    """Get the current event loop time."""
    return asyncio.get_event_loop().time()


# Singleton
ws_manager = WSManager()
