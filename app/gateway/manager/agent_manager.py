"""Agent 生命周期管理。

通过可插拔的 Provider 系统管理 Agent：
- 从 data/agents/ 加载/保存配置
- 按需启动 Agent（子进程/Docker/CLI 外部工具）
- 端口分配
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.config import config

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """Agent 配置（从 JSON 文件加载）。

    system_prompt 从 data/agents/{name}.prompt.md 运行时加载。
    tools 不存储 — 所有 Agent 默认可用全部内置工具。
    """

    name: str
    model: str
    description: str = ""
    provider: str = ""  # subprocess | docker | claude | codex | openclaw
    port: int = 0
    idle_timeout: int = 300
    created_at: str = ""

    @property
    def system_prompt(self) -> str:
        return self.load_prompt_file()

    def load_prompt_file(self, data_dir: Path | None = None) -> str:
        from app.agent.prompt_generator import load_prompt
        prompt = load_prompt(self.name, data_dir)
        return prompt or self.description or ""

    @property
    def tools(self) -> list[str]:
        from app.agent.tools import registry
        return registry.list_names()

    def to_dict(self) -> dict:
        return {
            "name": self.name, "model": self.model,
            "description": self.description, "provider": self.provider,
            "port": self.port, "idle_timeout": self.idle_timeout,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AgentConfig":
        return cls(
            name=data["name"], model=data["model"],
            description=data.get("description", data.get("system_prompt", "")),
            provider=data.get("provider", ""),
            port=data.get("port", 0), idle_timeout=data.get("idle_timeout", 300),
            created_at=data.get("created_at", ""),
        )


class AgentManager:
    """管理 Agent 配置和生命周期。"""

    def __init__(self, data_dir: Path | str | None = None):
        self.data_dir = Path(data_dir) if data_dir else config.data_dir
        self.agents_dir = self.data_dir / "agents"
        self.agents_dir.mkdir(parents=True, exist_ok=True)
        self._online: dict[str, bool] = {}
        self._provider_instances: dict[str, object] = {}

    # ── 配置持久化 ────────────────────────────────────────────────────

    def _config_dir(self, name: str, create: bool = False) -> Path:
        """返回 data/agents/{name}/ 目录。create=True 时自动创建。"""
        d = self.agents_dir / name
        if create:
            d.mkdir(parents=True, exist_ok=True)
        return d

    def _config_path(self, name: str, create: bool = False) -> Path:
        return self._config_dir(name, create=create) / "config.json"

    def load_config(self, name: str) -> Optional[AgentConfig]:
        path = self._config_path(name)
        if not path.exists():
            return None
        return AgentConfig.from_dict(json.loads(path.read_text()))

    def save_config(self, config: AgentConfig) -> None:
        self._config_dir(config.name, create=True)
        self._config_path(config.name, create=True).write_text(
            json.dumps(config.to_dict(), indent=2, ensure_ascii=False))

    def delete_config(self, name: str) -> bool:
        """软删除：将配置移到 data/agents/deleted/{name}_{timestamp}_{unique}/ 目录。

        时间戳+随机后缀避免同名 Agent 重复删除时的冲突。
        """
        d = self.agents_dir / name
        if not d.exists():
            return False
        import shutil
        import uuid
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).strftime(config.timestamp_format)
        uid = uuid.uuid4().hex[:6]
        deleted_dir = self.agents_dir / "deleted" / f"{name}_{ts}_{uid}"
        deleted_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(d), str(deleted_dir))
        logger.info(f"已软删除 Agent '{name}' → {deleted_dir}")
        return True

    def list_configs(self) -> list[AgentConfig]:
        configs = []
        for d in sorted(self.agents_dir.iterdir()):
            if not d.is_dir():
                continue
            path = d / "config.json"
            if path.exists():
                try:
                    configs.append(AgentConfig.from_dict(json.loads(path.read_text())))
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"跳过无效配置 {path}: {e}")
        return configs

    def next_port(self) -> int:
        port = config.agent_port_start
        existing = {c.port for c in self.list_configs()}
        while port in existing:
            port += 1
        return port

    # ── Provider ──────────────────────────────────────────────────────

    def _get_provider(self, name: str):
        """获取 Agent 对应的 Provider 实例。"""
        from app.agent.providers import get_provider, SubprocessProvider

        agent_config = self.load_config(name)
        provider_name = (agent_config.provider if agent_config and agent_config.provider
                         else config.agent_deploy_mode)

        provider_cls = get_provider(provider_name)
        if provider_cls is None:
            logger.warning(f"Provider '{provider_name}' 未找到，使用 subprocess")
            provider_cls = SubprocessProvider
            provider_name = "subprocess"

        if provider_name not in self._provider_instances:
            self._provider_instances[provider_name] = provider_cls(self.data_dir)
        return self._provider_instances[provider_name]

    # ── 生命周期 ──────────────────────────────────────────────────────

    async def start_agent(self, name: str) -> Optional[int]:
        agent_config = self.load_config(name)
        if not agent_config:
            logger.error(f"Agent {name} 未找到")
            return None

        provider = self._get_provider(name)
        provider_name = agent_config.provider or config.agent_deploy_mode

        # CLI Provider 不需要端口
        if provider_name in ("claude", "codex", "openclaw"):
            self._online[name] = True
            return 0

        if self._online.get(name):
            logger.info(f"Agent {name} 已在线")
            return agent_config.port

        if agent_config.port == 0:
            agent_config.port = self.next_port()
            self.save_config(agent_config)

        ws_url = config.ws_url
        ok = await provider.start(name, agent_config.port, ws_url)
        if not ok:
            return None
        self._online[name] = False
        return agent_config.port

    async def stop_agent(self, name: str) -> None:
        self._online.pop(name, None)
        try:
            provider = self._get_provider(name)
            await provider.stop(name)
        except Exception as e:
            logger.warning(f"停止 Agent {name} 失败: {e}")

    def set_online(self, name: str, online: bool):
        self._online[name] = online

    def is_online(self, name: str) -> bool:
        return self._online.get(name, False)

    async def shutdown_all(self):
        for name in list(self._online.keys()):
            await self.stop_agent(name)


# 单例
agent_manager = AgentManager()
