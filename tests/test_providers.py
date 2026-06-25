"""Provider 注册表与各 Provider 实例化测试。

不启动真实进程或容器，只测试 API 行为。
"""

import asyncio
import pytest

from app.agent.providers import get_provider, list_providers
from app.agent.providers.base import AgentProvider
from app.agent.providers.subprocess import SubprocessProvider
from app.agent.providers.docker import DockerProvider
from app.agent.providers.claude import ClaudeCodeProvider
from app.agent.providers.codex import CodexProvider
from app.agent.providers.openclaw import OpenClawProvider


# ── 注册表 ──────────────────────────────────────────────────────────────


class TestRegistry:

    EXPECTED_PROVIDERS = {"subprocess", "docker", "claude", "codex", "openclaw"}

    def test_all_providers_registered(self):
        names = set(list_providers())
        missing = self.EXPECTED_PROVIDERS - names
        assert not missing, f"Missing providers: {missing}"

    def test_list_providers_sorted(self):
        names = list_providers()
        assert names == sorted(names)

    def test_get_known_provider(self):
        assert get_provider("subprocess") == SubprocessProvider
        assert get_provider("docker") == DockerProvider
        assert get_provider("claude") == ClaudeCodeProvider
        assert get_provider("codex") == CodexProvider
        assert get_provider("openclaw") == OpenClawProvider

    def test_get_unknown_provider_returns_none(self):
        assert get_provider("nonexistent") is None
        assert get_provider("") is None


# ── 实例化 ──────────────────────────────────────────────────────────────


class TestInstantiation:

    PROVIDER_CLASSES = [SubprocessProvider, DockerProvider, ClaudeCodeProvider,
                        CodexProvider, OpenClawProvider]

    @pytest.mark.parametrize("provider_cls", PROVIDER_CLASSES)
    def test_all_providers_instantiable(self, provider_cls, tmp_path):
        p = provider_cls(data_dir=tmp_path)
        assert p is not None
        assert p.data_dir == tmp_path

    @pytest.mark.parametrize("provider_cls", PROVIDER_CLASSES)
    def test_all_providers_inherit_from_base(self, provider_cls):
        assert issubclass(provider_cls, AgentProvider)


# ── SubprocessProvider ───────────────────────────────────────────────────


class TestSubprocessProvider:

    @pytest.fixture
    def sp(self, tmp_path):
        return SubprocessProvider(data_dir=tmp_path)

    def test_env_contains_required_keys(self, sp):
        env = sp._env(name="test-agent", port=9999, ws_url="ws://localhost:8765")
        assert env["CREWCRAFT_AGENT_NAME"] == "test-agent"
        assert env["CREWCRAFT_AGENT_PORT"] == "9999"
        assert env["CREWCRAFT_GATEWAY_WS"] == "ws://localhost:8765"
        assert "CREWCRAFT_DATA_DIR" in env

    def test_env_includes_system_env(self, sp, monkeypatch):
        monkeypatch.setenv("MY_CUSTOM_VAR", "custom_value")
        env = sp._env(name="a", port=1, ws_url="ws://x")
        assert env["MY_CUSTOM_VAR"] == "custom_value"

    async def test_is_running_unknown(self, sp):
        assert await sp.is_running("nonexistent") is False

    async def test_send_task_returns_none(self, sp):
        """WebSocket Agent 由 ws_manager 处理，send_task 返回 None。"""
        result = await sp.send_task("any", "t1", "s1", "content", {})
        assert result is None

    async def test_stop_unknown_does_not_crash(self, sp):
        """停止不存在的 Agent 不抛异常。"""
        await sp.stop("nonexistent")

    async def test_start_and_stop_lifecycle(self, sp):
        """启动/停止的生命周期管理（start 会尝试创建子进程，预期失败但不崩溃）。"""
        ok = await sp.start(name="test", port=9999, ws_url="ws://localhost:8765")
        # 子进程启动可能成功也可能失败（取决于 Python 环境），
        # 但不应该抛异常。
        assert isinstance(ok, bool)
        await sp.stop("test")


# ── DockerProvider ──────────────────────────────────────────────────────


class TestDockerProvider:

    @pytest.fixture
    def dp(self, tmp_path):
        return DockerProvider(data_dir=tmp_path)

    def test_env_contains_docker_keys(self, dp):
        env = dp._env(name="docker-agent", port=9999, ws_url="ws://localhost:8765")
        assert env["CREWCRAFT_AGENT_NAME"] == "docker-agent"
        assert env["CREWCRAFT_AGENT_PORT"] == "9999"

    async def test_is_running_unknown(self, dp):
        assert await dp.is_running("nonexistent") is False


# ── CLI Providers (claude/codex/openclaw) ────────────────────────────────


class TestCLIProviders:

    @pytest.mark.parametrize("provider_cls", [
        ClaudeCodeProvider, CodexProvider, OpenClawProvider,
    ])
    def test_instantiation(self, provider_cls, tmp_path):
        p = provider_cls(data_dir=tmp_path)
        assert p is not None

    @pytest.mark.parametrize("provider_cls", [
        ClaudeCodeProvider, CodexProvider, OpenClawProvider,
    ])
    async def test_is_running_unknown(self, provider_cls, tmp_path):
        p = provider_cls(data_dir=tmp_path)
        assert await p.is_running("nonexistent") is False

    @pytest.mark.parametrize("provider_cls", [
        ClaudeCodeProvider, CodexProvider, OpenClawProvider,
    ])
    async def test_send_task_not_implemented_or_none(self, provider_cls, tmp_path):
        """CLI providers 可能抛 NotImplementedError 或返回 None。"""
        p = provider_cls(data_dir=tmp_path)
        try:
            result = await p.send_task("any", "t1", "s1", "content", {})
            assert result is None or isinstance(result, dict)
        except NotImplementedError:
            pass  # 允许未实现
