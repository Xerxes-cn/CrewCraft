"""消息总线 — 解耦 Channel 和 Agent，统一管理多平台消息路由。"""

import asyncio
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class InboundMsg:
    """从 Channel 进入系统的消息。"""
    channel: str          # cli / wechat / dingtalk / feishu
    sender_id: str
    chat_id: str
    content: str
    media: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class OutboundMsg:
    """系统发回 Channel 的消息。"""
    channel: str
    chat_id: str
    content: str = ""
    media: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class MsgManager:
    """统一管理所有 Channel 的入站/出站消息。

    Channel 通过 publish_inbound() 推送消息，通过 consume_outbound() 获取回复。
    Orchestrator 处理后通过 publish_outbound() 推送回复。
    """

    def __init__(self):
        self._inbound: asyncio.Queue[InboundMsg] = asyncio.Queue()
        self._outbound: asyncio.Queue[OutboundMsg] = asyncio.Queue()
        self._handlers: dict[str, asyncio.Queue[OutboundMsg]] = {}

    async def publish_inbound(self, msg: InboundMsg):
        """Channel → 总线。"""
        await self._inbound.put(msg)

    async def consume_inbound(self) -> InboundMsg:
        """Orchestrator 消费入站消息。"""
        return await self._inbound.get()

    async def publish_outbound(self, msg: OutboundMsg):
        """Orchestrator → 总线 → Channel。"""
        # 直接推给对应 Channel 的队列
        if msg.channel in self._handlers:
            await self._handlers[msg.channel].put(msg)
        # 也放到全局队列作为备份
        await self._outbound.put(msg)

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
