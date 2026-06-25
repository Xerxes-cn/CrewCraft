"""Agent Provider 注册表。

每个 Provider 实现 Agent 的启动/停止/任务发送。
Gateway 通过此模块按 deploy_mode 选择对应的 Provider。
"""

from .base import AgentProvider
from .subprocess import SubprocessProvider
from .docker import DockerProvider
from .claude import ClaudeCodeProvider
from .codex import CodexProvider
from .openclaw import OpenClawProvider

# 注册表：provider_name → Provider 类
_registry: dict[str, type[AgentProvider]] = {
    "subprocess": SubprocessProvider,
    "docker": DockerProvider,
    "claude": ClaudeCodeProvider,
    "codex": CodexProvider,
    "openclaw": OpenClawProvider,
}


def get_provider(name: str) -> type[AgentProvider] | None:
    """根据名称获取 Provider 类。"""
    return _registry.get(name)


def list_providers() -> list[str]:
    """列出所有已注册的 Provider。"""
    return sorted(_registry.keys())


__all__ = [
    "AgentProvider",
    "SubprocessProvider",
    "DockerProvider",
    "ClaudeCodeProvider",
    "CodexProvider",
    "OpenClawProvider",
    "get_provider",
    "list_providers",
]
