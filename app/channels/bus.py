"""消息总线 — 解耦 Channel 和 Agent，统一管理多平台消息路由。

收发时自动 format/validate 消息。
"""

import asyncio
import logging

from app.models import InboundMsg, OutboundMsg

logger = logging.getLogger(__name__)


class MsgManager:
    """统一管理所有 Channel 的入站/出站消息。"""

    def __init__(self):
        self._inbound: asyncio.Queue[InboundMsg] = asyncio.Queue()
        self._handlers: dict[str, asyncio.Queue[OutboundMsg]] = {}

    async def publish_inbound(self, msg: InboundMsg):
        """Channel → 总线。自动 format。"""
        msg.format()
        logger.debug(f"入站: [{msg.channel}] {msg.content[:80]}")
        await self._inbound.put(msg)

    async def consume_inbound(self) -> InboundMsg:
        """Orchestrator 消费入站消息。"""
        return await self._inbound.get()

    async def publish_outbound(self, msg: OutboundMsg):
        """Orchestrator → 总线 → Channel。自动 format。"""
        msg.format()
        logger.debug(f"出站: [{msg.channel}] {msg.content[:80]}")
        if msg.channel not in self._handlers:
            self.register_channel(msg.channel)
        await self._handlers[msg.channel].put(msg)

    def register_channel(self, name: str):
        """为 Channel 注册专属出站队列。"""
        if name not in self._handlers:
            self._handlers[name] = asyncio.Queue()

    async def consume_outbound(self, channel_name: str) -> OutboundMsg:
        """Channel 消费属于自己的出站消息。"""
        if channel_name not in self._handlers:
            self.register_channel(channel_name)
        return await self._handlers[channel_name].get()


# 单例
msg_manager = MsgManager()
