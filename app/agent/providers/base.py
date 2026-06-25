"""AgentProvider 抽象基类。"""

import asyncio
import logging
from abc import ABC, abstractmethod
from pathlib import Path

logger = logging.getLogger(__name__)


class AgentProvider(ABC):
    """外部 Agent 的适配器接口。

    Gateway 通过此接口管理 Agent 生命周期，不关心底层
    是子进程、Docker 容器还是外部 CLI 工具。
    """

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir

    @abstractmethod
    async def start(self, name: str, port: int, ws_url: str, **kwargs) -> bool:
        """启动 Agent。返回是否成功。"""
        ...

    @abstractmethod
    async def stop(self, name: str) -> None:
        """停止 Agent。"""
        ...

    @abstractmethod
    async def is_running(self, name: str) -> bool:
        """检查 Agent 是否在运行。"""
        ...

    @abstractmethod
    async def send_task(self, name: str, task_id: str, session_id: str,
                        content: str, config: dict) -> dict | None:
        """向 Agent 发送任务。返回结果字典或 None（失败时）。"""
        ...

    def _env(self, name: str, port: int, ws_url: str) -> dict:
        """构建标准环境变量。"""
        import os
        env = os.environ.copy()
        env["CREWCRAFT_AGENT_NAME"] = name
        env["CREWCRAFT_AGENT_PORT"] = str(port)
        env["CREWCRAFT_GATEWAY_WS"] = ws_url
        env["CREWCRAFT_DATA_DIR"] = str(self.data_dir)
        return env
