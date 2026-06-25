"""Codex Provider — 接入 OpenAI Codex CLI。"""

import logging
from pathlib import Path

from .cli_base import CLIProvider

logger = logging.getLogger(__name__)


class CodexProvider(CLIProvider):
    """通过 Codex CLI 运行 Agent 任务。"""

    executable = "codex"

    def _resolve_exe(self) -> str:
        import os
        return os.getenv("CREWCRAFT_CODEX_PATH", self.executable)

    def build_args(self, task_file: Path) -> list[str]:
        return [
            self._resolve_exe(),
            "exec",                         # 执行模式
            "--approval-mode", "auto",      # 自动审批
            str(task_file),
        ]
