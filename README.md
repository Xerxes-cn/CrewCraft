# CrewCraft

多 Agent 协作平台。Gateway 常驻服务管理 Agent 生命周期，CLI 通过 REST API 创建/管理 Agent 并下发任务。Agent 基于 [deepagents](https://github.com/langchain-ai/deepagents) 构建。

## 架构

```
CLI (Typer) ──REST──→ Gateway (FastAPI) ──WebSocket──→ Agent Process (deepagents)
                           │
                           ├── data/agents/{name}.json
                           └── data/sessions/{name}/
                               ├── sessions.json
                               └── tool_logs.json
```

- **Gateway**: FastAPI 常驻服务，REST API + 内部 WebSocket，管理 Agent 生命周期
- **Agent**: 独立子进程，各自端口，按需启动，空闲自动退出
- **CLI**: Typer 客户端，通过 HTTP 调用 Gateway API

## 快速开始

```bash
# 安装依赖
uv sync

# 启动 Gateway
uv run crewcraft gateway start

# 新开终端，创建 Agent
uv run crewcraft agent create --name researcher --model deepseek:chat --prompt "你是一个研究助手"

# 下发任务
uv run crewcraft task run --agent researcher "帮我研究 LangGraph 最新版本"

# 查看帮助
uv run crewcraft --help
```

## CLI 命令

### Agent 管理

```bash
crewcraft agent create  --name <name> --model <model> [--prompt <prompt>] [--tools <t1,t2>]
crewcraft agent list
crewcraft agent inspect <name>
crewcraft agent delete  <name>
```

### 任务管理

```bash
crewcraft task run     --agent <name> <content>
crewcraft task status  <task_id>
crewcraft task list
```

### 会话历史

```bash
crewcraft session list  --agent <name>
crewcraft session show  <session_id> --agent <name>
```

### Gateway

```bash
crewcraft gateway start [--host 127.0.0.1] [--port 8000]
```

## API 接口

Gateway 默认监听 `http://127.0.0.1:8000`

### Agent

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/agents` | 创建 Agent |
| `GET` | `/api/agents` | 列出所有 Agent |
| `GET` | `/api/agents/{name}` | Agent 详情 |
| `DELETE` | `/api/agents/{name}` | 删除 Agent |

### 任务

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/tasks` | 创建任务（异步返回 task_id） |
| `GET` | `/api/tasks/{task_id}` | 查询任务状态 |
| `GET` | `/api/tasks` | 列出所有任务 |

### 会话历史

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/agents/{name}/sessions` | 会话列表 |
| `GET` | `/api/agents/{name}/sessions/{session_id}` | 完整对话历史 |
| `GET` | `/api/agents/{name}/sessions/{session_id}/tools` | Tool 调用日志 |

## 数据存储

纯文件系统，默认目录 `data/`（已加入 `.gitignore`）。

```
data/
├── agents/
│   └── {name}.json          # Agent 配置（name, model, system_prompt, tools, port）
└── sessions/
    └── {name}/
        ├── sessions.json     # 完整对话历史（LLM messages 格式，tool 结果截断 100 字符）
        └── tool_logs.json    # Tool 调用完整 input/output
```

可通过环境变量 `CREWCRAFT_DATA_DIR` 自定义数据目录。

## 配置

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `CREWCRAFT_DATA_DIR` | `data` | 数据存储目录 |
| `CREWCRAFT_GATEWAY_WS` | `ws://127.0.0.1:8765` | Gateway WebSocket 地址 |
| `CREWCRAFT_AGENT_NAME` | - | Agent 进程的 name |
| `CREWCRAFT_AGENT_PORT` | - | Agent 进程的端口 |

## 依赖

- Python >= 3.11
- [deepagents](https://github.com/langchain-ai/deepagents) — Agent 执行引擎
- FastAPI + Uvicorn — Gateway HTTP 服务
- websockets — Gateway ↔ Agent 双向通信
- Typer + httpx — CLI 客户端

## 开发

```bash
# 安装开发依赖
uv sync --dev

# 运行测试
uv run pytest
```

## License

MIT
