"""Supervisor 监督 Agent 测试 — mock LLM 调用。"""

import json
import time
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


@pytest.fixture
def supervisor():
    from app.gateway.manager.supervisor import Supervisor
    return Supervisor()


@pytest.fixture
def sample_session():
    return {
        "session_id": "test-sid",
        "round": 5,
        "chain": ["dev", "qa", "dev"],
        "started_at": 0,
        "last_activity": 0,
        "seen_contents": set(),
    }


class TestSupervisorCheck:

    @pytest.mark.asyncio
    async def test_allow(self, supervisor, sample_session):
        """LLM 返回 allow → 放行。"""
        mock_response = MagicMock()
        mock_response.content = json.dumps({"action": "allow", "reason": "looks fine"})

        with patch("langchain.chat_models.init_chat_model") as mock_llm:
            mock_llm.return_value.ainvoke = AsyncMock(return_value=mock_response)
            result = await supervisor.check(sample_session, "dev", "qa", "need help with tests?")

        assert result is None  # allow → 放行

    @pytest.mark.asyncio
    async def test_halt(self, supervisor, sample_session):
        """LLM 返回 halt → 拦截。"""
        mock_response = MagicMock()
        mock_response.content = json.dumps({"action": "halt", "reason": "infinite loop detected"})

        with patch("langchain.chat_models.init_chat_model") as mock_llm:
            mock_llm.return_value.ainvoke = AsyncMock(return_value=mock_response)
            result = await supervisor.check(sample_session, "dev", "qa", "help")

        assert result is not None
        assert result["action"] == "halt"
        assert "infinite loop" in result["reason"]

    @pytest.mark.asyncio
    async def test_warn(self, supervisor, sample_session):
        """LLM 返回 warn → 返回警告但不拦截。"""
        mock_response = MagicMock()
        mock_response.content = json.dumps({"action": "warn", "reason": "repetitive pattern"})

        with patch("langchain.chat_models.init_chat_model") as mock_llm:
            mock_llm.return_value.ainvoke = AsyncMock(return_value=mock_response)
            result = await supervisor.check(sample_session, "dev", "qa", "help again?")

        assert result is not None
        assert result["action"] == "warn"

    @pytest.mark.asyncio
    async def test_llm_failure_allows_by_default(self, supervisor, sample_session):
        """LLM 调用失败时默认放行，不阻塞协作。"""
        with patch("langchain.chat_models.init_chat_model") as mock_llm:
            mock_llm.return_value.ainvoke = AsyncMock(side_effect=RuntimeError("LLM down"))
            result = await supervisor.check(sample_session, "dev", "qa", "help")

        assert result is None  # 出错放行

    @pytest.mark.asyncio
    async def test_extracts_json_from_code_block(self, supervisor, sample_session):
        """从 ```json``` 代码块提取 JSON。"""
        mock_response = MagicMock()
        mock_response.content = '```json\n{"action": "halt", "reason": "dangerous"}\n```'

        with patch("langchain.chat_models.init_chat_model") as mock_llm:
            mock_llm.return_value.ainvoke = AsyncMock(return_value=mock_response)
            result = await supervisor.check(sample_session, "dev", "qa", "rm -rf /")

        assert result is not None
        assert result["action"] == "halt"


class TestSupervisorModes:

    @pytest.fixture
    def wsm(self):
        from app.gateway.manager.ws_manager import WSManager
        return WSManager()

    def test_hard_rules_max_rounds_halt(self, wsm):
        """超过最大轮次应被硬规则拦截。"""
        from app.config import config

        sess = {
            "session_id": "s1", "round": config.collab_max_rounds + 1,
            "chain": ["a", "b"], "started_at": time.time(),
        }
        result = wsm._check_hard_rules(sess, time.time(), "a", "b", "x")
        assert result is not None
        assert result["action"] == "halt"
        assert "轮次" in result["reason"]

    def test_hard_rules_max_depth_halt(self, wsm):
        """超过最大深度应被硬规则拦截。"""
        from app.config import config

        chain = [f"agent-{i}" for i in range(config.collab_max_depth + 2)]
        sess = {
            "session_id": "s1", "round": 1, "chain": chain,
            "started_at": time.time(),
        }
        result = wsm._check_hard_rules(sess, time.time(), chain[-2], chain[-1], "x")
        assert result is not None
        assert result["action"] == "halt"

    def test_hard_rules_pass(self, wsm):
        """正常范围内应放行。"""
        sess = {
            "session_id": "s1", "round": 1, "chain": ["a"],
            "started_at": time.time(), "seen_contents": set(),
        }
        result = wsm._check_hard_rules(sess, time.time(), "a", "b", "normal message")
        assert result is None

    def test_near_limit_below_threshold(self, wsm):
        """低于 80% 限制时 _near_limit 返回 False。"""
        sess = {"round": 1, "chain": ["a"], "started_at": time.time()}
        assert wsm._near_limit(sess, time.time()) is False

    def test_near_limit_above_threshold(self, wsm):
        """超过 80% 限制时 _near_limit 返回 True。"""
        from app.config import config

        sess = {
            "round": int(config.collab_max_rounds * 0.9),
            "chain": ["a"],
            "started_at": time.time() - config.collab_timeout * 0.9,
        }
        assert wsm._near_limit(sess, time.time()) is True
