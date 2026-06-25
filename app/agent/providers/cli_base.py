"""CLI Provider 基类 — 用于外部命令行 Agent 工具。"""

import asyncio
import json
import logging
import os
import tempfile
from pathlib import Path

from .base import AgentProvider

logger = logging.getLogger(__name__)


class CLIProvider(AgentProvider):
    """通过 CLI 子进程运行外部 Agent 的基类。

    子类只需定义：
    - executable: 可执行文件路径或命令名
    - build_args(): 构建命令行参数
    - build_prompt(): 构建完整 prompt（含 system_prompt + task）
    """

    executable: str = ""
    timeout: int = 300

    def __init__(self, data_dir):
        super().__init__(data_dir)
        self._procs: dict[str, asyncio.subprocess.Process] = {}
        self._task_files: dict[str, Path] = {}

    def _resolve_exe(self) -> str:
        """解析可执行文件路径，优先取环境变量。"""
        return self.executable

    def build_args(self, task_file: Path) -> list[str]:
        """构建 CLI 参数列表。子类重写。"""
        return [self._resolve_exe(), "--print", str(task_file)]

    def build_prompt(self, system_prompt: str, task: str) -> str:
        """构建完整 prompt。子类可重写。"""
        if system_prompt:
            return f"{system_prompt}\n\n---\n\nTask: {task}"
        return task

    async def start(self, name: str, port: int, ws_url: str, **kwargs) -> bool:
        """CLI Agent 不需要预启动，按任务执行。"""
        return True

    async def stop(self, name: str) -> None:
        proc = self._procs.pop(name, None)
        if proc and proc.returncode is None:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=5)
            except asyncio.TimeoutError:
                proc.kill()

    async def is_running(self, name: str) -> bool:
        return name in self._procs

    async def send_task(self, name: str, task_id: str, session_id: str,
                        content: str, config: dict) -> dict | None:
        """通过 CLI 执行任务。"""
        proc = self._procs.get(name)

        system_prompt = config.get("system_prompt", "")
        full_prompt = self.build_prompt(system_prompt, content)

        # 写入临时文件
        task_file = Path(tempfile.mktemp(suffix=".md", prefix=f"crewcraft-{name}-"))
        task_file.write_text(full_prompt)
        self._task_files[name] = task_file
        logger.info(f"CLI 任务文件: {task_file}")

        args = self.build_args(task_file)
        logger.info(f"执行: {' '.join(args)}")

        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            self._procs[name] = proc
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=self.timeout)

            output = stdout.decode("utf-8", errors="replace")[:10000]
            if proc.returncode != 0:
                err = stderr.decode("utf-8", errors="replace")[:1000]
                logger.warning(f"{self.executable} 退出码 {proc.returncode}: {err}")
                return {"task_id": task_id, "session_id": session_id,
                        "status": "failed", "error": err}

            return {"task_id": task_id, "session_id": session_id,
                    "status": "completed", "result": output}
        except asyncio.TimeoutError:
            return {"task_id": task_id, "session_id": session_id,
                    "status": "failed", "error": f"超时 ({self.timeout}s)"}
        except Exception as e:
            return {"task_id": task_id, "session_id": session_id,
                    "status": "failed", "error": str(e)}
