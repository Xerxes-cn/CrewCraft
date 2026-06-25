# 012: 微信/钉钉/飞书 SDK 集成

## 概述

在已有的 Channel 骨架上补完整 SDK 实现，使三个 IM 平台可实际接入使用。

## 设计

### 微信 (WeChat)

使用 `ilinkai.weixin.qq.com` HTTP API，参考 nanobot 的协议逆向实现。

```
WeChatChannel
  ├── start()  → 扫码登录获取 token（持久化）
  ├── _poll_once() → POST /ilink/bot/getupdates 长轮询
  ├── send() → POST /ilink/bot/sendmessage
  └── _download_media() → 下载图片/文件到本地
```

- token 保存到 `data/channels/wechat/{name}/account.json`
- 支持私聊、群聊（需 @）
- 消息分片（4000 字符限制）

### 钉钉 (DingTalk)

使用 `dingtalk-stream` SDK 的 WebSocket 长连接。

```
DingTalkChannel
  ├── start() → DingTalkStreamClient.start()
  ├── 收到消息 → _on_message()
  └── send() → POST /v1.0/robot/oToMessages/batchSend
```

- SDK 自动处理重连
- 支持私聊和群聊

### 飞书 (Feishu)

使用 `lark-oapi` SDK 的 WebSocket 长连接。

```
FeishuChannel
  ├── start() → lark.ws.Client.start()
  ├── 收到消息 → _on_message()
  ├── send() → POST /open-apis/im/v1/messages
  └── 流式输出 → CardKit 流式卡片
```

- 支持流式推送到飞书卡片（打字机效果）
- 支持多种消息格式（text/post/interactive card）

### 公共功能

所有 Channel 共用：
- `_handle_message()` → bus.publish_inbound()
- `send()` → bus.consume_outbound() 后调用平台 API
- 媒体下载到 `data/media/{platform}/`

### 配置示例

`data/channels.json`:
```json
{
  "channels": [
    {
      "type": "wechat", "name": "my-wechat",
      "enabled": true,
      "base_url": "https://ilinkai.weixin.qq.com",
      "allow_from": ["*"]
    },
    {
      "type": "dingtalk", "name": "dingtalk-bot",
      "enabled": true,
      "client_id": "xxx",
      "client_secret": "xxx"
    },
    {
      "type": "feishu", "name": "feishu-bot",
      "enabled": true,
      "app_id": "xxx", "app_secret": "xxx"
    }
  ]
}
```

### 变更范围

- `app/channels/wechat.py` — 完整 HTTP 长轮询
- `app/channels/dingtalk.py` — 完整 WebSocket
- `app/channels/feishu.py` — 完整 WebSocket + 流式
- `data/channels.json` — 更新配置模板
