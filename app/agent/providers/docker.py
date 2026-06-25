"""Docker Provider — 以容器方式运行 Agent。"""

import logging

from .base import AgentProvider

logger = logging.getLogger(__name__)
CONTAINER_PREFIX = "crewcraft-agent"


class DockerProvider(AgentProvider):
    """以 Docker 容器方式运行 Agent。"""

    def __init__(self, data_dir):
        super().__init__(data_dir)
        self._client = None

    def _get_client(self):
        if self._client is None:
            import docker
            self._client = docker.from_env()
        return self._client

    def _container_name(self, name: str) -> str:
        return f"{CONTAINER_PREFIX}-{name}"

    async def start(self, name: str, port: int, ws_url: str, **kwargs) -> bool:
        try:
            client = self._get_client()
        except Exception as e:
            logger.error(f"Docker 不可用: {e}")
            return False

        cname = self._container_name(name)
        try:
            existing = client.containers.get(cname)
            if existing.status == "running":
                logger.info(f"Docker Agent {name} 已在运行 ({existing.id[:12]})")
                return True
            existing.remove(force=True)
        except Exception:
            pass

        logger.info(f"启动 Docker Agent {name}，端口 {port}")
        try:
            container = client.containers.run(
                image="crewcraft-agent",
                name=cname,
                detach=True,
                ports={f"{port}/tcp": port},
                environment={
                    "CREWCRAFT_AGENT_NAME": name,
                    "CREWCRAFT_AGENT_PORT": str(port),
                    "CREWCRAFT_GATEWAY_WS": ws_url,
                    "CREWCRAFT_DATA_DIR": "/data",
                },
                volumes={str(self.data_dir.absolute()): {"bind": "/data", "mode": "rw"}},
                remove=False,
            )
            logger.info(f"Docker 容器 {container.id[:12]} 已启动")
            return True
        except Exception as e:
            logger.error(f"Docker 启动失败: {e}")
            return False

    async def stop(self, name: str) -> None:
        cname = self._container_name(name)
        logger.info(f"停止 Docker Agent {name}")
        try:
            client = self._get_client()
            container = client.containers.get(cname)
            container.stop(timeout=5)
            container.remove()
        except Exception as e:
            logger.warning(f"Docker 停止失败: {e}")

    async def is_running(self, name: str) -> bool:
        try:
            client = self._get_client()
            container = client.containers.get(self._container_name(name))
            return container.status == "running"
        except Exception:
            return False

    async def send_task(self, name: str, task_id: str, session_id: str,
                        content: str, config: dict) -> dict | None:
        return None  # 由 ws_manager 处理
