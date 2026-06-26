"""数据模型测试 — 覆盖 app/models.py 所有 dataclass 的构造、序列化、校验。"""

import json

from app.models import (
    InboundMsg, OutboundMsg, TaskRequest, TaskResult,
    ChannelConfig, ApprovalItem, ApprovalResponse,
    WSMessage, WSRegisterMsg, WSRegisteredMsg, WSTaskMsg,
    WSTaskUpdateMsg, WSApprovalRequest, WSApprovalResponse,
)


# ── InboundMsg ──────────────────────────────────────────────────────────


class TestInboundMsg:

    def test_constructor_defaults(self):
        msg = InboundMsg(channel="c", sender_id="s", chat_id="c", content="x")
        assert msg.media == []
        assert msg.metadata == {}

    def test_format_strips_whitespace(self):
        msg = InboundMsg(channel="  cli  ", sender_id=" u ", chat_id=" c ",
                         content="  hi  ")
        msg.format()
        assert msg.channel == "cli"
        assert msg.sender_id == "u"
        assert msg.chat_id == "c"
        assert msg.content == "hi"

    def test_format_lowercases_channel(self):
        msg = InboundMsg(channel="FEISHU-PROD", sender_id="u", chat_id="c", content="x")
        msg.format()
        assert msg.channel == "feishu-prod"

    def test_format_truncates_content_at_10000(self):
        msg = InboundMsg(channel="c", sender_id="u", chat_id="c", content="a" * 20000)
        msg.format()
        assert len(msg.content) == 10000
        assert msg.content == "a" * 10000

    def test_format_returns_self(self):
        msg = InboundMsg(channel="c", sender_id="u", chat_id="c", content="x")
        assert msg.format() is msg

    def test_format_stringifies_sender_id(self):
        msg = InboundMsg(channel="c", sender_id=42, chat_id="c", content="x")
        msg.format()
        assert msg.sender_id == "42"
        assert isinstance(msg.sender_id, str)

    def test_from_dict_extracts_known_fields(self):
        d = {"channel": "wx", "sender_id": "u1", "chat_id": "c1", "content": "hi",
             "media": ["/tmp/a"], "metadata": {"k": "v"}, "extra": "ignored"}
        msg = InboundMsg.from_dict(d)
        assert msg.channel == "wx"
        assert msg.media == ["/tmp/a"]
        assert msg.metadata == {"k": "v"}

    def test_from_dict_preserves_media_and_metadata_defaults(self):
        msg = InboundMsg.from_dict({"channel": "c", "sender_id": "u", "chat_id": "c", "content": "hi"})
        assert msg.media == []
        assert msg.metadata == {}


# ── OutboundMsg ─────────────────────────────────────────────────────────


class TestOutboundMsg:

    def test_constructor_defaults(self):
        msg = OutboundMsg(channel="c", chat_id="c")
        assert msg.content == ""
        assert msg.media == []
        assert msg.metadata == {}

    def test_format_strips_channel_and_content(self):
        msg = OutboundMsg(channel="  CLI  ", chat_id="c1", content="  hi  ")
        msg.format()
        assert msg.channel == "cli"
        assert msg.content == "hi"

    def test_format_does_not_lowercase_chat_id(self):
        """chat_id 保留原始大小写。"""
        msg = OutboundMsg(channel="c", chat_id="Chat-ABC-123", content="x")
        msg.format()
        assert msg.chat_id == "Chat-ABC-123"

    def test_format_truncates_content_at_8000(self):
        msg = OutboundMsg(channel="c", chat_id="c", content="b" * 16000)
        msg.format()
        assert len(msg.content) == 8000

    def test_format_returns_self(self):
        msg = OutboundMsg(channel="c", chat_id="c")
        assert msg.format() is msg


# ── TaskRequest ─────────────────────────────────────────────────────────


class TestTaskRequest:

    def test_constructor_with_agent_and_channel(self):
        req = TaskRequest(content="do stuff", agent_name="dev", channel="cli", chat_id="c1")
        assert req.content == "do stuff"
        assert req.agent_name == "dev"

    def test_format_strips_and_truncates(self):
        req = TaskRequest(content="  x" + "y"*20000 + "  ", agent_name=" Dev ")
        req.format()
        assert req.content.startswith("xy")
        assert len(req.content) == 10000
        assert req.agent_name == "Dev"

    def test_constructor_defaults(self):
        req = TaskRequest(content="x")
        assert req.agent_name == ""
        assert req.channel == ""
        assert req.chat_id == ""


# ── TaskResult ──────────────────────────────────────────────────────────


class TestTaskResult:

    def test_constructor_defaults(self):
        r = TaskResult(task_id="t1")
        assert r.session_id == ""
        assert r.agent_name == ""
        assert r.status == "pending"
        assert r.result == ""
        assert r.error == ""
        assert r.plan == []

    def test_full_fields(self):
        r = TaskResult(
            task_id="t1", session_id="s1", agent_name="dev",
            status="completed", result="OK", error="",
            plan=[{"agent": "a", "task": "t"}],
        )
        assert r.status == "completed"
        assert len(r.plan) == 1


# ── ChannelConfig ───────────────────────────────────────────────────────


