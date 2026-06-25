"""钉钉 Channel — WebSocket 长连接（dingtalk-stream SDK）。

基于 nanobot/channels/dingtalk.py 实现。
"""

import asyncio
import logging
from typing import Any

from .base import BaseChannel
from .bus import OutboundMsg
from . import register_channel_type

logger = logging.getLogger(__name__)

DINGTALK_AVAILABLE = False
try:
    from dingtalk_stream import Credential, DingTalkStreamClient, ChatbotMessage, CallbackHandler, AckMessage, CallbackMessage  # noqa: F401
    DINGTALK_AVAILABLE = True
except ImportError:
    pass


class DingTalkChannel(BaseChannel):
    """钉钉 Channel。通过 WebSocket 长连接收发消息。"""

    name = "dingtalk"
    display_name = "DingTalk"

    def __init__(self, config: dict):
        super().__init__(config)
        self._client: Any = None

    async def start(self):
        if not DINGTALK_AVAILABLE:
            logger.error("钉钉 SDK 未安装。运行: pip install dingtalk-stream")
            return

        client_id = self.config.get("client_id", "")
        client_secret = self.config.get("client_secret", "")
        if not client_id or not client_secret:
            logger.error("钉钉 Channel 缺少 client_id/client_secret")
            return

        self._running = True
        logger.info(f"钉钉 Channel 已启动 (name={self.config.get('name', 'default')})")

        # TODO: 实现 dingtalk-stream SDK 集成
        # credential = Credential(client_id, client_secret)
        # self._client = DingTalkStreamClient(credential)
        # handler = NanobotDingTalkHandler(self)
        # self._client.register_callback_handler(ChatbotMessage.TOPIC, handler)
        while self._running:
            await asyncio.sleep(5)

    async def stop(self):
        self._running = False

    async def send(self, msg: OutboundMsg):
        """发送消息到钉钉。"""
        logger.info(f"钉钉发送: {msg.content[:100]}")
        # TODO: 调用钉钉 API 发送消息


register_channel_type("dingtalk", DingTalkChannel)
