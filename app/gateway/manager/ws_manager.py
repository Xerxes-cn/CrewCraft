"""WebSocket 连接池和心跳管理。

网关运行一个内部 WebSocket 服务器供 Agent 进程连接。
本模块管理连接池、心跳和消息路由。
"""

import asyncio
import json
import logging
import uuid
from typing import Optional

import websockets
from websockets.asyncio.server import ServerConnection

from app.config import config
from .agent_manager import agent_manager as _am

logger = logging.getLogger(__name__)

TASK_TIMEOUT = 300  # 秒
MAX_MISSED_PINGS = 3  # 连续丢失心跳次数后踢下线


class WSManager:
    """管理来自 Agent 进程的 WebSocket 连接。"""

    def __init__(self):
        self._connections: dict[str, ServerConnection] = {}
        self._heartbeats: dict[str, asyncio.Task] = {}
        self._pending_tasks: dict[str, asyncio.Future] = {}
        self._last_beat: dict[str, float] = {}
        self._server = None
        # 协作会话跟踪 {session_id: {round, chain, started_at, last_activity, seen_contents}}
        self._collab_sessions: dict[str, dict] = {}

    @property
    def active_agents(self) -> list[str]:
        return list(self._connections.keys())

    def is_connected(self, name: str) -> bool:
        return name in self._connections

    # ── 连接处理器 ───────────────────────────────────────────────────

    async def handle_agent(self, ws: ServerConnection):
        """处理一个接入的 Agent WebSocket 连接。"""
        agent_name: Optional[str] = None

        try:
            # 第一条消息必须是注册消息
            raw = await asyncio.wait_for(ws.recv(), timeout=10)
            msg = json.loads(raw)

            if msg.get("type") != "register":
                await ws.send(json.dumps({"type": "error", "message": "Expected register"}))
                return

            agent_name = msg["name"]
            logger.info(f"Agent {agent_name} connecting...")

            # 验证 Agent 配置是否存在
            config = _am.load_config(agent_name)
            if not config:
                await ws.send(json.dumps({
                    "type": "error",
                    "message": f"Agent '{agent_name}' not found in registry. Create it first with: crewcraft agent create --name {agent_name} ...",
                }))
                logger.warning(f"Rejected unregistered agent: {agent_name}")
                return

            # 关闭之前的连接（如果存在）
            old = self._connections.get(agent_name)
            if old is not None:
                try:
                    await old.close()
                except Exception:
                    pass

            # 发送注册确认 + 完整配置
            await ws.send(json.dumps({
                "type": "registered",
                "name": agent_name,
                "config": config.to_dict(),
            }))
            logger.info(f"Agent {agent_name} registered (model={config.model})")

            self._connections[agent_name] = ws
            self._last_beat[agent_name] = loop_time()
            _am.set_online(agent_name, True)

            # 启动心跳
            self._heartbeats[agent_name] = asyncio.create_task(
                self._heartbeat_loop(agent_name, ws)
            )

            # 监听来自 Agent 的消息
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
                                # 进度更新 — 存储以供状态查询
                                future._result = msg

                elif msg_type == "agent_message":
                    await self._relay_message(agent_name, msg)

                elif msg_type == "agent_broadcast":
                    await self._broadcast_message(agent_name, msg)

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

    # ── Agent 间消息转发 ──────────────────────────────────────────────

    async def _relay_message(self, from_agent: str, msg: dict):
        """转发 Agent 间点对点消息，带监督检查。"""
        to_agent = msg.get("to", "")
        sid = msg.get("session_id", "")
        content = msg.get("content", "")

        if to_agent not in self._connections:
            await self._connections[from_agent].send(json.dumps({
                "type": "agent_message", "from": to_agent, "session_id": sid,
                "error": f"Agent '{to_agent}' 不在线",
            }))
            return

        # 监督检查
        check = self._check_collab(sid, from_agent, to_agent, content)
        if check:
            await self._connections[from_agent].send(json.dumps(check))
            return

        logger.info(f"Agent 消息: {from_agent} → {to_agent} [{sid[:8]}]")
        await self._connections[to_agent].send(json.dumps({
            "type": "agent_message",
            "from": from_agent,
            "to": to_agent,
            "session_id": sid,
            "content": content,
            "context": msg.get("context", {}),
        }))

    async def _broadcast_message(self, from_agent: str, msg: dict):
        """广播消息给所有其他在线 Agent。"""
        content = msg.get("content", "")
        sid = msg.get("session_id", str(uuid.uuid4()))
        logger.info(f"Agent 广播: {from_agent} → {len(self._connections)-1} 个 Agent")

        payload = json.dumps({
            "type": "agent_broadcast",
            "from": from_agent,
            "session_id": sid,
            "content": content,
        })
        for name, ws in self._connections.items():
            if name != from_agent:
                try:
                    await ws.send(payload)
                except Exception:
                    pass

    # ── 协作监督 ─────────────────────────────────────────────────────

    def _check_collab(self, sid: str, from_agent: str, to_agent: str, content: str) -> dict | None:
        """检查协作是否越界。返回 None 表示放行，返回 dict 表示拦截。"""
        from app.config import config

        if not sid:
            sid = str(uuid.uuid4())

        now = loop_time()
        if sid not in self._collab_sessions:
            self._collab_sessions[sid] = {
                "round": 0, "chain": [from_agent], "started_at": now,
                "last_activity": now, "seen_contents": set(),
            }

        sess = self._collab_sessions[sid]
        sess["round"] += 1
        sess["last_activity"] = now
        if to_agent not in sess["chain"]:
            sess["chain"].append(to_agent)

        # 超时
        if now - sess["started_at"] > config.collab_timeout:
            return {"type": "supervisor", "action": "halt",
                    "reason": f"协作超时 ({config.collab_timeout}s)", "session_id": sid}

        # 轮次上限
        if sess["round"] > config.collab_max_rounds:
            return {"type": "supervisor", "action": "halt",
                    "reason": f"达到最大轮次 ({config.collab_max_rounds})", "session_id": sid}

        # 深度上限
        if len(sess["chain"]) > config.collab_max_depth:
            return {"type": "supervisor", "action": "halt",
                    "reason": f"链条过深 ({len(sess['chain'])} > {config.collab_max_depth})", "session_id": sid}

        # 重复检测
        content_hash = hash(content)
        if content_hash in sess["seen_contents"]:
            logger.warning(f"协作重复消息: {from_agent} → {to_agent}")
        sess["seen_contents"].add(content_hash)

        return None

    def _unregister(self, name: str):
        """清理 Agent 连接。"""
        self._connections.pop(name, None)
        self._last_beat.pop(name, None)
        _am.set_online(name, False)

        hb = self._heartbeats.pop(name, None)
        if hb and not hb.done():
            hb.cancel()

    # ── 心跳 ────────────────────────────────────────────────────────

    async def _heartbeat_loop(self, name: str, ws: ServerConnection):
        """发送定期 ping 并检测死连接。连续丢失 3 次心跳则踢下线。"""
        missed = 0
        try:
            while name in self._connections:
                await asyncio.sleep(config.agent_heartbeat_interval)
                if name not in self._connections:
                    return

                try:
                    await ws.send(json.dumps({"type": "ping"}))
                except websockets.exceptions.ConnectionClosed:
                    missed += 1
                    if missed < MAX_MISSED_PINGS:
                        logger.warning(
                            f"Agent {name} heartbeat lost ({missed}/{MAX_MISSED_PINGS})"
                        )
                        continue

                    logger.warning(
                        f"Agent {name} unresponsive after {MAX_MISSED_PINGS} missed pings, kicking"
                    )
                    self._unregister(name)
                    try:
                        await ws.close()
                    except Exception:
                        pass
                    return

                # ping 成功送达，重置计数
                missed = 0

        except asyncio.CancelledError:
            pass  # _unregister 取消心跳任务，不额外处理

    # ── 任务分派 ────────────────────────────────────────────────────

    async def dispatch_task(
        self, agent_name: str, content: str
    ) -> dict:
        """将任务发送给 Agent 并返回一个等待结果的 Future。"""
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

        # 创建 Future 以等待任务结果
        future: asyncio.Future = asyncio.Future()
        self._pending_tasks[task_id] = future

        return {
            "task_id": task_id,
            "session_id": session_id,
            "status": "pending",
        }

    def get_task_result(self, task_id: str) -> Optional[dict]:
        """获取任务的当前状态。

        如果任务未找到返回 None；否则返回包含以下字段的状态字典：
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

    # ── 服务器生命周期 ──────────────────────────────────────────────

    async def start_server(self, host: str = "127.0.0.1", port: int = 8765):
        """启动 WebSocket 服务器，供 Agent 连接。"""
        if self._server is not None:
            return

        self._server = await websockets.serve(
            self.handle_agent, host, port
        )
        logger.info(f"WebSocket server listening on ws://{host}:{port}")

    async def stop_server(self):
        """停止 WebSocket 服务器。"""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

        # 关闭所有 Agent 连接
        for name, ws in list(self._connections.items()):
            try:
                await ws.close()
            except Exception:
                pass
            self._unregister(name)


def loop_time() -> float:
    """获取当前事件循环时间。"""
    return asyncio.get_event_loop().time()


# 单例
ws_manager = WSManager()
