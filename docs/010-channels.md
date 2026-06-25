# 010: IM 平台 Channels 接入

## 概述

支持微信、钉钉、飞书三个 IM 平台接入。每个 Channel 通过平台 SDK **主动连接**
到 IM 服务器（WebSocket 或长轮询），不需要公网 IP、不需要配置 webhook 回调 URL。

## 架构

Gateway 启动时初始化已启用的 Channel。Channel 通过各平台 SDK 主动建立
与 IM 服务器的长连接，接收到消息后转发给 Gateway 的 Orchestrator 处理。

```
Gateway (CrewCraft)
  │
  ├── WeChat Channel ──HTTP long-poll──→ ilinkai.weixin.qq.com
  ├── DingTalk Channel ──WebSocket─────→ DingTalk Stream API
  └── Feishu Channel ──WebSocket───────→ Feishu Open API
       │
       │  收到用户消息
       ▼
  Orchestrator → Agent 执行 → Channel.send() → IM 平台 API → 用户收到回复
```

> 不需要公网暴露端口、不需要配置 webhook 回调。Channel 主动连到平台，
> 在本地/Docker 环境即可工作。

## 设计

### BaseChannel 抽象

```python
class BaseChannel(ABC):
    name: str           # wechat / dingtalk / feishu
    display_name: str   # 微信 / 钉钉 / 飞书

    @abstractmethod
    async def start(self)           # 连接平台，开始监听消息
    @abstractmethod
    async def stop(self)            # 断开连接
    @abstractmethod
    async def send(self, chat_id, content)  # 发送消息
```

### MsgManager 消息总线

多 Channel 场景下需要一个统一的消息管理器，解耦 Channel 和 Agent：

```
CLI ────────────→ InboundMsg ──→ MsgManager ──→ Orchestrator
WeChat ──────────→ InboundMsg ──→    │              │
DingTalk ────────→ InboundMsg ──→    │          Agent 执行
Feishu ──────────→ InboundMsg ──→    │              │
                                     │              │
CLI ←──── OutboundMsg ←── MsgManager ←── 结果 ─────┘
WeChat ←── OutboundMsg ←──
DingTalk ← OutboundMsg ←──
Feishu ←── OutboundMsg ←──
```

**审批路由：**

Agent 执行需要用户确认时，通过 channel 信息找到正确的 Channel 推送审批：

```
用户 (微信) → task(channel=wechat, chat_id=xxx)
  → Agent 调 shell_exec → 需要审批
  → MsgManager 查 channel=wechat → OutboundMsg(wechat, chat_id, "确认执行?")
  → 微信 Channel.send("确认执行?")
  → 用户回复 "y" → InboundMsg → MsgManager → agent 继续
```

**优势：**
- Channel 不需要知道 task/orchestrator 的存在，只收发消息
- 新增 Channel 只需实现收发，自动接入
- 流式推送 + 审批确认 都通过 MsgManager 统一路由
- 审批知道找哪个 Channel 的用户确认

**消息结构（含 channel 路由信息）：**

```python
@dataclass
class InboundMsg:
    channel: str        # "cli" / "wechat" / "dingtalk" / "feishu"
    sender_id: str      # 发送者 ID
    chat_id: str        # 会话 ID
    content: str        # 消息文本
    media: list[str]    # 附件路径

@dataclass
class OutboundMsg:
    channel: str        # 目标 Channel
    chat_id: str
    content: str        # 回复内容
    media: list[str]    # 附件
    metadata: dict      # 扩展信息: {_progress, _stream_delta, _approval, ...}
```

**Task 携带 channel 信息**，审批时 MsgManager 根据 `OutboundMsg.channel` 路由到正确的 Channel。

### 消息流

### 各平台通信方式

| 平台 | SDK | 连接方式 | 说明 |
|------|-----|----------|------|
| 微信 | 无官方 SDK | HTTP 长轮询 `ilinkai.weixin.qq.com` | 扫码登录，token 持久化 |
| 钉钉 | `dingtalk-stream` | WebSocket | AppKey/Secret 认证 |
| 飞书 | `lark-oapi` | WebSocket | App ID/Secret 认证 |

### 配置

```env
CREWCRAFT_CHANNELS=wechat,dingtalk,feishu

# 微信
CREWCRAFT_WECHAT_TOKEN=        # 扫码登录后自动获取

# 钉钉
CREWCRAFT_DINGTALK_CLIENT_ID=
CREWCRAFT_DINGTALK_CLIENT_SECRET=

# 飞书
CREWCRAFT_FEISHU_APP_ID=
CREWCRAFT_FEISHU_APP_SECRET=
```

### 使用

```bash
# 本地开发 — 配置密钥后直接启动
cp .env.example .env
crewcraft gateway start
# Channel 自动连接到各平台，无需公网暴露
```

### 目录结构

```
app/channels/
├── __init__.py      # ChannelManager, 注册表
├── base.py          # BaseChannel 抽象
├── bus.py           # MsgManager — 消息总线（InboundMsg/OutboundMsg）
├── cli.py           # CLI REPL Channel（终端交互）
├── wechat.py        # 微信（HTTP 长轮询）
├── dingtalk.py      # 钉钉（WebSocket）
└── feishu.py        # 飞书（WebSocket）
```

CLI REPL 也统一为 Channel，和其他平台平级，不再直接调 task API。
