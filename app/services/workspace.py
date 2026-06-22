import os
import re
import shutil
from pathlib import Path

from app.config import settings


def _sanitize(name: str) -> str:
    """Replace unsafe filesystem characters with underscores."""
    return re.sub(r"[^a-zA-Z0-9_一-鿿\-]", "_", name)[:64]


def crew_dir(crew_id: int, crew_name: str) -> Path:
    """Return the workspace path for a crew."""
    root = Path(settings.workspace_root).resolve()
    return root / f"{crew_id}_{_sanitize(crew_name)}"


def agent_dir(crew_id: int, crew_name: str, agent_name: str, order: int) -> Path:
    """Return the isolated workspace path for an agent."""
    return crew_dir(crew_id, crew_name) / f"{order:02d}_{_sanitize(agent_name)}"


def init_crew_workspace(crew_id: int, crew_name: str) -> Path:
    """Create the workspace directory for a crew. Returns the path."""
    path = crew_dir(crew_id, crew_name)
    path.mkdir(parents=True, exist_ok=True)
    return path


def init_agent_workspace(crew_id: int, crew_name: str, agent_name: str, order: int) -> Path:
    """Create the isolated workspace directory for an agent. Returns the path."""
    path = agent_dir(crew_id, crew_name, agent_name, order)
    path.mkdir(parents=True, exist_ok=True)
    # Create a README in the agent's directory
    readme = path / "README.txt"
    if not readme.exists():
        readme.write_text(
            f"Agent: {agent_name}\n"
            f"Crew: {crew_name}\n"
            f"This is an isolated workspace. Only this agent can access files here.\n",
            encoding="utf-8",
        )
    return path


def remove_crew_workspace(crew_id: int, crew_name: str) -> None:
    """Remove the entire workspace directory for a crew."""
    path = crew_dir(crew_id, crew_name)
    if path.exists():
        shutil.rmtree(path)


def remove_agent_workspace(crew_id: int, crew_name: str, agent_name: str, order: int) -> None:
    """Remove the workspace directory for a specific agent."""
    path = agent_dir(crew_id, crew_name, agent_name, order)
    if path.exists():
        shutil.rmtree(path)


def init_all_workspaces() -> None:
    """Ensure the workspace root directory exists."""
    root = Path(settings.workspace_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
