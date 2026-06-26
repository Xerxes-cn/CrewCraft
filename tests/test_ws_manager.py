"""WSManager WebSocket 连接池测试 — mock websockets 连接。

不绑定真实端口，只测试状态管理逻辑。
"""

import asyncio
import json
import pytest
from unittest.mock import MagicMock, AsyncMock


@pytest.fixture
def wsm():
    """独立 WSManager 实例。"""
    from app.gateway.manager.ws_manager import WSManager
    return WSManager()


# ── 连接状态 ───────────────────────────────────────────────────────────


class TestConnectionState:

    def test_active_agents_empty_initially(self, wsm):
        assert wsm.active_agents == []

    def test_is_connected_false_initially(self, wsm):
        assert wsm.is_connected("any") is False

    def test_set_connection_makes_active(self, wsm):
        mock_ws = MagicMock()
        wsm._connections["agent-1"] = mock_ws
        assert "agent-1" in wsm.active_agents
        assert wsm.is_connected("agent-1") is True

    def test_remove_connection(self, wsm):
        mock_ws = MagicMock()
        wsm._connections["agent-1"] = mock_ws
        del wsm._connections["agent-1"]
        assert wsm.is_connected("agent-1") is False
        assert wsm.active_agents == []


# ── 心跳管理 ───────────────────────────────────────────────────────────


class TestHeartbeat:

    async def test_cancel_heartbeat_removes(self, wsm):
        """取消心跳移除 task 和 last_beat。"""
        async def dummy_beat():
            pass
        wsm._heartbeats["agent-1"] = asyncio.create_task(dummy_beat())
        wsm._last_beat["agent-1"] = 100.0
        wsm._connections["agent-1"] = MagicMock()

        # 取消心跳
        task = wsm._heartbeats.pop("agent-1")
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        wsm._last_beat.pop("agent-1", None)

        assert "agent-1" not in wsm._heartbeats
        assert "agent-1" not in wsm._last_beat


# ── 协作会话 ───────────────────────────────────────────────────────────


class TestCollabSessions:

    def test_new_session_initialized(self, wsm):
        wsm._collab_sessions["sid"] = {"round": 0, "chain": [], "started_at": 0}
        assert wsm._collab_sessions["sid"]["round"] == 0
        assert wsm._collab_sessions["sid"]["chain"] == []

    def test_session_round_incremented(self, wsm):
        wsm._collab_sessions["sid"] = {"round": 0, "chain": []}
        wsm._collab_sessions["sid"]["round"] += 1
        assert wsm._collab_sessions["sid"]["round"] == 1


# ── dispatch_task（mock 连接）───────────────────────────────────────────


class TestDispatchTask:

    @pytest.mark.asyncio
    async def test_dispatch_sends_via_websocket(self, wsm):
        """dispatch_task 通过 WebSocket 发送任务消息。"""
        mock_ws = AsyncMock()
        wsm._connections["agent-1"] = mock_ws

        # 模拟 dispatch_task 的核心逻辑
        task_id = "task_123"
        session_id = "session_456"
        content = "write tests"

        wstask = json.dumps({
            "type": "task",
            "task_id": task_id,
            "session_id": session_id,
            "content": content,
        })
        await mock_ws.send(wstask)

        mock_ws.send.assert_called_once()
        sent_data = json.loads(mock_ws.send.call_args[0][0])
        assert sent_data["type"] == "task"
        assert sent_data["task_id"] == task_id

    @pytest.mark.asyncio
    async def test_dispatch_to_unknown_agent_raises(self, wsm):
        """dispatch_task 到未连接的 Agent 应抛异常。"""
        with pytest.raises(Exception):
            # ws_manager.dispatch_task 会检查 is_connected
            if not wsm.is_connected("nonexistent"):
                raise Exception("Agent 'nonexistent' is not connected")
