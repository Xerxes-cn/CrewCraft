"""Agent process lifecycle management.

Handles:
- Loading/saving agent configs from data/agents/
- Spawning agent subprocesses on demand
- Port allocation
- Tracking running agents
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.config import config

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """Agent configuration loaded from JSON file.

    system_prompt is loaded from data/agents/{name}.prompt.md at runtime.
    tools are NOT stored — all agents get all available tools by default.
    Custom tools can be placed in data/agents/{name}/skills/.
    """

    name: str
    model: str
    description: str = ""
    port: int = 0
    idle_timeout: int = 300
    created_at: str = ""

    @property
    def system_prompt(self) -> str:
        """Load system prompt from .prompt.md file."""
        return self.load_prompt_file()

    def load_prompt_file(self, data_dir: Path | None = None) -> str:
        from app.agent.prompt_generator import load_prompt
        prompt = load_prompt(self.name, data_dir)
        if prompt:
            return prompt
        # Fallback: return description if prompt not yet generated
        return self.description or ""

    @property
    def tools(self) -> list[str]:
        """All agents get all built-in tools + any agent-specific skills."""
        from app.agent.tools import registry
        return registry.list_names()

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "model": self.model,
            "description": self.description,
            "port": self.port,
            "idle_timeout": self.idle_timeout,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AgentConfig":
        return cls(
            name=data["name"],
            model=data["model"],
            description=data.get("description", data.get("system_prompt", "")),
            port=data.get("port", 0),
            idle_timeout=data.get("idle_timeout", 300),
            created_at=data.get("created_at", ""),
        )


class AgentManager:
    """Manages agent configuration and process lifecycle."""

    def __init__(self, data_dir: Path | str | None = None):
        self.data_dir = Path(data_dir) if data_dir else config.data_dir
        self.agents_dir = self.data_dir / "agents"
        self.agents_dir.mkdir(parents=True, exist_ok=True)
        # agent_name -> asyncio.subprocess.Process
        self._processes: dict[str, asyncio.subprocess.Process] = {}
        # agent_name -> bool (WebSocket connected)
        self._online: dict[str, bool] = {}

    # ── Config file operations ──────────────────────────────────────────

    def _config_path(self, name: str) -> Path:
        return self.agents_dir / f"{name}.json"

    def load_config(self, name: str) -> Optional[AgentConfig]:
        """Load agent config from JSON file."""
        path = self._config_path(name)
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        return AgentConfig.from_dict(data)

    def save_config(self, config: AgentConfig) -> None:
        """Save agent config to JSON file."""
        path = self._config_path(config.name)
        path.write_text(json.dumps(config.to_dict(), indent=2, ensure_ascii=False))

    def delete_config(self, name: str) -> bool:
        """Delete agent config file. Returns False if not found."""
        path = self._config_path(name)
        if not path.exists():
            return False
        path.unlink()
        return True

    def list_configs(self) -> list[AgentConfig]:
        """List all agent configs from the agents directory."""
        configs = []
        for path in sorted(self.agents_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text())
                configs.append(AgentConfig.from_dict(data))
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Skipping invalid config {path}: {e}")
        return configs

    def next_port(self) -> int:
        """Find the next available port."""
        port = config.agent_port_start
        existing = {c.port for c in self.list_configs()}
        while port in existing:
            port += 1
        return port

    # ── Process lifecycle ────────────────────────────────────────────────

    async def start_agent(self, name: str) -> Optional[int]:
        """Start an agent subprocess. Returns the port, or None on failure."""
        config = self.load_config(name)
        if not config:
            logger.error(f"Agent {name} not found")
            return None

        if name in self._processes and self._processes[name].returncode is None:
            logger.info(f"Agent {name} already running")
            return config.port

        if config.port == 0:
            config.port = self.next_port()
            self.save_config(config)

        logger.info(f"Starting agent {name} on port {config.port}")

        env = os.environ.copy()
        env["CREWCRAFT_AGENT_NAME"] = name
        env["CREWCRAFT_AGENT_PORT"] = str(config.port)
        env["CREWCRAFT_DATA_DIR"] = str(self.data_dir)

        proc = await asyncio.create_subprocess_exec(
            "python", "-m", "app.agent.server",
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self._processes[name] = proc
        self._online[name] = False

        # Brief wait for the agent to start
        await asyncio.sleep(0.5)
        return config.port

    async def stop_agent(self, name: str) -> None:
        """Stop an agent subprocess."""
        proc = self._processes.pop(name, None)
        self._online.pop(name, None)
        if proc and proc.returncode is None:
            logger.info(f"Stopping agent {name}")
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=5)
            except asyncio.TimeoutError:
                logger.warning(f"Agent {name} didn't exit, killing")
                proc.kill()
                await proc.wait()

    def set_online(self, name: str, online: bool):
        """Mark an agent as online/offline."""
        self._online[name] = online

    def is_online(self, name: str) -> bool:
        """Check if an agent is online (WebSocket connected)."""
        return self._online.get(name, False)

    def is_running(self, name: str) -> bool:
        """Check if agent process is running."""
        proc = self._processes.get(name)
        return proc is not None and proc.returncode is None

    async def shutdown_all(self):
        """Stop all running agent processes."""
        for name in list(self._processes.keys()):
            await self.stop_agent(name)


# Singleton
agent_manager = AgentManager()
