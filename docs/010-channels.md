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

### 消息流

```
Channel.start() → 建立长连接 → 平台推送消息
  → Channel 解析 → 创建 task → Orchestrator → Agent
  → Channel.send(chat_id, result) → 平台 API → 用户
```

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
├── wechat.py        # 微信（HTTP 长轮询）
├── dingtalk.py      # 钉钉（WebSocket）
└── feishu.py        # 飞书（WebSocket）
```
