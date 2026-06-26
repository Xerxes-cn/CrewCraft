"""微信 Channel — HTTP 长轮询 ilinkai.weixin.qq.com。

基于 nanobot/channels/weixin.py 的协议逆向实现。
扫码登录获取 token，持久化到 data/channels/wechat/{name}/ 目录。
"""

import asyncio
import json
import logging
from pathlib import Path

import httpx

from app.models import InboundMsg, OutboundMsg
from .base import BaseChannel
from .bus import msg_manager
from . import register_channel_type

logger = logging.getLogger(__name__)

ILINK_BASE = "https://ilinkai.weixin.qq.com"
POLL_TIMEOUT = 35       # 运行时从 config.wechat_poll_timeout 读取
MAX_MESSAGE_LEN = 4000   # 运行时从 config.wechat_max_message_len 读取


class WeChatChannel(BaseChannel):
    """微信个人号 Channel。通过 HTTP 长轮询收发消息。"""

    name = "wechat"
    display_name = "WeChat"

    def __init__(self, config: dict):
        super().__init__(config)
        self._token = config.get("token", "")
        self._base_url = config.get("base_url", ILINK_BASE)
        self._buf = ""
        self._client: httpx.AsyncClient | None = None

    @property
    def _state_dir(self) -> Path:
        d = Path("data/channels/wechat") / self.config.get("name", "default")
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _load_token(self) -> str:
        f = self._state_dir / "token.json"
        if f.exists():
            return json.loads(f.read_text()).get("token", "")
        return ""

    def _save_token(self, token: str):
        self._state_dir.mkdir(parents=True, exist_ok=True)
        (self._state_dir / "token.json").write_text(
            json.dumps({"token": token}))

    async def start(self):
        self._running = True
        self._token = self._token or self._load_token()
        if not self._token:
            logger.warning("微信 Channel 未配置 token，跳过启动")
            return

        self._client = httpx.AsyncClient(timeout=60)
        logger.info(f"微信 Channel 已启动 ({self.config.get('name', 'default')})")

        while self._running:
            try:
                body = {"get_updates_buf": self._buf, "base_info": {}}
                resp = await self._client.post(
                    f"{self._base_url}/ilink/bot/getupdates", json=body,
                    headers={"Authorization": f"Bearer {self._token}"},
                    timeout=POLL_TIMEOUT + 10,
                )
                data = resp.json()

                if data.get("ret", 0) != 0:
                    await asyncio.sleep(5)
                    continue

                self._buf = data.get("get_updates_buf", self._buf)
                for msg in data.get("msgs", []):
                    await self._process_message(msg)
            except httpx.TimeoutException:
                continue
            except Exception:
                logger.exception("微信轮询异常")
                await asyncio.sleep(5)

    async def _process_message(self, msg: dict):
        """处理一条微信消息。"""
        sender = msg.get("from_user_id", "")
        items = msg.get("item_list", [])
        parts = []
        for item in items:
            if item.get("type") == 1:  # text
                parts.append((item.get("text_item") or {}).get("text", ""))
        content = "\n".join(p for p in parts if p)
        if not content:
            return

        inbound = InboundMsg(
            channel=f"wechat-{self.config.get('name', 'default')}",
            sender_id=sender, chat_id=sender,
            content=content,
        ).format()
        await msg_manager.publish_inbound(inbound)

    async def stop(self):
        self._running = False
        if self._client:
            await self._client.aclose()

    async def send(self, msg: OutboundMsg):
        """发送消息到微信。"""
        if not self._client or not self._token:
            return
        chunks = [msg.content[i:i+MAX_MESSAGE_LEN]
                  for i in range(0, len(msg.content), MAX_MESSAGE_LEN)]
        for chunk in chunks:
            body = {
                "msg": {
                    "to_user_id": msg.chat_id, "from_user_id": "",
                    "item_list": [{"type": 1, "text_item": {"text": chunk}}],
                    "message_type": 2, "message_state": 2,
                },
                "base_info": {},
            }
            await self._client.post(
                f"{self._base_url}/ilink/bot/sendmessage", json=body,
                headers={"Authorization": f"Bearer {self._token}"},
            )


register_channel_type("wechat", WeChatChannel)
