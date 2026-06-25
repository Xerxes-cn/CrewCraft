"""钉钉 Channel — WebSocket 长连接（dingtalk-stream SDK）。"""

import asyncio
import json
import logging
import time
from typing import Any

import httpx

from app.models import InboundMsg, OutboundMsg
from .base import BaseChannel
from .bus import msg_manager
from . import register_channel_type

logger = logging.getLogger(__name__)

DINGTALK_AVAILABLE = False
try:
    from dingtalk_stream import (  # noqa: F401
        AckMessage, CallbackHandler, CallbackMessage,
        ChatbotMessage, Credential, DingTalkStreamClient,
    )
    DINGTALK_AVAILABLE = True
except ImportError:
    CallbackHandler = object  # type: ignore
    CallbackMessage = object  # type: ignore
    ChatbotMessage = object  # type: ignore
    AckMessage = None


if DINGTALK_AVAILABLE:

    class _DingTalkHandler(CallbackHandler):
        """钉钉 Stream SDK 回调处理器。"""

        def __init__(self, channel: "DingTalkChannel"):
            super().__init__()
            self.ch = channel

        async def process(self, message: CallbackMessage):
            try:
                chatbot_msg = ChatbotMessage.from_dict(message.data)
                content = ""
                if chatbot_msg.text:
                    content = chatbot_msg.text.content.strip()
                if not content:
                    return AckMessage.STATUS_OK, "OK"

                chat_type = message.data.get("conversationType", "1")
                conv_id = message.data.get("conversationId", "")
                sender_id = chatbot_msg.sender_staff_id or chatbot_msg.sender_id
                chat_id = f"group:{conv_id}" if chat_type == "2" else sender_id

                inbound = InboundMsg(
                    channel=self.ch._channel_name,
                    sender_id=sender_id, chat_id=chat_id, content=content,
                ).format()
                await msg_manager.publish_inbound(inbound)
                return AckMessage.STATUS_OK, "OK"
            except Exception:
                logger.exception("钉钉消息处理异常")
                return AckMessage.STATUS_OK, "Error"


class DingTalkChannel(BaseChannel):
    """钉钉 Channel。通过 WebSocket 长连接收发消息。"""

    name = "dingtalk"
    display_name = "DingTalk"

    def __init__(self, config: dict):
        super().__init__(config)
        self._client: Any = None
        self._http: httpx.AsyncClient | None = None
        self._token: str | None = None
        self._token_expiry: float = 0

    @property
    def _channel_name(self) -> str:
        return f"dingtalk-{self.config.get('name', 'default')}"

    async def _get_token(self) -> str | None:
        if self._token and time.time() < self._token_expiry:
            return self._token
        if not self._http:
            self._http = httpx.AsyncClient()
        client_id = self.config.get("client_id", "")
        secret = self.config.get("client_secret", "")
        resp = await self._http.post(
            "https://api.dingtalk.com/v1.0/oauth2/accessToken",
            json={"appKey": client_id, "appSecret": secret},
        )
        data = resp.json()
        self._token = data.get("accessToken")
        self._token_expiry = time.time() + data.get("expireIn", 7200) - 60
        return self._token

    async def start(self):
        if not DINGTALK_AVAILABLE:
            logger.error("钉钉 SDK 未安装。pip install dingtalk-stream")
            return
        client_id = self.config.get("client_id", "")
        secret = self.config.get("client_secret", "")
        if not client_id or not secret:
            logger.error("钉钉缺少 client_id/client_secret")
            return

        self._running = True
        logger.info(f"钉钉 Channel 已启动 ({self.config.get('name', 'default')})")

        credential = Credential(client_id, secret)
        self._client = DingTalkStreamClient(credential)
        self._client.register_callback_handler(
            ChatbotMessage.TOPIC, _DingTalkHandler(self))

        msg_manager.register_channel(self._channel_name)
        while self._running:
            try:
                await self._client.start()
            except Exception as e:
                logger.warning(f"钉钉 Stream 异常: {e}")
            if self._running:
                await asyncio.sleep(5)

    async def stop(self):
        self._running = False
        if self._http:
            await self._http.aclose()

    async def send(self, msg: OutboundMsg):
        token = await self._get_token()
        if not token or not self._http:
            return

        is_group = msg.chat_id.startswith("group:")
        if is_group:
            url = "https://api.dingtalk.com/v1.0/robot/groupMessages/send"
            payload = {
                "robotCode": self.config.get("client_id"),
                "openConversationId": msg.chat_id[6:],
                "msgKey": "sampleMarkdown",
                "msgParam": json.dumps({"text": msg.content, "title": "CrewCraft"}),
            }
        else:
            url = "https://api.dingtalk.com/v1.0/robot/oToMessages/batchSend"
            payload = {
                "robotCode": self.config.get("client_id"),
                "userIds": [msg.chat_id],
                "msgKey": "sampleMarkdown",
                "msgParam": json.dumps({"text": msg.content, "title": "CrewCraft"}),
            }
        await self._http.post(url, json=payload, headers={
            "x-acs-dingtalk-access-token": token,
        })


register_channel_type("dingtalk", DingTalkChannel)
