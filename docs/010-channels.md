# 010: IM 平台 Channels 接入

## 概述

支持微信、钉钉、飞书三个 IM 平台接入。用户在 IM 中 @机器人 发消息，
Gateway 接收后转给 Orchestrator 处理，结果通过 IM 返回。

## 架构

Gateway 启动时注册 Channel。每个 Channel 向 IM 平台注册 webhook 回调地址，
平台收到用户消息后通过 HTTP POST 推送消息到 Gateway。
回复消息时 Gateway 调用平台 API 发送。

```
用户 (微信/钉钉/飞书 App)
  │
  │  发消息给机器人
  ▼
IM 平台服务器
  │
  │  HTTP POST (webhook 回调)
  ▼
Gateway (FastAPI)
  ├── POST /api/channels/wechat/webhook    ← 微信回调
  ├── POST /api/channels/dingtalk/webhook  ← 钉钉回调
  └── POST /api/channels/feishu/webhook    ← 飞书回调
  │
  ▼
Orchestrator → Agent 执行
  │
  ▼
调用平台 API 回复消息
  ├── 微信: POST https://qyapi.weixin.qq.com/cgi-bin/message/send
  ├── 钉钉: POST https://oapi.dingtalk.com/robot/send
  └── 飞书: POST https://open.feishu.cn/open-apis/im/v1/messages
```

> 这是标准的 webhook 模式：平台推送消息到 Gateway，Gateway 调用平台 API 回复。
> 不是 Gateway 主动连到平台建立 WebSocket。平台通过配置的回调 URL 找到 Gateway。

## 设计

### BaseChannel 抽象

```python
class BaseChannel(ABC):
    name: str           # wechat / dingtalk / feishu
    display_name: str   # 微信 / 钉钉 / 飞书

    @abstractmethod
    async def verify(self, request) -> bool        # 验证签名/解密
    @abstractmethod
    async def parse(self, request) -> dict          # 解析消息 → {chat_id, content}
    @abstractmethod
    async def send(self, chat_id, content) -> bool  # 调用平台 API 发送消息
```

### 消息流

```
IM 发送消息 → webhook POST → verify 签名 → parse 提取文本
  → 创建 task → Orchestrator → Agent 执行
  → channel.reply(chat_id, result)
```

### 配置

```env
CREWCRAFT_CHANNELS=wechat,dingtalk,feishu

# 微信
CREWCRAFT_WECHAT_TOKEN=xxx
CREWCRAFT_WECHAT_AES_KEY=xxx
CREWCRAFT_WECHAT_APP_ID=xxx

# 钉钉
CREWCRAFT_DINGTALK_APP_KEY=xxx
CREWCRAFT_DINGTALK_APP_SECRET=xxx

# 飞书
CREWCRAFT_FEISHU_APP_ID=xxx
CREWCRAFT_FEISHU_APP_SECRET=xxx
```

### Gateway 路由

```
POST /api/channels/wechat/webhook    → 微信回调（含 verify）
POST /api/channels/dingtalk/webhook  → 钉钉回调
POST /api/channels/feishu/webhook    → 飞书回调
GET  /api/channels/status            → 各 channel 状态
```

### Channel 管理

- 启动时根据 `CREWCRAFT_CHANNELS` 注册启用的 channel
- 未配置密钥的 channel 跳过
- 消息统一走 task 流程：`task = POST /api/tasks {content}` → 编排 → 回复

### 目录结构

```
app/channels/
├── __init__.py      # ChannelManager, 注册表
├── base.py          # BaseChannel 抽象
├── wechat.py        # 微信企业号
├── dingtalk.py      # 钉钉
└── feishu.py        # 飞书
```

### 使用

```bash
# 配置
cp .env.example .env
# 编辑填入各平台密钥，设置 CREWCRAFT_CHANNELS=wechat,dingtalk,feishu

# 启动
crewcraft gateway start

# IM 中 @机器人 "帮我搜索..."
# → Agent 执行 → 回复到 IM
```
