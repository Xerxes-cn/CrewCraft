# 009: Human-in-the-Loop 操作审批

## 概述

Agent 执行敏感操作（执行 Shell 命令、修改文件、发送网络请求等）时，需要用户确认。
同时在 REPL 中接入外部 Agent（Claude Code 等）的权限交互。

## 设计

### 权限分级

| 级别 | 说明 | 示例工具 | 默认行为 |
|------|------|----------|----------|
| `safe` | 只读，无副作用 | time_now, calculator, text_stats, uuid_gen, hash, random_number | 自动通过 |
| `read` | 读取外部数据 | web_search, web_fetch, file_ops(read) | 自动通过 |
| `write` | 修改文件 | file_ops(write/delete), shell_exec | 需要确认 |
| `dangerous` | 可能破坏系统 | shell_exec(rm, sudo), file_ops(delete /) | 需要确认 + 警告 |

### 工具权限标记

```python
# 在注册工具时声明权限级别
@register("shell_exec", ..., permission="write")
@register("file_ops", ..., permission="write")
@register("web_search", ..., permission="read")
@register("time_now", ..., permission="safe")
```

### 审批流程

```
Agent 执行中
  │
  ├─ 调用 safe/read 工具 → 自动通过，不打扰用户
  │
  └─ 调用 write/dangerous 工具
        │
        ▼
      Gateway 收到 tool call
        │
        ▼
      查权限表 → 需要确认
        │
        ├── REPL 已连接 → 发送审批请求到 REPL
        │     crewcraft> ⚠ agent 'researcher' 要执行: rm -rf /tmp/cache
        │     crewcraft> [Y] 允许  [N] 拒绝  [A] 本次会话全部允许
        │
        ├── REPL 未连接 → 记录 pending，下一个 REPL session 可以查看
        │
        └── 超时 (60s) → 自动拒绝
```

### REPL 交互 — 主动推送

REPL 不要求用户手动查询。后台线程持续监听 Gateway，有审批请求时
**立即弹出** 打断当前操作，用户处理完再回到正常交互。

```
终端 2: REPL
─────────────────────────────────────
crewcraft> 帮我清理系统临时文件
  (task 创建成功，等待 agent 执行...)

  ╔══════════════════════════════════╗
  ║ ⚠ 需要确认                       ║
  ║ Agent: admin                     ║
  ║ 操作: shell_exec                 ║
  ║ 命令: rm -rf /tmp/cache          ║
  ║ 权限级别: write                   ║
  ║                                  ║
  ║ [Y] 允许  [N] 拒绝  [A] 全部允许  ║
  ╚══════════════════════════════════╝
  > y
  ✓ 已批准

crewcraft>                          # 回到正常交互
```

**监听机制**：REPL 启动后后台线程轮询 `GET /api/approvals/pending?session=<id>`，
发现待审批请求立即在终端展示。一条接一条，流水线式逐个审批。

### Gateway 协议扩展

```json
// Gateway → REPL: 审批请求
{
  "type": "approval_request",
  "request_id": "approval_abc123",
  "agent": "researcher",
  "session_id": "uuid",
  "tool": "shell_exec",
  "action": "rm -rf /tmp/cache",
  "permission": "write",
  "timestamp": "..."
}

// REPL → Gateway: 审批结果
{
  "type": "approval_response",
  "request_id": "approval_abc123",
  "decision": "approved",   // approved | denied | approved_all
  "session_id": "uuid"
}
```

### 外部 Agent 权限对接

Claude Code / Codex 有自己的权限系统。Provider 适配时：

```python
class ClaudeCodeProvider(AgentProvider):
    async def start(self, config):
        if config.approval_mode == "auto":
            args = ["--dangerously-skip-permissions"]
        elif config.approval_mode == "interactive":
            # 不跳过权限，让 Claude Code 输出到 stderr
            # Gateway 捕获 stderr 中的确认提示
            # 转发到 REPL 让用户确认
            args = []
```

### 变更范围

- `app/agent/tools/registry.py`：Tool 增加 `permission` 字段
- `app/agent/tools/*.py`：所有工具标注权限级别
- `app/gateway/manager/ws_manager.py`：新增 approval_request/response 消息处理
- `app/gateway/api/approvals.py`：`GET /api/approvals/pending` 端点（REPL 轮询用）
- `app/cli/repl.py`：后台监听线程 + 即时弹出审批框，逐个处理
- `app/gateway/api/agents.py`：Agent 创建时支持 `approval_mode` 参数
- `app/config.py`：默认审批超时配置

### 使用场景

```bash
# 终端 1: Gateway
crewcraft gateway start

# 终端 2: REPL — 审批主动推送
crewcraft
> /agent create admin --desc "系统管理" --approval interactive
> /task run "清理临时文件"

  (后台 agent 执行中...)
  ╔════════════════════════════════╗
  ║ ⚠ admin 要执行:                ║
  ║   rm -rf /tmp/cache            ║
  ║ [Y]允许 [N]拒绝 [A]全部允许    ║
  ╚════════════════════════════════╝
  > y
  ✓ 已批准，agent 继续执行

crewcraft>                          # 审批完回到交互
```

### Agent 配置

```json
// data/agents/{name}.json
{
  "name": "admin",
  "model": "deepseek:chat",
  "approval_mode": "interactive",  // auto | interactive
  "description": "系统管理"
}
```
