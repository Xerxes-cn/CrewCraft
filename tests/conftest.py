"""共享 fixtures。"""

import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_data_dir():
    """创建临时数据目录。"""
    with tempfile.TemporaryDirectory() as tmp:
        old = os.environ.get("CREWCRAFT_DATA_DIR")
        os.environ["CREWCRAFT_DATA_DIR"] = tmp
        yield Path(tmp)
        if old:
            os.environ["CREWCRAFT_DATA_DIR"] = old


@pytest.fixture
def sample_agent_config():
    """示例 Agent 配置。"""
    from app.gateway.manager.agent_manager import AgentConfig
    return AgentConfig(
        name="test-agent",
        model="openai:gpt-4o",
        description="测试 agent",
        port=9001,
    )