class TestChannelConfig:

    def test_from_dict_full(self):
        cfg = ChannelConfig.from_dict({
            "type": "wechat", "name": "bot1", "enabled": True,
            "token": "abc", "app_id": "123",
        })
        assert cfg.type == "wechat"
        assert cfg.name == "bot1"
        assert cfg.enabled is True
        assert cfg.config == {"token": "abc", "app_id": "123"}

    def test_from_dict_empty(self):
        cfg = ChannelConfig.from_dict({})
        assert cfg.type == ""
        assert cfg.name == ""
        assert cfg.enabled is True
        assert cfg.config == {}

    def test_from_dict_reserved_keys_excluded_from_config(self):
        """type/name/enabled 不进入 config。"""
        cfg = ChannelConfig.from_dict({"type": "dingtalk", "name": "d1", "enabled": False})
        assert "type" not in cfg.config
        assert "name" not in cfg.config
        assert "enabled" not in cfg.config

    def test_from_dict_disabled(self):
        cfg = ChannelConfig.from_dict({"type": "wechat", "enabled": False})
        assert cfg.enabled is False

    def test_from_dict_name_fallback_to_type(self):
        cfg = ChannelConfig.from_dict({"type": "feishu"})
        assert cfg.name == "feishu"


# ── ApprovalItem ────────────────────────────────────────────────────────


class TestApprovalItem:

    def test_defaults(self):
        item = ApprovalItem()
        assert item.request_id == ""
        assert item.permission == "safe"

    def test_to_dict_contains_all_keys(self):
        item = ApprovalItem(
            request_id="r1", agent="a", session_id="s", tool="t",
            action="x", permission="dangerous", timestamp="2025",
        )
        d = item.to_dict()
        assert d["request_id"] == "r1"
        assert d["permission"] == "dangerous"
        assert d["timestamp"] == "2025"

    def test_to_dict_roundtrip(self):
        item = ApprovalItem(request_id="r1", agent="a", permission="write")
        d = item.to_dict()
        assert isinstance(d, dict)
        assert d["request_id"] == "r1"


# ── ApprovalResponse ────────────────────────────────────────────────────


class TestApprovalResponseModel:

    def test_minimal_construction(self):
        r = ApprovalResponse(request_id="r1", decision="approved")
        assert r.request_id == "r1"
        assert r.decision == "approved"
        assert r.session_id == ""


# ── WSMessage 基类与子类 ────────────────────────────────────────────────


class TestWSMessage:

    def test_default_type_empty(self):
        msg = WSMessage()
        assert msg.type == ""

    def test_to_json_produces_valid_json(self):
        msg = WSMessage(type="ping")
        j = msg.to_json()
        data = json.loads(j)
        assert data["type"] == "ping"


class TestWSRegisterMsg:

    def test_default_type(self):
        msg = WSRegisterMsg()
        assert msg.type == "register"

    def test_to_json(self):
        msg = WSRegisterMsg(name="agent-1")
        data = json.loads(msg.to_json())
        assert data["type"] == "register"
        assert data["name"] == "agent-1"


class TestWSRegisteredMsg:

    def test_to_json_includes_config(self):
        msg = WSRegisteredMsg(name="a", config={"model": "gpt"})
        data = json.loads(msg.to_json())
        assert data["config"] == {"model": "gpt"}


class TestWSTaskMsg:

    def test_defaults(self):
        msg = WSTaskMsg(task_id="t1", session_id="s1", content="do stuff")
        data = json.loads(msg.to_json())
        assert data["type"] == "task"
        assert data["task_id"] == "t1"
        assert data["content"] == "do stuff"


class TestWSTaskUpdateMsg:

    def test_to_json(self):
        msg = WSTaskUpdateMsg(
            task_id="t1", session_id="s1",
            status="completed", result="ok", error="", progress="100%",
        )
        data = json.loads(msg.to_json())
        assert data["status"] == "completed"
        assert data["result"] == "ok"
        assert data["progress"] == "100%"

    def test_default_status(self):
        msg = WSTaskUpdateMsg()
        assert msg.status == "running"


class TestWSApprovalRequest:

    def test_to_json(self):
        msg = WSApprovalRequest(
            request_id="r1", agent="a", session_id="s", tool="t",
            action="rm", permission="dangerous", timestamp="2025",
        )
        data = json.loads(msg.to_json())
        assert data["permission"] == "dangerous"
        assert data["timestamp"] == "2025"


class TestWSApprovalResponse:

    def test_to_json(self):
        msg = WSApprovalResponse(request_id="r1", decision="approved", session_id="s")
        data = json.loads(msg.to_json())
        assert data["type"] == "approval_response"
        assert data["decision"] == "approved"


# ── JSON 序列化往返一致性 ───────────────────────────────────────────────


class TestJSONRoundtrip:

    def test_all_ws_subclasses_produce_valid_json(self):
        """所有 WS 消息子类都能正确序列化为合法 JSON。"""
        messages = [
            WSRegisterMsg(name="agent-1"),
            WSRegisteredMsg(name="agent-1", config={"model": "gpt"}),
            WSTaskMsg(task_id="t1", session_id="s1", content="hello"),
            WSTaskUpdateMsg(task_id="t1", session_id="s1", status="done",
                            result="ok", progress="done"),
            WSApprovalRequest(request_id="r1", agent="a", session_id="s",
                              tool="t", action="x", permission="write", timestamp="t"),
            WSApprovalResponse(request_id="r1", decision="approved", session_id="s"),
        ]
        for msg in messages:
            j = msg.to_json()
            data = json.loads(j)
            assert "type" in data
            assert isinstance(data["type"], str)
            assert data["type"] != ""
