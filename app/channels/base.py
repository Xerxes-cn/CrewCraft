"""BaseChannel — 所有 IM 平台的抽象基类。"""

from abc import ABC, abstractmethod
from typing import Any

from app.models import InboundMsg, OutboundMsg
from .bus import msg_manager


class BaseChannel(ABC):
    """Channel 抽象基类。每个 IM 平台实现此接口即可接入 CrewCraft。"""

    name: str = "base"
    display_name: str = "Base"

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self._running = False

    @abstractmethod
    async def start(self) -> None:
        """启动 Channel，连接 IM 平台，开始监听消息。"""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """停止 Channel，断开连接。"""
        ...

    @abstractmethod
    async def send(self, msg: OutboundMsg) -> None:
        """发送消息到 IM 平台。"""
        ...

    @property
    def is_running(self) -> bool:
        return self._running

    async def _on_message(self, content: str, sender_id: str, chat_id: str,
                          media: list[str] | None = None, **kwargs):
        """子类调用此方法将收到的消息推入总线。"""
        inbound = InboundMsg(
            channel=f"{self.name}-{self.config.get('name', 'default')}",
            sender_id=sender_id,
            chat_id=chat_id,
            content=content,
            media=media or [],
            metadata=kwargs,
        ).format()
        await msg_manager.publish_inbound(inbound)
