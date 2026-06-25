"""飞书 Channel — WebSocket 长连接（lark-oapi SDK）。"""

import asyncio
import json
import logging
import os
import threading
from typing import Any

from app.models import InboundMsg, OutboundMsg
from .base import BaseChannel
from .bus import msg_manager
from . import register_channel_type

logger = logging.getLogger(__name__)

FEISHU_AVAILABLE = False
try:
    import lark_oapi as lark  # noqa: F401
    FEISHU_AVAILABLE = True
except ImportError:
    pass


class FeishuChannel(BaseChannel):
    """飞书 Channel。通过 WebSocket 长连接收发消息。"""

    name = "feishu"
    display_name = "Feishu"

    def __init__(self, config: dict):
        super().__init__(config)
        self._client: Any = None
        self._ws_thread: threading.Thread | None = None

    @property
    def _channel_name(self) -> str:
        return f"feishu-{self.config.get('name', 'default')}"

    def _on_message(self, data: Any):
        """同步回调（WebSocket 线程），调度到主事件循环。"""
        asyncio.run_coroutine_threadsafe(self._handle(data), asyncio.get_running_loop())

    async def _handle(self, data: Any):
        try:
            event = data.event
            msg = event.message
            sender = event.sender

            if sender.sender_type == "bot":
                return

            sender_id = sender.sender_id.open_id if sender.sender_id else "unknown"
            chat_id = msg.chat_id
            chat_type = msg.chat_type
            content = ""

            try:
                body = json.loads(msg.content) if msg.content else {}
            except json.JSONDecodeError:
                body = {}

            if msg.message_type == "text":
                content = body.get("text", "")
            elif msg.message_type == "post":
                post = body.get("post", {})
                zh = post.get("zh_cn", {}) if isinstance(post, dict) else {}
                for row in zh.get("content", []):
                    for el in row:
                        if el.get("tag") == "text":
                            content += el.get("text", "")
            else:
                content = f"[{msg.message_type}]"

            if chat_type == "group":
                mentions = getattr(msg, "mentions", None) or []
                bot_mentioned = any(
                    getattr(m.id, "open_id", "") == getattr(self, "_bot_open_id", "")
                    for m in mentions
                )
                if not bot_mentioned and "@_all" not in (msg.content or ""):
                    return

            inbound = InboundMsg(
                channel=self._channel_name,
                sender_id=sender_id, chat_id=chat_id, content=content,
            ).format()
            await msg_manager.publish_inbound(inbound)

        except Exception:
            logger.exception("飞书消息处理异常")

    async def start(self):
        if not FEISHU_AVAILABLE:
            logger.error("飞书 SDK 未安装。pip install lark-oapi")
            return
        app_id = self.config.get("app_id", "")
        secret = self.config.get("app_secret", "")
        if not app_id or not secret:
            logger.error("飞书缺少 app_id/app_secret")
            return

        self._running = True
        domain = lark.FEISHU_DOMAIN

        self._client = (
            lark.Client.builder()
            .app_id(app_id).app_secret(secret).domain(domain)
            .log_level(lark.LogLevel.INFO).build()
        )

        handler = lark.EventDispatcherHandler.builder("", "").register_p2_im_message_receive_v1(
            self._on_message
        ).build()

        def run_ws():
            ws_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(ws_loop)
            ws_client = lark.ws.Client(app_id, secret, domain=domain, event_handler=handler, log_level=lark.LogLevel.INFO)
            try:
                while self._running:
                    try:
                        ws_client.start()
                    except Exception as e:
                        logger.warning(f"飞书 WS 异常: {e}")
                    if self._running:
                        import time
                        time.sleep(5)
            finally:
                ws_loop.close()

        self._ws_thread = threading.Thread(target=run_ws, daemon=True)
        self._ws_thread.start()

        msg_manager.register_channel(self._channel_name)
        logger.info(f"飞书 Channel 已启动 ({self.config.get('name', 'default')})")

        while self._running:
            await asyncio.sleep(1)

    async def stop(self):
        self._running = False

    async def send(self, msg: OutboundMsg):
        if not self._client:
            return
        rid_type = "chat_id" if msg.chat_id.startswith("oc_") else "open_id"
        content = msg.content.strip()
        if not content:
            return

        loop = asyncio.get_running_loop()
        if len(content) <= 200:
            text_body = json.dumps({"text": content}, ensure_ascii=False)
            await loop.run_in_executor(
                None,
                lambda: self._client.im.v1.message.create(
                    lark.api.im.v1.CreateMessageRequest.builder()
                    .receive_id_type(rid_type)
                    .request_body(
                        lark.api.im.v1.CreateMessageRequestBody.builder()
                        .receive_id(msg.chat_id).msg_type("text").content(text_body).build()
                    ).build()
                )
            )
        else:
            card = json.dumps({
                "config": {"wide_screen_mode": True},
                "elements": [
                    {"tag": "markdown", "content": content[:5000]}
                ],
            }, ensure_ascii=False)
            await loop.run_in_executor(
                None,
                lambda: self._client.im.v1.message.create(
                    lark.api.im.v1.CreateMessageRequest.builder()
                    .receive_id_type(rid_type)
                    .request_body(
                        lark.api.im.v1.CreateMessageRequestBody.builder()
                        .receive_id(msg.chat_id).msg_type("interactive").content(card).build()
                    ).build()
                )
            )


register_channel_type("feishu", FeishuChannel)
