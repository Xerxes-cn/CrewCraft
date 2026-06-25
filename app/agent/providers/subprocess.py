"""Subprocess Provider — 本地子进程运行 Agent。"""

import asyncio
import logging

from .base import AgentProvider

logger = logging.getLogger(__name__)


class SubprocessProvider(AgentProvider):
    """以本地子进程方式运行 Agent（直接调用 Python）。"""

    def __init__(self, data_dir):
        super().__init__(data_dir)
        self._procs: dict[str, asyncio.subprocess.Process] = {}

    async def start(self, name: str, port: int, ws_url: str, **kwargs) -> bool:
        if name in self._procs and self._procs[name].returncode is None:
            logger.info(f"Agent {name} 已在运行（子进程）")
            return True

        logger.info(f"启动 Agent {name} 子进程，端口 {port}")
        env = self._env(name, port, ws_url)

        try:
            proc = await asyncio.create_subprocess_exec(
                "python", "-m", "app.agent.server",
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            self._procs[name] = proc
            await asyncio.sleep(0.5)
            return True
        except Exception as e:
            logger.error(f"启动子进程失败: {e}")
            return False

    async def stop(self, name: str) -> None:
        proc = self._procs.pop(name, None)
        if proc and proc.returncode is None:
            logger.info(f"停止 Agent {name} 子进程")
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=5)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()

    async def is_running(self, name: str) -> bool:
        proc = self._procs.get(name)
        return proc is not None and proc.returncode is None

    async def send_task(self, name: str, task_id: str, session_id: str,
                        content: str, config: dict) -> dict | None:
        """子进程 Agent 通过 WebSocket 通信，由 ws_manager 处理。"""
        return None  # ws_manager 直接发送，Provider 不介入
