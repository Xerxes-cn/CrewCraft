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

### Skill 系统

Agent 专属 Skill，存放在数据目录下：

```
data/agents/{name}/skills/      # 该 Agent 的 skills
├── code-review.md
├── deploy.md
└── research.md
```

- Skill 是 markdown 文件，内容为 Agent 行为指令和工具使用指南
- 创建 Agent 后用户自行在 skills/ 目录下添加 .md 文件
- Agent 启动时 `app/agent/skills` 加载器扫描该目录，注入 system_prompt

### 实现计划

1. `app/agent/mcp.py` — MCP 客户端（连接、发现、调用）
2. `app/agent/skills/__init__.py` — Skill 加载器
3. 更新 `app/agent/server.py` — 合并 MCP tools + 注入 skills

### 变更范围

- `app/agent/mcp.py` — 新增
- `app/agent/skills/__init__.py` — Skill 加载器
- `app/agent/server.py` — 合并 MCP tools
