"""MsgManager 消息总线测试 — 覆盖发布/消费/路由/format 行为。"""

import pytest

from app.channels.bus import MsgManager
from app.models import InboundMsg, OutboundMsg, ChannelConfig


# ── InboundMsg 模型测试 ──────────────────────────────────────────────────


class TestInboundMsgModel:

    def test_defaults(self):
        msg = InboundMsg(channel="cli", sender_id="u1", chat_id="c1", content="hi")
        assert msg.media == []
        assert msg.metadata == {}

    def test_full_fields(self):
        msg = InboundMsg(
            channel="feishu", sender_id="ou_123", chat_id="oc_456",
            content="hello", media=["/tmp/img.jpg"],
            metadata={"msg_type": "text"},
        )
        assert msg.channel == "feishu"
        assert msg.media == ["/tmp/img.jpg"]
        assert msg.metadata["msg_type"] == "text"

    def test_format_trims_whitespace(self):
        msg = InboundMsg(channel="  CLI  ", sender_id=" u1 ", chat_id=" c1 ",
                         content="  hello  ")
        msg.format()
        assert msg.channel == "cli"
        assert msg.sender_id == "u1"
        assert msg.chat_id == "c1"
        assert msg.content == "hello"

    def test_format_lowercases_channel(self):
        msg = InboundMsg(channel="Feishu-API", sender_id="u", chat_id="c", content="x")
        msg.format()
        assert msg.channel == "feishu-api"

    def test_format_stringifies_sender_and_chat(self):
        msg = InboundMsg(channel="c", sender_id=12345, chat_id=67890, content="x")
        msg.format()
        assert msg.sender_id == "12345"
        assert msg.chat_id == "67890"

    def test_format_truncates_long_content(self):
        long_text = "x" * 20000
        msg = InboundMsg(channel="c", sender_id="u", chat_id="c", content=long_text)
        msg.format()
        assert len(msg.content) == 10000

    def test_from_dict_extracts_known_fields(self):
        d = {"channel": "cli", "sender_id": "u", "chat_id": "c", "content": "hi",
             "media": ["/tmp/x"], "metadata": {"k": "v"}, "extra_field": "ignore_me"}
        msg = InboundMsg.from_dict(d)
        assert msg.channel == "cli"
        assert msg.sender_id == "u"
        assert msg.content == "hi"
        assert msg.media == ["/tmp/x"]
        assert not hasattr(msg, "extra_field")

    def test_from_dict_missing_optional_uses_defaults(self):
        msg = InboundMsg.from_dict({"channel": "c", "sender_id": "u", "chat_id": "c", "content": "hi"})
        assert msg.media == []
        assert msg.metadata == {}


# ── OutboundMsg 模型测试 ─────────────────────────────────────────────────


class TestOutboundMsgModel:

    def test_defaults(self):
        msg = OutboundMsg(channel="cli", chat_id="c1")
        assert msg.content == ""
        assert msg.media == []
        assert msg.metadata == {}

    def test_format_trims_and_lowercases(self):
        msg = OutboundMsg(channel="  CLI  ", chat_id=" C1 ", content="  hello  ")
        msg.format()
        assert msg.channel == "cli"       # lowercased
        assert msg.chat_id == "C1"        # stripped, NOT lowercased (ID 保留原样)
        assert msg.content == "hello"

    def test_format_truncates_long_content(self):
        msg = OutboundMsg(channel="c", chat_id="c", content="y" * 16000)
        msg.format()
        assert len(msg.content) == 8000


# ── ChannelConfig 模型测试 ───────────────────────────────────────────────


class TestChannelConfigModel:

    def test_from_dict_basic(self):
        cfg = ChannelConfig.from_dict({"type": "wechat", "name": "bot1", "enabled": True,
                                       "token": "abc123"})
        assert cfg.type == "wechat"
        assert cfg.name == "bot1"
        assert cfg.enabled is True
        assert cfg.config["token"] == "abc123"

    def test_from_dict_defaults(self):
        cfg = ChannelConfig.from_dict({})
        assert cfg.type == ""
        assert cfg.name == ""
        assert cfg.enabled is True
        assert cfg.config == {}

    def test_from_dict_extra_keys_go_to_config(self):
        cfg = ChannelConfig.from_dict({"type": "dingtalk", "client_id": "id1",
                                       "client_secret": "secret1", "enabled": False})
        assert cfg.config["client_id"] == "id1"
        assert cfg.config["client_secret"] == "secret1"
        assert "type" not in cfg.config
        assert "enabled" not in cfg.config

    def test_from_dict_name_fallback(self):
        cfg = ChannelConfig.from_dict({"type": "feishu"})
        assert cfg.name == "feishu"


