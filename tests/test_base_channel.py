"""BaseChannel 抽象基类测试。

使用最小化具体实现测试 _on_message、is_running 等共享行为。
不依赖真实 IM 平台。
"""

import asyncio
import pytest

from app.channels.base import BaseChannel
from app.channels.bus import MsgManager, msg_manager as global_mgr
from app.models import InboundMsg, OutboundMsg


# ── 最小化具体实现 ──────────────────────────────────────────────────────


class MockChannel(BaseChannel):
    """用于测试的最小 Channel 实现。"""

    name = "mock"
    display_name = "Mock"

    async def start(self):
        self._running = True

    async def stop(self):
        self._running = False

    async def send(self, msg: OutboundMsg):
        pass  # 测试用不做任何事


# ── 基本属性 ───────────────────────────────────────────────────────────


class TestBaseChannelProperties:

    def test_is_running_defaults_false(self):
        ch = MockChannel({"name": "test"})
        assert ch.is_running is False

    def test_is_running_after_start(self):
        ch = MockChannel({"name": "test"})
        asyncio.run(ch.start())
        assert ch.is_running is True

    def test_is_running_after_stop(self):
        ch = MockChannel({"name": "test"})
        asyncio.run(ch.start())
        asyncio.run(ch.stop())
        assert ch.is_running is False

    def test_config_stored(self):
        cfg = {"name": "mock-1", "token": "secret"}
        ch = MockChannel(cfg)
        assert ch.config == cfg
        assert ch.config["name"] == "mock-1"


# ── _on_message 集成测试 ────────────────────────────────────────────────


class TestOnMessage:

    @pytest.fixture
    def ch(self):
        return MockChannel({"name": "test"})

    @pytest.mark.asyncio
    async def test_on_message_publishes_to_bus(self, ch):
        """_on_message 创建 InboundMsg 并发布到总线。"""
        await ch._on_message("hello", sender_id="u1", chat_id="c1")

        # 从全局总线消费
        msg = await global_mgr.consume_inbound()
        assert isinstance(msg, InboundMsg)
        assert msg.content == "hello"
        assert msg.sender_id == "u1"
        assert msg.chat_id == "c1"
        assert msg.channel == "mock-test"  # {name}-{config.name}

    @pytest.mark.asyncio
    async def test_on_message_formats_before_publish(self, ch):
        """_on_message 发布的 InboundMsg 已经过 format()。"""
        await ch._on_message("  hello world  ", sender_id="U1", chat_id="C1")
        msg = await global_mgr.consume_inbound()
        assert msg.content == "hello world"  # stripped
        assert msg.sender_id == "U1"  # stripped
        assert msg.channel == "mock-test"

    @pytest.mark.asyncio
    async def test_on_message_includes_media(self, ch):
        await ch._on_message("photo", sender_id="u", chat_id="c",
                            media=["/tmp/photo.jpg"])
        msg = await global_mgr.consume_inbound()
        assert msg.media == ["/tmp/photo.jpg"]

    @pytest.mark.asyncio
    async def test_on_message_includes_extra_metadata(self, ch):
        await ch._on_message("hi", sender_id="u", chat_id="c",
                            extra_key="extra_value", foo="bar")
        msg = await global_mgr.consume_inbound()
        assert msg.metadata["extra_key"] == "extra_value"
        assert msg.metadata["foo"] == "bar"

    @pytest.mark.asyncio
    async def test_on_message_with_different_config_name(self):
        ch = MockChannel({"name": "production"})
        await ch._on_message("x", sender_id="u", chat_id="c")
        msg = await global_mgr.consume_inbound()
        assert msg.channel == "mock-production"  # uses config name
