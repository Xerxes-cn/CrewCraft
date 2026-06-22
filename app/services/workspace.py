import re
import shutil
from pathlib import Path

from app.config import settings


def _sanitize(name: str) -> str:
    """Replace unsafe filesystem characters with underscores."""
    return re.sub(r"[^a-zA-Z0-9_一-鿿\-]", "_", name)[:64]


def agent_dir(agent_id: int, agent_name: str, order: int) -> Path:
    """Return the isolated workspace path for an agent."""
    root = Path(settings.workspace_root).resolve()
    return root / f"{order:02d}_{_sanitize(agent_name)}"


def init_agent_workspace(agent_id: int, agent_name: str, order: int) -> Path:
    """Create the isolated workspace directory for an agent. Returns the path."""
    path = agent_dir(agent_id, agent_name, order)
    path.mkdir(parents=True, exist_ok=True)
    readme = path / "README.txt"
    if not readme.exists():
        readme.write_text(
            f"Agent: {agent_name}\n"
            f"这是该 Agent 的独立工作区，仅此 Agent 可访问其中文件。\n",
            encoding="utf-8",
        )
    return path


def remove_agent_workspace(agent_id: int, agent_name: str, order: int) -> None:
    """Remove the workspace directory for a specific agent."""
    path = agent_dir(agent_id, agent_name, order)
    if path.exists():
        shutil.rmtree(path)


def init_all_workspaces() -> None:
    """Ensure the workspace root directory exists."""
    root = Path(settings.workspace_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
