"""集中式配置 — 导入时一次性加载。

配置值从环境变量读取（支持 .env 文件），并缓存为普通属性，
使查找操作为 O(1)，无需重复调用 os.getenv。

用法：
    from app.config import config
    print(config.gateway_port)
"""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class Config:
    """应用配置 — 一次性读取环境变量并全部缓存。"""

    def __init__(self):
        self._load_dotenv()
        self._cache_values()
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

    # ── Cache all values once ─────────────────────────────────────────

    def _cache_values(self):
        get = os.getenv
        # 数据目录
        self.data_dir = Path(get("CREWCRAFT_DATA_DIR", "data"))
        # 网关 REST
        self.gateway_host = get("CREWCRAFT_GATEWAY_HOST", "127.0.0.1")
        self.gateway_port = int(get("CREWCRAFT_GATEWAY_PORT", "8000"))
        # 网关 WebSocket
        self.ws_host = get("CREWCRAFT_WS_HOST", "127.0.0.1")
        self.ws_port = int(get("CREWCRAFT_WS_PORT", "8765"))
        self.ws_url = f"ws://{self.ws_host}:{self.ws_port}"
        # Agent
        self.agent_deploy_mode = get("CREWCRAFT_AGENT_DEPLOY_MODE", "subprocess")  # subprocess | docker
        self.agent_port_start = int(get("CREWCRAFT_AGENT_PORT_START", "9001"))
        self.agent_idle_timeout = int(get("CREWCRAFT_AGENT_IDLE_TIMEOUT", "300"))
        self.agent_heartbeat_interval = int(get("CREWCRAFT_AGENT_HEARTBEAT_INTERVAL", "15"))
        # 日志
        self.log_level = get("CREWCRAFT_LOG_LEVEL", "INFO")

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
