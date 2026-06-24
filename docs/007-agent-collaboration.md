# 007: Agent 间协作通信

## 问题

当前架构中 Agent 之间无法直接通信。Orchestrator 可以分派任务给多个 Agent，但 Agent 执行过程中如果
需要向其他 Agent 求助、传递中间结果、或协同完成一个子任务，没有通道。

## 方案对比

### 方案 A：Gateway 消息中继（推荐）

Gateway 已有所有 Agent 的 WebSocket 连接，作为消息 broker 转发。

```
Agent A ──WS──→ Gateway ──WS──→ Agent B
```

- Agent A 发 `{type: "agent_message", to: "agent_b", ...}` 给 Gateway
- Gateway 查连接表，转发给 Agent B
- 支持点对点和广播两种模式

优点：实现简单、Gateway 已有全部连接、可记录/审计
缺点：多一跳延迟（毫秒级，可忽略）

### 方案 B：Agent 直连

Agent 之间建立独立的 WebSocket 连接。

优点：低延迟、去中心化
缺点：复杂、端口管理、NAT/防火墙问题、Docker 网络配置麻烦

### 方案 C：消息队列

引入 Redis/RabbitMQ 作为消息中间件。

优点：持久化、可靠性高、解耦
缺点：引入外部依赖、过于重量级

## 推荐方案 A

Gateway 在现有 WebSocket 协议上增加消息转发。

### 协议扩展

```json
// Agent A → Gateway：请求发给 Agent B
{
  "type": "agent_message",
  "to": "agent_b",
  "session_id": "uuid",
  "content": "请帮我验证这个结果是否正确...",
  "context": {}   // 可选附加上下文
}

// Gateway → Agent B：转发
{
  "type": "agent_message",
  "from": "agent_a",
  "session_id": "uuid",
  "content": "请帮我验证这个结果是否正确...",
  "context": {}
}

// Agent B → Gateway → Agent A：回复
{
  "type": "agent_message",
  "to": "agent_a",
  "session_id": "uuid",
  "reply_to": "original_session_id",
  "content": "验证通过，结果正确"
}
```

### 广播模式

```json
// 发给所有在线 Agent
{
  "type": "agent_broadcast",
  "from": "agent_a",
  "content": "我已完成第一部分，谁可以接手第二部分？"
}
```

### 变更范围

- `ws_manager.py`：新增 `agent_message` 和 `agent_broadcast` 消息处理
- `agent/server.py`：任务执行中可调用 `send_to_agent()` 向其他 Agent 发消息，接收 `agent_message` 并返回结果
- 协议新增 2 种消息类型

### 协作场景

```
用户: "写一份技术报告，包含调研和数据分析"
  │
Orchestrator:
  ├→ researcher: "调研 Python 3.13 新特性"
  ├→ analyst: "分析性能数据"
  │
researcher 执行中:
  │→ 发消息给 analyst: "你那边有性能对比数据吗？"
  │← analyst 回复: "有，Python 3.13 比 3.12 快 15%"
  │
Orchestrator:
  ← researcher: "调研完成"
  ← analyst: "分析完成"
  → 汇总 → 用户: "报告已完成"
```
