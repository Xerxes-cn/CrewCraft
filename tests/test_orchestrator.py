"""Orchestrator 编排器测试 — mock LLM 调用，验证规划与分派逻辑。"""

import asyncio
import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


# ── 辅助 ────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_am():
    """Mock AgentManager。"""
    from app.gateway.manager.agent_manager import AgentConfig
    am = MagicMock()
    am.list_configs.return_value = [
        AgentConfig(name="dev", model="gpt", description="Python developer"),
        AgentConfig(name="qa", model="claude", description="QA tester"),
    ]
    am.load_config.return_value = AgentConfig(name="dev", model="gpt", description="dev")
    am.is_online.return_value = True
    am.start_agent = AsyncMock(return_value=9001)
    return am


@pytest.fixture
def mock_ws():
    """Mock WSManager。"""
    ws = MagicMock()
    ws.dispatch_task = AsyncMock(return_value={"task_id": "t1", "status": "dispatched"})
    return ws


@pytest.fixture
def orch(mock_am, mock_ws):
    from app.gateway.orchestrator import Orchestrator
    return Orchestrator(mock_am, mock_ws)


# ── _build_agent_list ───────────────────────────────────────────────────


class TestBuildAgentList:

    def test_with_agents(self, orch, mock_am):
        result = orch._build_agent_list()
        assert "dev" in result
        assert "Python developer" in result
        assert "qa" in result
        assert "QA tester" in result

    def test_excludes_orchestrator(self, orch, mock_am):
        from app.gateway.manager.agent_manager import AgentConfig
        from app.gateway.orchestrator import ORCHESTRATOR_NAME
        mock_am.list_configs.return_value = [
            AgentConfig(name=ORCHESTRATOR_NAME, model="gpt", description="orch"),
            AgentConfig(name="dev", model="gpt", description="dev"),
        ]
        result = orch._build_agent_list()
        assert ORCHESTRATOR_NAME not in result
        assert "dev" in result

    def test_no_agents(self, orch, mock_am):
        mock_am.list_configs.return_value = []
        result = orch._build_agent_list()
        assert "(no agents configured)" in result


# ── _plan ───────────────────────────────────────────────────────────────


class TestPlan:

    @pytest.mark.asyncio
    async def test_plan_valid_json(self, orch):
        """LLM 返回有效 JSON 计划。"""
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "plan": [{"agent": "dev", "task": "write code", "reason": "best fit"}]
        })

        with patch("langchain.chat_models.init_chat_model") as mock_llm:
            mock_llm.return_value.ainvoke = AsyncMock(return_value=mock_response)
            result = await orch._plan("build a feature")

        assert "plan" in result
        assert len(result["plan"]) == 1
        assert result["plan"][0]["agent"] == "dev"

    @pytest.mark.asyncio
    async def test_plan_empty_agents(self, orch, mock_am):
        """无可用 Agent 时返回空计划。"""
        mock_am.list_configs.return_value = []
        mock_response = MagicMock()
        mock_response.content = json.dumps({"plan": []})

        with patch("langchain.chat_models.init_chat_model") as mock_llm:
            mock_llm.return_value.ainvoke = AsyncMock(return_value=mock_response)
            result = await orch._plan("some task")

        assert result == {"plan": []}

    @pytest.mark.asyncio
    async def test_plan_llm_failure(self, orch):
        """LLM 调用失败时返回 error。"""
        with patch("langchain.chat_models.init_chat_model") as mock_llm:
            mock_llm.return_value.ainvoke = AsyncMock(side_effect=RuntimeError("LLM down"))
            result = await orch._plan("something")

        assert "error" in result
        assert "LLM down" in result["error"]

    @pytest.mark.asyncio
    async def test_plan_malformed_json(self, orch):
        """LLM 返回非 JSON 时返回 error。"""
        mock_response = MagicMock()
        mock_response.content = "Not a JSON response at all"

        with patch("langchain.chat_models.init_chat_model") as mock_llm:
            mock_llm.return_value.ainvoke = AsyncMock(return_value=mock_response)
            result = await orch._plan("task")

        assert "error" in result

    @pytest.mark.asyncio
    async def test_plan_extracts_json_from_code_block(self, orch):
        """LLM 返回 ```json...``` 包裹的 JSON 时正确提取。"""
        mock_response = MagicMock()
        mock_response.content = '```json\n{"plan": [{"agent": "dev", "task": "x", "reason": "r"}]}\n```'

        with patch("langchain.chat_models.init_chat_model") as mock_llm:
            mock_llm.return_value.ainvoke = AsyncMock(return_value=mock_response)
            result = await orch._plan("task")

        assert "error" not in result
        assert len(result["plan"]) == 1


# ── handle_task ─────────────────────────────────────────────────────────