# ── MsgManager 基本操作 ──────────────────────────────────────────────────


class TestMsgManagerBasics:

    @pytest.mark.asyncio
    async def test_publish_and_consume_inbound(self):
        mgr = MsgManager()
        msg = InboundMsg(channel="cli", sender_id="u1", chat_id="c1", content="hello")
        await mgr.publish_inbound(msg)

        received = await mgr.consume_inbound()
        assert received.channel == "cli"
        assert received.content == "hello"

    @pytest.mark.asyncio
    async def test_format_called_on_publish_inbound(self):
        """publish_inbound 自动调用 format()。"""
        mgr = MsgManager()
        msg = InboundMsg(channel="  CLI  ", sender_id=" u1 ", chat_id=" c1 ",
                         content="  hello  ")
        await mgr.publish_inbound(msg)
        received = await mgr.consume_inbound()
        assert received.channel == "cli"  # trimmed + lowercased
        assert received.content == "hello"  # trimmed

    @pytest.mark.asyncio
    async def test_format_called_on_publish_outbound(self):
        mgr = MsgManager()
        mgr.register_channel("cli")
        msg = OutboundMsg(channel="  CLI  ", chat_id=" c1 ", content="  hi  ")
        await mgr.publish_outbound(msg)
        received = await mgr.consume_outbound("cli")
        assert received.channel == "cli"
        assert received.content == "hi"


# ── Channel 路由 ─────────────────────────────────────────────────────────


class TestChannelRouting:

    @pytest.mark.asyncio
    async def test_channel_routing_separate_queues(self):
        mgr = MsgManager()
        mgr.register_channel("cli")
        mgr.register_channel("wechat-test")

        await mgr.publish_outbound(OutboundMsg(channel="cli", chat_id="c1", content="reply"))
        await mgr.publish_outbound(OutboundMsg(channel="wechat-test", chat_id="g1", content="hello"))

        msg1 = await mgr.consume_outbound("cli")
        assert msg1.channel == "cli"
        msg2 = await mgr.consume_outbound("wechat-test")
        assert msg2.channel == "wechat-test"

    @pytest.mark.asyncio
    async def test_auto_register_on_publish_outbound(self):
        """publish_outbound 到未注册 channel 自动创建队列。"""
        mgr = MsgManager()
        assert "unknown-ch" not in mgr._handlers
        await mgr.publish_outbound(OutboundMsg(channel="unknown-ch", chat_id="c", content="hi"))
        assert "unknown-ch" in mgr._handlers

    @pytest.mark.asyncio
    async def test_register_channel_idempotent(self):
        """重复注册不替换已有队列。"""
        mgr = MsgManager()
        mgr.register_channel("cli")
        await mgr.publish_outbound(OutboundMsg(channel="cli", chat_id="c", content="first"))

        # 第二次注册不应清空队列
        mgr.register_channel("cli")
        await mgr.publish_outbound(OutboundMsg(channel="cli", chat_id="c", content="second"))

        assert (await mgr.consume_outbound("cli")).content == "first"
        assert (await mgr.consume_outbound("cli")).content == "second"

    @pytest.mark.asyncio
    async def test_fifo_ordering(self):
        """消息按 FIFO 顺序到达。"""
        mgr = MsgManager()
        mgr.register_channel("cli")
        for i in range(5):
            await mgr.publish_outbound(OutboundMsg(channel="cli", chat_id="c", content=f"msg-{i}"))

        for i in range(5):
            msg = await mgr.consume_outbound("cli")
            assert msg.content == f"msg-{i}"

    @pytest.mark.asyncio
    async def test_empty_content_message(self):
        """空内容消息不崩溃。"""
        mgr = MsgManager()
        msg = InboundMsg(channel="cli", sender_id="u", chat_id="c", content="")
        await mgr.publish_inbound(msg)
        received = await mgr.consume_inbound()
        assert received.content == ""


# ── 多消费者（背压）──────────────────────────────────────────────────────


class TestMultipleConsumers:

    @pytest.mark.asyncio
    async def test_inbound_queue_fifo(self):
        """入站队列保持 FIFO。"""
        mgr = MsgManager()
        for i in range(10):
            await mgr.publish_inbound(InboundMsg(
                channel="c", sender_id="u", chat_id="c", content=f"msg-{i}"))
        for i in range(10):
            msg = await mgr.consume_inbound()
            assert msg.content == f"msg-{i}"
