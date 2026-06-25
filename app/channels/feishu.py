"""飞书 Channel — WebSocket 长连接（lark-oapi SDK）。

基于 nanobot/channels/feishu.py 实现。
"""

import asyncio
import logging
from typing import Any

from .base import BaseChannel
from .bus import OutboundMsg
from . import register_channel_type

logger = logging.getLogger(__name__)

FEISHU_AVAILABLE = False
try:
    import lark_oapi  # noqa: F401
    FEISHU_AVAILABLE = True
except ImportError:
    pass


class FeishuChannel(BaseChannel):
    """飞书 Channel。通过 WebSocket 长连接收发消息。"""

    name = "feishu"
    display_name = "Feishu"

    def __init__(self, config: dict):
        super().__init__(config)
        self._ws_client: Any = None

    async def start(self):
        if not FEISHU_AVAILABLE:
            logger.error("飞书 SDK 未安装。运行: pip install lark-oapi")
            return

        app_id = self.config.get("app_id", "")
        app_secret = self.config.get("app_secret", "")
        if not app_id or not app_secret:
            logger.error("飞书 Channel 缺少 app_id/app_secret")
            return

        self._running = True
        logger.info(f"飞书 Channel 已启动 (name={self.config.get('name', 'default')})")

        # TODO: 实现 lark-oapi WebSocket 集成
        # domain = FEISHU_DOMAIN
        # client = lark.Client.builder().app_id(app_id).app_secret(app_secret).domain(domain).build()
        # self._ws_client = lark.ws.Client(app_id, app_secret, domain=domain, ...)
        while self._running:
            await asyncio.sleep(5)

    async def stop(self):
        self._running = False

    async def send(self, msg: OutboundMsg):
        """发送消息到飞书。"""
        logger.info(f"飞书发送: {msg.content[:100]}")
        # TODO: 调用飞书 API 发送消息


register_channel_type("feishu", FeishuChannel)
