# 014: 数据模型 + IM SDK 完善

## 概述

1. 统一内部消息模型为 dataclass/Pydantic，收发时 format/validate
2. 完成微信/钉钉/飞书 SDK 集成

## 数据模型统一

### 消息总线

`app/channels/bus.py` 已有 dataclass，保持不变：

```python
@dataclass
class InboundMsg:
    channel: str
    sender_id: str
    chat_id: str
    content: str
    media: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

@dataclass
class OutboundMsg:
    channel: str
    chat_id: str
    content: str = ""
    media: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
```

### 新增消息模型

`app/models.py` — 统一消息模型：

```python
@dataclass
class AgentConfig: ...       # 已有的移过来
@dataclass
class TaskRequest: ...       # task 请求
@dataclass
class TaskResult: ...        # task 结果
@dataclass
class ChannelConfig: ...     # Channel 配置
@dataclass
class ApprovalItem: ...      # 审批项
```

### 校验规则

- 收发时统一 format：`InboundMsg.format()` / `OutboundMsg.format()` 裁剪空白、长度限制
- Channel 配置：Pydantic 自动校验必填字段
- WebSocket 消息：dict → dataclass 转换

## IM SDK 实现

### 微信 (WeChat)

参考 nanobot 协议逆向，使用 `ilinkai.weixin.qq.com` HTTP API：
- `_poll_once()` → POST /ilink/bot/getupdates
- `send()` → POST /ilink/bot/sendmessage
- 扫码登录 → token 持久化

### 钉钉 (DingTalk)

使用 dingtalk-stream SDK：
- WebSocket 长连接接收消息
- send() → REST API 发送
- 支持群聊和私聊

### 飞书 (Feishu)

使用 lark-oapi SDK：
- WebSocket 长连接
- send() → REST API + 流式卡片
- 支持多消息格式

## 变更文件

- `app/models.py` — 新增统一数据模型
- `app/channels/bus.py` — format/validate
- `app/channels/wechat.py` — 完整实现
- `app/channels/dingtalk.py` — 完整实现
- `app/channels/feishu.py` — 完整实现
- 其他引用 dict 的地方 → 替换为 dataclass
