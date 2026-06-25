"""Provider 注册表测试。"""

from app.agent.providers import get_provider, list_providers
from app.agent.providers.subprocess import SubprocessProvider
from app.agent.providers.docker import DockerProvider
from app.agent.providers.claude import ClaudeCodeProvider
from app.agent.providers.codex import CodexProvider
from app.agent.providers.openclaw import OpenClawProvider


def test_all_providers_registered():
    """测试所有 Provider 已注册。"""
    names = list_providers()
    assert "subprocess" in names
    assert "docker" in names
    assert "claude" in names
    assert "codex" in names
    assert "openclaw" in names
    assert len(names) == 5


def test_get_provider():
    """测试按名称获取 Provider。"""
    assert get_provider("subprocess") == SubprocessProvider
    assert get_provider("docker") == DockerProvider
    assert get_provider("claude") == ClaudeCodeProvider
    assert get_provider("unknown") is None


def test_provider_creation(temp_data_dir):
    """测试创建 Provider 实例。"""
    p = SubprocessProvider(data_dir=temp_data_dir)
    assert p is not None
    d = DockerProvider(data_dir=temp_data_dir)
    assert d is not None
