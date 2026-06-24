"""Centralized configuration loaded from environment variables.

Loads .env file via python-dotenv. All settings have sensible defaults.
Usage:
    from app.config import config
    print(config.gateway_host)
"""

import os
from pathlib import Path

_loaded = False


def _load_dotenv():
    """Load .env file from project root if it exists."""
    global _loaded
    if _loaded:
        return
    _loaded = True

    try:
        from dotenv import load_dotenv
        # Look for .env in project root (two levels up from this file)
        root = Path(__file__).parent.parent
        env_file = root / ".env"
        if env_file.exists():
            load_dotenv(env_file)
    except ImportError:
        pass


class Config:
    """Application configuration — reads from env vars with defaults."""

    def __init__(self):
        _load_dotenv()

    # ── Data ──────────────────────────────────────────────────────────

    @property
    def data_dir(self) -> Path:
        return Path(os.getenv("CREWCRAFT_DATA_DIR", "data"))

    # ── Gateway REST ──────────────────────────────────────────────────

    @property
    def gateway_host(self) -> str:
        return os.getenv("CREWCRAFT_GATEWAY_HOST", "127.0.0.1")

    @property
    def gateway_port(self) -> int:
        return int(os.getenv("CREWCRAFT_GATEWAY_PORT", "8000"))

    # ── Gateway WebSocket (for agent connections) ─────────────────────

    @property
    def ws_host(self) -> str:
        return os.getenv("CREWCRAFT_WS_HOST", "127.0.0.1")

    @property
    def ws_port(self) -> int:
        return int(os.getenv("CREWCRAFT_WS_PORT", "8765"))

    @property
    def ws_url(self) -> str:
        return f"ws://{self.ws_host}:{self.ws_port}"

    # ── Agent ─────────────────────────────────────────────────────────

    @property
    def agent_port_start(self) -> int:
        return int(os.getenv("CREWCRAFT_AGENT_PORT_START", "9001"))

    @property
    def agent_idle_timeout(self) -> int:
        return int(os.getenv("CREWCRAFT_AGENT_IDLE_TIMEOUT", "300"))

    @property
    def agent_heartbeat_interval(self) -> int:
        return int(os.getenv("CREWCRAFT_AGENT_HEARTBEAT_INTERVAL", "15"))

    # ── Logging ───────────────────────────────────────────────────────

    @property
    def log_level(self) -> str:
        return os.getenv("CREWCRAFT_LOG_LEVEL", "INFO")


# Singleton
config = Config()
