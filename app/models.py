"""统一数据模型 — 所有内部消息传递使用 dataclass/Pydantic。

收发时统一 format/validate。
"""

from dataclasses import dataclass, field, asdict


# ── Channel 消息 ──────────────────────────────────────────────────────

@dataclass
class InboundMsg:
    """从 Channel 进入系统的消息。"""
    channel: str
    sender_id: str
    chat_id: str
    content: str
    media: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def format(self) -> "InboundMsg":
        """裁剪空白、限制长度。"""
        self.content = self.content.strip()[:10000]
        self.channel = self.channel.strip().lower()
        self.sender_id = str(self.sender_id).strip()
        self.chat_id = str(self.chat_id).strip()
        return self

    @classmethod
    def from_dict(cls, d: dict) -> "InboundMsg":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class OutboundMsg:
    """系统发回 Channel 的消息。"""
    channel: str
    chat_id: str
    content: str = ""
    media: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def format(self) -> "OutboundMsg":
        self.content = self.content.strip()[:8000]
        self.channel = self.channel.strip().lower()
        self.chat_id = str(self.chat_id).strip()
        return self


# ── Agent 配置 ────────────────────────────────────────────────────────

@dataclass
class AgentConfig:
    """Agent 配置。"""
    name: str
    model: str
    description: str = ""
    provider: str = ""
    port: int = 0
    idle_timeout: int = 300
    created_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# ── Task ──────────────────────────────────────────────────────────────

@dataclass
class TaskRequest:
    """任务请求。"""
    content: str
    agent_name: str = ""
    channel: str = ""
    chat_id: str = ""

    def format(self) -> "TaskRequest":
        self.content = self.content.strip()[:10000]
        self.agent_name = self.agent_name.strip()
        return self


@dataclass
class TaskResult:
    """任务结果。"""
    task_id: str
    session_id: str = ""
    agent_name: str = ""
    status: str = "pending"
    result: str = ""
    error: str = ""
    plan: list = field(default_factory=list)


# ── Channel 配置 ──────────────────────────────────────────────────────

@dataclass
class ChannelConfig:
    """单个 Channel 的配置。"""
    type: str = ""
    name: str = ""
    enabled: bool = True
    config: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> "ChannelConfig":
        return cls(
            type=d.get("type", ""),
            name=d.get("name", d.get("type", "")),
            enabled=d.get("enabled", True),
            config={k: v for k, v in d.items() if k not in ("type", "name", "enabled")},
        )


# ── Approval ──────────────────────────────────────────────────────────

@dataclass
class ApprovalItem:
    """审批队列中的一项。"""
    request_id: str = ""
    agent: str = ""
    session_id: str = ""
    tool: str = ""
    action: str = ""
    permission: str = "safe"
    timestamp: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ApprovalResponse:
    """审批结果。"""
    request_id: str
    decision: str  # approved / denied
    session_id: str = ""


# ── WebSocket 消息 ────────────────────────────────────────────────────

@dataclass
class WSMessage:
    """WebSocket 消息基类。"""
    type: str = ""

    def to_json(self) -> str:
        import json
        return json.dumps(asdict(self), ensure_ascii=False)


@dataclass
class WSRegisterMsg(WSMessage):
    """Agent 注册消息。"""
    type: str = "register"
    name: str = ""


@dataclass
class WSRegisteredMsg(WSMessage):
    """Gateway 注册确认。"""
    type: str = "registered"
    name: str = ""
    config: dict = field(default_factory=dict)


@dataclass
class WSTaskMsg(WSMessage):
    """任务下发消息。"""
    type: str = "task"
    task_id: str = ""
    session_id: str = ""
    content: str = ""


@dataclass
class WSTaskUpdateMsg(WSMessage):
    """任务状态更新。"""
    type: str = "task_update"
    task_id: str = ""
    session_id: str = ""
    status: str = "running"
    result: str = ""
    error: str = ""
    progress: str = ""


@dataclass
class WSApprovalRequest(WSMessage):
    """审批请求。"""
    type: str = "approval_request"
    request_id: str = ""
    agent: str = ""
    session_id: str = ""
    tool: str = ""
    action: str = ""
    permission: str = ""
    timestamp: str = ""


@dataclass
class WSApprovalResponse(WSMessage):
    """审批响应。"""
    type: str = "approval_response"
    request_id: str = ""
    decision: str = ""
    session_id: str = ""
