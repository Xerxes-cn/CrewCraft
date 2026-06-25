# 011: Skill + MCP 集成

## 概述

Agent 支持 MCP (Model Context Protocol) 协议和自定义 Skill。
MCP 是标准化的工具协议，任何实现 MCP 的服务器都可以被 Agent 调用。
Skill 是 Agent 的按需加载行为模块。

## 设计

### MCP 集成

Agent 启动时加载 MCP 配置，自动连接 MCP Server，将其 tools 注册到自己的工具列表。

```
Agent                     MCP Server
  │                          │
  │──── connect ────────────→│  (stdio/sse/http)
  │←─── list tools ──────────│
  │──── call tool ──────────→│
  │←─── result ──────────────│
```

### 配置

`data/agents/{name}/mcp.json`:
```json
{
  "servers": [
    {"name": "filesystem", "command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]},
    {"name": "fetch", "command": "uvx", "args": ["mcp-server-fetch"]},
    {"name": "docker-mcp", "command": "docker", "args": ["run", "-i", "mcp/docker"]}
  ]
}
```

### Skill 系统扩展

`data/agents/{name}/skills/` 目录：
```
skills/
├── code-review.md     # 自定义审查流程
├── deploy.md          # 部署检查清单
└── research.md        # 深度研究流程
```

每个 skill 是一个 markdown 文件，包含 Agent 的行为指令和工具使用指南。
Agent 执行任务时自动加载相关 skill。

### 实现计划

1. `app/agent/mcp.py` — MCP 客户端（连接、发现、调用）
2. 更新 `agent_manager.py` — 启动时加载 MCP 配置
3. 更新 `app/agent/server.py` — 合并 MCP tools 到工具列表
4. `app/agent/skills.py` — Skill 加载器 + 注入 system_prompt
5. CLI: `/agent skills <name>` 查看/管理 skills

### 变更范围

- `app/agent/mcp.py` — 新增
- `app/agent/skills.py` — 新增
- `app/agent/server.py` — 合并 MCP tools
- `app/gateway/manager/agent_manager.py` — 加载 MCP 配置
