"""共享 fixtures — 所有测试模块的基础设施。"""

import pytest

from app.models import InboundMsg, OutboundMsg, TaskRequest, ChannelConfig


# ── 环境与目录 ──────────────────────────────────────────────────────────


@pytest.fixture
def temp_data_dir(tmp_path, monkeypatch):
    """临时数据目录，自动 monkeypatch CREWCRAFT_DATA_DIR 环境变量。

    使用 pytest 内置 tmp_path（基于系统的临时目录），
    monkeypatch 保证测试失败时也不会污染环境。
    """
    data_dir = tmp_path / "data"
    monkeypatch.setenv("CREWCRAFT_DATA_DIR", str(data_dir))
    return data_dir


@pytest.fixture
def agent_manager(temp_data_dir):
    """AgentManager 实例，指向临时数据目录。"""
    from app.gateway.manager.agent_manager import AgentManager
    return AgentManager(data_dir=temp_data_dir)


@pytest.fixture
def sample_agent_config():
    """示例 Agent 配置 — 所有字段均填充。"""
    from app.gateway.manager.agent_manager import AgentConfig
    return AgentConfig(
        name="test-agent",
        model="openai:gpt-4o",
        description="测试 agent",
        provider="subprocess",
        port=9001,
        idle_timeout=300,
        created_at="2025-01-01T00:00:00Z",
    )


# ── 消息模型 ────────────────────────────────────────────────────────────


@pytest.fixture
def sample_inbound_msg():
    """标准入站消息。"""
    return InboundMsg(
        channel="cli",
        sender_id="user-1",
        chat_id="chat-1",
        content="Hello, world!",
        media=["/tmp/img.jpg"],
        metadata={"msg_type": "text"},
    )


@pytest.fixture
def sample_outbound_msg():
    """标准出站消息。"""
    return OutboundMsg(
        channel="cli",
        chat_id="chat-1",
        content="Hello back!",
        media=[],
        metadata={},
    )


@pytest.fixture
def sample_task_request():
    """标准任务请求。"""
    return TaskRequest(
        content="Write a Python script",
        agent_name="dev-agent",
        channel="cli",
        chat_id="chat-1",
    )


@pytest.fixture
def sample_channel_config():
    """标准 Channel 配置字典。"""
    return {
        "type": "cli",
        "name": "cli-default",
        "enabled": True,
    }


# ── Approval 队列清理 ───────────────────────────────────────────────────


@pytest.fixture
def clear_approvals():
    """确保测试前后审批队列为空。"""
    from app.gateway.api.approvals import clear_queue, get_queue_size
    clear_queue()
    assert get_queue_size() == 0
    yield
    clear_queue()


# ── 工具注册表（不修改全局状态）─────────────────────────────────────────


@pytest.fixture
def fresh_registry():
    """独立的空工具注册表，不污染全局单例。"""
    from app.agent.tools.registry import ToolRegistry
    return ToolRegistry()


@pytest.fixture
def sample_tool():
    """示例工具。"""
    from app.agent.tools.registry import Tool

    def dummy_func(x: int = 0) -> str:
        return f"result:{x}"

    return Tool(
        name="dummy",
        description="A dummy tool for testing",
        func=dummy_func,
        parameters={"x": {"type": "integer", "description": "Input"}},
        permission="safe",
    )
