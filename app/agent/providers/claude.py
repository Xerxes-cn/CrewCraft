"""Claude Code Provider — 接入 Anthropic Claude Code CLI。"""

import logging
from pathlib import Path

from .cli_base import CLIProvider

logger = logging.getLogger(__name__)


class ClaudeCodeProvider(CLIProvider):
    """通过 Claude Code CLI 运行 Agent 任务。"""

    executable = "claude"

    def _resolve_exe(self) -> str:
        import os
        return os.getenv("CREWCRAFT_CLAUDE_PATH", self.executable)

    def build_args(self, task_file: Path) -> list[str]:
        return [
            self._resolve_exe(),
            "--print",                      # 非交互模式
            "--dangerously-skip-permissions",  # 自动批准（审批由 CrewCraft 管理）
            str(task_file),
        ]
