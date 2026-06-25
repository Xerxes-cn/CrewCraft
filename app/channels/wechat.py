"""微信 Channel — HTTP 长轮询 ilinkai.weixin.qq.com。

基于 nanobot/channels/weixin.py 的协议逆向实现。
扫码登录，token 持久化到 data/channels/wechat/{name}/ 目录。
"""

import asyncio
import json
import logging

from .base import BaseChannel
from .bus import OutboundMsg
from . import register_channel_type

logger = logging.getLogger(__name__)


class WeChatChannel(BaseChannel):
    """微信个人号 Channel。通过 HTTP 长轮询收发消息。"""

    name = "wechat"
    display_name = "WeChat"

    def __init__(self, config: dict):
        super().__init__(config)
        self._token = config.get("token", "")
        self._poll_task: asyncio.Task | None = None

    async def start(self):
        self._running = True
        if not self._token:
            logger.warning("微信 Channel 未配置 token，跳过启动。请先通过扫码获取 token。")
            return
        logger.info(f"微信 Channel 已启动 (name={self.config.get('name', 'default')})")
        # TODO: 实现 HTTP 长轮询循环
        while self._running:
            await asyncio.sleep(5)

    async def stop(self):
        self._running = False
        if self._poll_task:
            self._poll_task.cancel()

    async def send(self, msg: OutboundMsg):
        """发送消息到微信。"""
        logger.info(f"微信发送: {msg.content[:100]}")
        # TODO: 调用 ilinkai API 发送消息


register_channel_type("wechat", WeChatChannel)
