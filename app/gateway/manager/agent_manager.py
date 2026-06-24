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
from typing import Any, Optional

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
        self._processes: dict[str, Any] = {}  # asyncio.subprocess.Process or str (container name)
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
        """Start an agent process/container. Returns the port, or None on failure."""
        agent_config = self.load_config(name)
        if not agent_config:
            logger.error(f"Agent {name} not found")
            return None

        if self.is_running(name):
            logger.info(f"Agent {name} already running")
            return agent_config.port

        if agent_config.port == 0:
            agent_config.port = self.next_port()
            self.save_config(agent_config)

        mode = config.agent_deploy_mode
        if mode == "docker":
            return await self._start_docker(name, agent_config)
        else:
            return await self._start_subprocess(name, agent_config)

    async def _start_subprocess(self, name: str, agent_config) -> int:
        """Start agent as a local subprocess."""
        logger.info(f"Starting agent {name} on port {agent_config.port} (subprocess)")
        env = os.environ.copy()
        env["CREWCRAFT_AGENT_NAME"] = name
        env["CREWCRAFT_AGENT_PORT"] = str(agent_config.port)
        env["CREWCRAFT_DATA_DIR"] = str(self.data_dir)

        proc = await asyncio.create_subprocess_exec(
            "python", "-m", "app.agent.server",
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self._processes[name] = proc
        self._online[name] = False
        await asyncio.sleep(0.5)
        return agent_config.port

    async def _start_docker(self, name: str, agent_config) -> Optional[int]:
        """Start agent as a Docker container using Python Docker SDK."""
        container_name = f"crewcraft-agent-{name}"
        port = agent_config.port

        try:
            client = self._docker_client()
        except Exception as e:
            logger.error(f"Docker not available: {e}")
            return None

        # Check if container already exists
        try:
            existing = client.containers.get(container_name)
            if existing.status == "running":
                logger.info(f"Docker agent {name} already running ({existing.id[:12]})")
                self._processes[name] = container_name
                self._online[name] = False
                return port
            # Remove stopped container
            existing.remove(force=True)
        except Exception:
            pass  # Not found, ok

        logger.info(f"Starting agent {name} on port {port} (docker)")

        try:
            container = client.containers.run(
                image="crewcraft-agent",
                name=container_name,
                detach=True,
                ports={f"{port}/tcp": port},
                environment={
                    "CREWCRAFT_AGENT_NAME": name,
                    "CREWCRAFT_AGENT_PORT": str(port),
                    "CREWCRAFT_GATEWAY_WS": f"ws://host.docker.internal:{config.ws_port}",
                    "CREWCRAFT_DATA_DIR": "/data",
                },
                volumes={str(self.data_dir.absolute()): {"bind": "/data", "mode": "rw"}},
                remove=False,
            )
            logger.info(f"Docker container {container.id[:12]} started for {name}")
        except Exception as e:
            logger.error(f"Docker run failed: {e}")
            return None

        self._processes[name] = container_name
        self._online[name] = False
        return port

    async def stop_agent(self, name: str) -> None:
        """Stop an agent (subprocess or docker container)."""
        target = self._processes.pop(name, None)
        self._online.pop(name, None)

        if target is None:
            return

        if isinstance(target, str):
            # Docker container
            logger.info(f"Stopping Docker agent {name}")
            try:
                client = self._docker_client()
                container = client.containers.get(target)
                container.stop(timeout=5)
                container.remove()
            except Exception as e:
                logger.warning(f"Docker stop failed for {name}: {e}")
        else:
            # Subprocess
            if target.returncode is None:
                logger.info(f"Stopping agent {name}")
                target.terminate()
                try:
                    await asyncio.wait_for(target.wait(), timeout=5)
                except asyncio.TimeoutError:
                    logger.warning(f"Agent {name} didn't exit, killing")
                    target.kill()
                    await target.wait()

    @staticmethod
    def _docker_client():
        """Get a Docker client. Cached on first call."""
        import docker
        return docker.from_env()

    def is_running(self, name: str) -> bool:
        """Check if agent process/container is running."""
        target = self._processes.get(name)
        if target is None:
            return False
        if isinstance(target, str):
            # Docker — assume running if we have a name (could enhance with docker ps check)
            return True
        return target.returncode is None

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
