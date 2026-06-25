"""MsgManager 测试。"""

import asyncio
import pytest
from app.channels.bus import MsgManager, InboundMsg, OutboundMsg


@pytest.mark.asyncio
async def test_publish_and_consume_inbound():
    """测试入站消息的发布和消费。"""
    mgr = MsgManager()
    msg = InboundMsg(channel="cli", sender_id="u1", chat_id="c1", content="hello")
    await mgr.publish_inbound(msg)

    received = await mgr.consume_inbound()
    assert received.channel == "cli"
    assert received.content == "hello"


@pytest.mark.asyncio
async def test_channel_routing():
    """测试 Channel 路由。"""
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
async def test_inbound_msg_dataclass():
    """测试 InboundMsg 数据类。"""
    msg = InboundMsg(
        channel="feishu", sender_id="ou_123", chat_id="oc_456",
        content="hello", media=["/tmp/img.jpg"],
        metadata={"msg_type": "text"}
    )
    assert msg.channel == "feishu"
    assert msg.media == ["/tmp/img.jpg"]
    assert msg.metadata["msg_type"] == "text"
