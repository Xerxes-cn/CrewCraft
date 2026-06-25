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

### 监督机制

Gateway 的 Orchestrator 作为监督者，防止子 Agent 通信陷入死循环：

```
Agent A ←──→ Agent B
      ↘     ↙
     Orchestrator (监督)
```

**防护规则：**

| 规则 | 默认值 | 说明 |
|------|--------|------|
| 最大轮次 | 10 | 单个会话中 Agent 间消息往返次数上限 |
| 最大深度 | 3 | Agent A→B→C 链条深度，超过则截断 |
| 重复检测 | 开启 | 相同 content 重复发送则警告 |
| 超时 | 60s | 协作链条无进展则强制终止 |

**监督动作：**

```json
// Orchestrator 检测到异常 → 发 supervisor 消息终止协作
{
  "type": "supervisor",
  "action": "halt",
  "reason": "达到最大轮次上限 (10 轮)",
  "session_id": "uuid"
}
```

**跟踪数据结构：**

```python
# ws_manager 中维护每个协作会话的跟踪信息
_collab_sessions = {
    "session_id": {
        "round": 3,           # 当前轮次
        "chain": ["A","B"],   # 参与方链条
        "started_at": 12345,  # 开始时间
        "last_activity": 12350,  # 最后活动时间
    }
}
```

### 变更范围

- `ws_manager.py`：新增 `agent_message`、`agent_broadcast` 处理 + 监督跟踪
- `orchestrator.py`：新增协作监控协程，超时/超轮次自动终止
- `agent/server.py`：支持发送/接收 Agent 间消息
- 协议新增 3 种消息类型：`agent_message`、`agent_broadcast`、`supervisor`

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
