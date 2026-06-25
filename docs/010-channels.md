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
Channel A (微信) ──→ InboundMsg ──→ MsgManager ──→ Orchestrator
Channel B (钉钉) ──→ InboundMsg ──→    │              │
Channel C (飞书) ──→ InboundMsg ──→    │          Agent 执行
                                       │              │
Channel A ←── OutboundMsg ←── MsgManager ←── 结果 ───┘
Channel B ←── OutboundMsg ←──
Channel C ←── OutboundMsg ←──
```

**优势：**
- Channel 不需要知道 task/orchestrator 的存在，只收发消息
- 新增 Channel 只需实现收发，自动接入
- 支持流式推送（Agent 边执行边通过 MsgManager 推送进度到 Channel）
- 统一管理多 Channel 的会话和路由

**消息结构：**

```python
@dataclass
class InboundMsg:
    channel: str        # "wechat" / "dingtalk" / "feishu"
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
    metadata: dict      # 扩展信息（流式标记等）
```

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
├── wechat.py        # 微信（HTTP 长轮询）
├── dingtalk.py      # 钉钉（WebSocket）
└── feishu.py        # 飞书（WebSocket）
```