class TestHandleTask:

    @pytest.mark.asyncio
    async def test_handle_task_valid_plan(self, orch):
        """有效计划分派到 Agent。"""
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "plan": [{"agent": "dev", "task": "write tests", "reason": "expert"}]
        })

        with patch("langchain.chat_models.init_chat_model") as mock_llm:
            mock_llm.return_value.ainvoke = AsyncMock(return_value=mock_response)
            result = await orch.handle_task("write some tests")

        assert result["status"] == "pending"
        assert "task_id" in result
        assert "session_id" in result
        assert len(result["plan"]) == 1
        assert result["plan"][0]["agent"] == "dev"

    @pytest.mark.asyncio
    async def test_handle_task_llm_error(self, orch):
        """LLM 报错时 handle_task 返回 failed。"""
        with patch("langchain.chat_models.init_chat_model") as mock_llm:
            mock_llm.return_value.ainvoke = AsyncMock(side_effect=Exception("boom"))
            result = await orch.handle_task("do something")

        assert result["status"] == "failed"
        assert "boom" in result["error"]

    @pytest.mark.asyncio
    async def test_handle_task_empty_plan(self, orch):
        """空计划返回 failed。"""
        mock_response = MagicMock()
        mock_response.content = json.dumps({"plan": []})

        with patch("langchain.chat_models.init_chat_model") as mock_llm:
            mock_llm.return_value.ainvoke = AsyncMock(return_value=mock_response)
            result = await orch.handle_task("do something")

        assert result["status"] == "failed"

    @pytest.mark.asyncio
    async def test_handle_task_plan_with_error(self, orch):
        """计划中包含 error 字段。"""
        mock_response = MagicMock()
        mock_response.content = json.dumps({"error": "No suitable agent"})

        with patch("langchain.chat_models.init_chat_model") as mock_llm:
            mock_llm.return_value.ainvoke = AsyncMock(return_value=mock_response)
            result = await orch.handle_task("impossible task")

        assert result["status"] == "failed"
        assert result["error"] == "No suitable agent"

    @pytest.mark.asyncio
    async def test_handle_task_starts_offline_agent(self, orch, mock_am, mock_ws):
        """离线 Agent 被自动启动。"""
        mock_am.is_online.return_value = False
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "plan": [{"agent": "dev", "task": "code", "reason": "r"}]
        })

        with patch("langchain.chat_models.init_chat_model") as mock_llm:
            mock_llm.return_value.ainvoke = AsyncMock(return_value=mock_response)
            result = await orch.handle_task("code")

        mock_am.start_agent.assert_awaited()  # 确保被调用

    @pytest.mark.asyncio
    async def test_handle_task_skips_unknown_agent(self, orch, mock_am, mock_ws):
        """计划中不存在的 Agent 被跳过。"""
        from app.gateway.manager.agent_manager import AgentConfig

        def load_config_side_effect(name):
            if name == "dev":
                return AgentConfig(name="dev", model="gpt", description="dev")
            return None

        mock_am.load_config.side_effect = load_config_side_effect
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "plan": [
                {"agent": "unknown", "task": "do", "reason": "r"},
                {"agent": "dev", "task": "do", "reason": "r"},
            ]
        })

        with patch("langchain.chat_models.init_chat_model") as mock_llm:
            mock_llm.return_value.ainvoke = AsyncMock(return_value=mock_response)
            result = await orch.handle_task("some task")

        # 只有 dev 被分派
        assert len(result["plan"]) == 1

    @pytest.mark.asyncio
    async def test_handle_task_dispatch_error(self, orch, mock_ws):
        """dispatch_task 异常时记录错误不崩溃。"""
        mock_ws.dispatch_task = AsyncMock(side_effect=Exception("connect failed"))
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "plan": [{"agent": "dev", "task": "x", "reason": "r"}]
        })

        with patch("langchain.chat_models.init_chat_model") as mock_llm:
            mock_llm.return_value.ainvoke = AsyncMock(return_value=mock_response)
            result = await orch.handle_task("task")

        assert result["status"] == "pending"
        assert result["plan"][0]["status"] == "error"
        assert "connect failed" in result["plan"][0]["error"]

    @pytest.mark.asyncio
    async def test_handle_task_multi_agent_plan(self, orch, mock_am, mock_ws):
        """多 Agent 计划正确分派。"""
        mock_am.load_config.return_value = MagicMock(name="dev")
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "plan": [
                {"agent": "dev", "task": "task1", "reason": "r1"},
                {"agent": "qa", "task": "task2", "reason": "r2"},
            ]
        })

        with patch("langchain.chat_models.init_chat_model") as mock_llm:
            mock_llm.return_value.ainvoke = AsyncMock(return_value=mock_response)
            result = await orch.handle_task("big task")

        assert len(result["plan"]) == 2
        assert mock_ws.dispatch_task.call_count >= 1


# ── 单例 ────────────────────────────────────────────────────────────────


class TestSingleton:

    def test_get_orchestrator_creates_and_reuses(self, mock_am, mock_ws):
        from app.gateway.orchestrator import get_orchestrator, _orchestrator

        # 重置单例
        import app.gateway.orchestrator as orch_mod
        orch_mod._orchestrator = None

        o1 = get_orchestrator(mock_am, mock_ws)
        o2 = get_orchestrator(None, None)
        assert o1 is o2

    def test_get_orchestrator_none_when_not_initialized(self):
        from app.gateway.orchestrator import get_orchestrator, _orchestrator

        import app.gateway.orchestrator as orch_mod
        orch_mod._orchestrator = None

        result = get_orchestrator(None, None)
        assert result is None
