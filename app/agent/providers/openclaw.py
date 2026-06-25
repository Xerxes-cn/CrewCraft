"""OpenClaw Provider — 接入 OpenClaw CLI Agent。"""

import logging
from pathlib import Path

from .cli_base import CLIProvider

logger = logging.getLogger(__name__)


class OpenClawProvider(CLIProvider):
    """通过 OpenClaw CLI 运行 Agent 任务。"""

    executable = "openclaw"

    def _resolve_exe(self) -> str:
        import os
        return os.getenv("CREWCRAFT_OPENCLAW_PATH", self.executable)

    def build_args(self, task_file: Path) -> list[str]:
        return [
            self._resolve_exe(),
            "--task", str(task_file),
        ]
