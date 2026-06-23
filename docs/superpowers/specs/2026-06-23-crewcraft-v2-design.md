# CrewCraft V2 Design Spec

## 概述

CrewCraft 是一个多 Agent 协作平台。Gateway 常驻服务管理 Agent 生命周期，CLI 通过 REST API 与 Gateway 通信创建/管理 Agent 并下发任务。Agent 基于 `deepagents`（langchain-ai/deepagents）构建，以独立子进程运行在各自端口，通过 WebSocket 与 Gateway 双向通信。

## 架构

```
CLI (Typer) ──REST──→ Gateway (FastAPI) ──WebSocket──→ Agent Process (deepagents)
                           │
                           ├── data/agents/{name}.json       # Agent 静态配置
                           └── data/sessions/{name}/         # 运行时数据
                               ├── sessions.json             # 完整对话历史
                               └── tool_logs.json            # Tool 调用详情
```

## 目录结构

```
CrewCraft/
├── app/
│   ├── gateway/           # Gateway 常驻服务
│   │   ├── main.py        # FastAPI 入口
│   │   ├── api/           # REST 路由
│   │   │   ├── agents.py  # Agent CRUD
│   │   │   └── tasks.py   # Task 创建 + 状态查询
│   │   ├── manager/       # Agent 生命周期管理
│   │   │   ├── agent_manager.py
│   │   │   └── ws_manager.py
│   │   └── scheduler/     # 定时任务
│   │       └── cron.py
│   ├── agent/             # Agent 进程
│   │   └── server.py      # WebSocket server + deepagents 封装
│   └── cli/               # CLI 客户端
│       └── main.py
├── data/                  # 数据目录（gitignore）
│   ├── agents/
│   └── sessions/
├── pyproject.toml
└── main.py                # 统一入口
```

## 数据模型

### Agent 配置 `data/agents/{name}.json`

```json
{
  "name": "researcher",
  "model": "deepseek:chat",
  "system_prompt": "...",
  "tools": ["web_search", "file_read"],
  "port": 9001,
  "idle_timeout": 300,
  "created_at": "2026-06-23T10:00:00Z"
}
```

### 对话历史 `data/sessions/{name}/sessions.json`

LLM messages 格式，每条带 session_id (UUID)，tool 结果截断 100 字符。

```json
[
  {
    "session_id": "uuid",
    "role": "user",
    "content": "...",
    "timestamp": "..."
  }
]
```

### Tool 日志 `data/sessions/{name}/tool_logs.json`

```json
[
  {
    "session_id": "uuid",
    "tool_name": "web_search",
    "input": {},
    "output": "...",
    "timestamp": "..."
  }
]
```

## API 设计

```
POST   /api/agents                                    # 创建 agent
GET    /api/agents                                    # 列出 agent
GET    /api/agents/{name}                             # agent 详情
DELETE /api/agents/{name}                             # 删除 agent

POST   /api/tasks                                     # 创建任务（异步）
GET    /api/tasks/{task_id}                           # 任务状态
GET    /api/tasks                                     # 任务列表

GET    /api/agents/{name}/sessions                    # 会话列表
GET    /api/agents/{name}/sessions/{session_id}        # 对话历史
GET    /api/agents/{name}/sessions/{session_id}/tools  # tool 日志
```

## Agent 生命周期

```
[stopped] →(task)→ [starting] →(WS connected)→ [idle]
                                                    ↓(task received)
                                                 [running]
                                                    ↓(complete)
  [stopped] ←(timeout/error)── [stopping] ←─────────┘(idle timeout)
```

- Gateway 启动时不启动任何 agent
- 任务到达时按需 spawn 子进程
- WebSocket 心跳保活
- 空闲超时自动 shutdown，下次任务重新启动

## CLI 命令

```
crewcraft agent create --name <name> --model <model> --prompt <prompt>
crewcraft agent list
crewcraft agent inspect <name>
crewcraft agent delete <name>

crewcraft task run --agent <name> <content>
crewcraft task status <task_id>
crewcraft task list

crewcraft session list --agent <name>
crewcraft session show <session_id>

crewcraft gateway start
```

## 非目标（V2 不做）

- IM 平台对接（app/channels）
- Docker 化部署 Agent
- 用户认证与权限
