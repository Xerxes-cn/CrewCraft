"""集中式配置 — 导入时一次性加载。

配置值从环境变量读取（支持 .env 文件），并缓存为普通属性，
使查找操作为 O(1)，无需重复调用 os.getenv。

用法：
    from app.config import config
    print(config.gateway_port)

所有字段在类级别声明类型注解，IDE 可正确推断引用类型。
"""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class Config:
    """应用配置 — 一次性读取环境变量并全部缓存。"""

    # 数据目录
    data_dir: Path = Path("data")

    # 网关 REST
    gateway_host: str = "127.0.0.1"
    gateway_port: int = 8000

    # 网关 WebSocket
    ws_host: str = "127.0.0.1"
    ws_port: int = 8765

    # Agent
    agent_deploy_mode: str = "subprocess"  # subprocess | docker
    agent_port_start: int = 9001
    agent_idle_timeout: int = 300
    agent_heartbeat_interval: int = 15

    # 协作监督
    collab_max_rounds: int = 10
    collab_max_depth: int = 3
    collab_timeout: int = 60
    collab_supervisor_mode: str = "hybrid"  # llm | hybrid | sampling

    # 日志
    log_level: str = "INFO"

    def __init__(self):
        self._load_dotenv()
        self._read_env()
        self._print_summary()

    # ── Dotenv ────────────────────────────────────────────────────────

    @staticmethod
    def _load_dotenv():
        try:
            from dotenv import load_dotenv
            root = Path(__file__).parent.parent
            env_file = root / ".env"
            if env_file.exists():
                load_dotenv(env_file)
        except ImportError:
            pass

    # ── Read env ──────────────────────────────────────────────────────

    def _read_env(self):
        get = os.getenv
        self.data_dir = Path(get("CREWCRAFT_DATA_DIR", "data"))
        self.gateway_host = get("CREWCRAFT_GATEWAY_HOST", "127.0.0.1")
        self.gateway_port = int(get("CREWCRAFT_GATEWAY_PORT", "8000"))
        self.ws_host = get("CREWCRAFT_WS_HOST", "127.0.0.1")
        self.ws_port = int(get("CREWCRAFT_WS_PORT", "8765"))
        self.agent_deploy_mode = get("CREWCRAFT_AGENT_DEPLOY_MODE", "subprocess")
        self.agent_port_start = int(get("CREWCRAFT_AGENT_PORT_START", "9001"))
        self.agent_idle_timeout = int(get("CREWCRAFT_AGENT_IDLE_TIMEOUT", "300"))
        self.agent_heartbeat_interval = int(get("CREWCRAFT_AGENT_HEARTBEAT_INTERVAL", "15"))
        self.collab_max_rounds = int(get("CREWCRAFT_COLLAB_MAX_ROUNDS", "10"))
        self.collab_max_depth = int(get("CREWCRAFT_COLLAB_MAX_DEPTH", "3"))
        self.collab_timeout = int(get("CREWCRAFT_COLLAB_TIMEOUT", "60"))
        self.collab_supervisor_mode = get("CREWCRAFT_COLLAB_SUPERVISOR_MODE", "hybrid")
        self.log_level = get("CREWCRAFT_LOG_LEVEL", "INFO")

    @property
    def ws_url(self) -> str:
        return f"ws://{self.ws_host}:{self.ws_port}"

    # ── Print summary ─────────────────────────────────────────────────

    def _print_summary(self):
        logger.info("Configuration loaded:")
        logger.info("  data_dir                = %s", self.data_dir)
        logger.info("  gateway                 = %s:%s", self.gateway_host, self.gateway_port)
        logger.info("  agent_ws                = %s", self.ws_url)
        logger.info("  agent_port_start        = %s", self.agent_port_start)
        logger.info("  agent_idle_timeout      = %ss", self.agent_idle_timeout)
        logger.info("  agent_heartbeat_interval = %ss", self.agent_heartbeat_interval)
        logger.info("  log_level               = %s", self.log_level)


# 单例 — 导入时创建一次，值永久缓存
config = Config()
