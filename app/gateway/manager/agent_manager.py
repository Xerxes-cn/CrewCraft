"""Agent 进程生命周期管理。

处理：
- 从 data/agents/ 加载/保存 Agent 配置
- 按需启动 Agent 子进程
- 端口分配
- 跟踪运行中的 Agent
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
    """从 JSON 文件加载的 Agent 配置。

    system_prompt 在运行时从 data/agents/{name}.prompt.md 加载。
    工具不被存储 — 默认所有 Agent 都获得所有可用工具。
    自定义工具可以放在 data/agents/{name}/skills/ 目录中。
    """

    name: str
    model: str
    description: str = ""
    port: int = 0
    idle_timeout: int = 300
    created_at: str = ""

    @property
    def system_prompt(self) -> str:
        """从 .prompt.md 文件加载系统提示词。"""
        return self.load_prompt_file()

    def load_prompt_file(self, data_dir: Path | None = None) -> str:
        from app.agent.prompt_generator import load_prompt
        prompt = load_prompt(self.name, data_dir)
        if prompt:
            return prompt
        # 回退：如果提示词尚未生成则返回描述
        return self.description or ""

    @property
    def tools(self) -> list[str]:
        """所有 Agent 都获得所有内置工具 + 任何 Agent 特定的技能。"""
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
    """管理 Agent 配置和进程生命周期。"""

    def __init__(self, data_dir: Path | str | None = None):
        self.data_dir = Path(data_dir) if data_dir else config.data_dir
        self.agents_dir = self.data_dir / "agents"
        self.agents_dir.mkdir(parents=True, exist_ok=True)
        # agent_name -> asyncio.subprocess.Process 或 str（容器名称）
        self._processes: dict[str, Any] = {}
        # agent_name -> bool（WebSocket 已连接）
        self._online: dict[str, bool] = {}

    # ── 配置文件操作 ──────────────────────────────────────────────────

    def _config_path(self, name: str) -> Path:
        return self.agents_dir / f"{name}.json"

    def load_config(self, name: str) -> Optional[AgentConfig]:
        """从 JSON 文件加载 Agent 配置。"""
        path = self._config_path(name)
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        return AgentConfig.from_dict(data)

    def save_config(self, config: AgentConfig) -> None:
        """将 Agent 配置保存到 JSON 文件。"""
        path = self._config_path(config.name)
        path.write_text(json.dumps(config.to_dict(), indent=2, ensure_ascii=False))

    def delete_config(self, name: str) -> bool:
        """删除 Agent 配置文件。未找到则返回 False。"""
        path = self._config_path(name)
        if not path.exists():
            return False
        path.unlink()
        return True

    def list_configs(self) -> list[AgentConfig]:
        """列出 agents 目录下的所有 Agent 配置。"""
        configs = []
        for path in sorted(self.agents_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text())
                configs.append(AgentConfig.from_dict(data))
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Skipping invalid config {path}: {e}")
        return configs

    def next_port(self) -> int:
        """找到下一个可用端口。"""
        port = config.agent_port_start
        existing = {c.port for c in self.list_configs()}
        while port in existing:
            port += 1
        return port

    # ── 进程生命周期 ──────────────────────────────────────────────────

    async def start_agent(self, name: str) -> Optional[int]:
        """启动一个 Agent 进程/容器。返回端口号，失败则返回 None。"""
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
        """以本地子进程方式启动 Agent。"""
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
        """使用 Python Docker SDK 以 Docker 容器方式启动 Agent。"""
        container_name = f"crewcraft-agent-{name}"
        port = agent_config.port

        try:
            client = self._docker_client()
        except Exception as e:
            logger.error(f"Docker not available: {e}")
            return None

        # 检查容器是否已存在
        try:
            existing = client.containers.get(container_name)
            if existing.status == "running":
                logger.info(f"Docker agent {name} already running ({existing.id[:12]})")
                self._processes[name] = container_name
                self._online[name] = False
                return port
            # 移除已停止的容器
            existing.remove(force=True)
        except Exception:
            pass  # 未找到，正常

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
        """停止一个 Agent（子进程或 Docker 容器）。"""
        target = self._processes.pop(name, None)
        self._online.pop(name, None)

        if target is None:
            return

        if isinstance(target, str):
            # Docker 容器
            logger.info(f"Stopping Docker agent {name}")
            try:
                client = self._docker_client()
                container = client.containers.get(target)
                container.stop(timeout=5)
                container.remove()
            except Exception as e:
                logger.warning(f"Docker stop failed for {name}: {e}")
        else:
            # 子进程
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
        """获取 Docker 客户端。首次调用时缓存。"""
        import docker
        return docker.from_env()

    def is_running(self, name: str) -> bool:
        """检查 Agent 进程/容器是否正在运行。"""
        target = self._processes.get(name)
        if target is None:
            return False
        if isinstance(target, str):
            # Docker — 如果有名称则假设正在运行（可通过 docker ps 检查来增强）
            return True
        return target.returncode is None

    def set_online(self, name: str, online: bool):
        """标记 Agent 为在线/离线。"""
        self._online[name] = online

    def is_online(self, name: str) -> bool:
        """检查 Agent 是否在线（WebSocket 已连接）。"""
        return self._online.get(name, False)

    def is_running(self, name: str) -> bool:
        """检查 Agent 进程是否正在运行。"""
        proc = self._processes.get(name)
        return proc is not None and proc.returncode is None

    async def shutdown_all(self):
        """停止所有运行中的 Agent 进程。"""
        for name in list(self._processes.keys()):
            await self.stop_agent(name)


# 单例
agent_manager = AgentManager()
