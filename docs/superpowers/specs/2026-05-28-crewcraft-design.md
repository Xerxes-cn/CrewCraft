# CrewCraft Design Spec

## 概述

CrewCraft 是一个多 Agent 角色协作平台。用户通过 Web UI 创建 Agent 团队（Crew），为每个 Agent 配置不同的角色和工具，定义协作工作流，然后在可视化界面中发起任务并实时观察多 Agent 协作过程。同时提供 CLI 工具支持终端执行。

**核心差异化**：与 CrewAI、AutoGen 等需要写代码的项目不同，CrewCraft 提供完整的用户界面，让非技术用户也能零代码构建多 Agent 协作系统。

## 目标用户

兼顾两类用户：
- **简单模式**：非技术用户（产品经理、运营人员），完全通过 UI 配置，零代码
- **高级模式**：技术用户（开发者），可自定义 System Prompt、模型参数等

## 架构

```
Browser (React) → FastAPI (REST + WebSocket) → 配置→Graph 编译器 → LangGraph 运行时 → DeepSeek API
```

### 分层职责

| 层 | 技术 | 职责 |
|---|---|---|
| 前端 | React + Vite + Zustand | Crew/Agent 管理界面、任务执行与监控、实时对话展示 |
| API 层 | FastAPI | REST CRUD、WebSocket 流推送 |
| 编译层 | 自研 compiler.py | 将 UI 配置编译为 LangGraph StateGraph |
| 运行层 | LangGraph | Agent 协作状态机、checkpoint、流式输出 |
| LLM 层 | DeepSeek API | 当前唯一适配的 LLM，后续扩展多 API |

### 数据流

1. 用户通过 UI 创建 Crew → 添加 Agent → 配置角色/工具 → 选择 Workflow
2. 配置持久化到 SQLite/PostgreSQL
3. 用户发起任务 → 后端读取配置 → Compiler 编译为 LangGraph → 执行
4. 执行过程中的消息通过 WebSocket 实时推送到前端
5. 任务完成后结果存储，可在历史中回放

## 核心数据模型

```
Crew (团队)
├── id, name, description
├── agents: [Agent]        ← 成员列表
├── workflow: Workflow     ← 协作流程定义
└── tasks: [Task]          ← 任务历史

Agent (成员)
├── id, name, role         ← 角色描述（如"研究员"、"写手"）
├── system_prompt           ← 系统提示词
├── tools: [Tool]           ← 可使用的工具
├── model_config            ← 模型参数（temperature 等）
└── depends_on: [Agent]     ← 可选的依赖关系

Workflow (协作流程)
├── type: sequential | hierarchical | roundtable
│   sequential:   Agent 按顺序执行，前一个输出是后一个输入
│   hierarchical: 一个 Leader Agent 分配任务给其他 Agent
│   roundtable:   所有 Agent 自由讨论，达成共识
└── config: {...}

Task (任务)
├── id, crew_id, status
├── input: str              ← 用户输入
├── messages: [Message]     ← 协作对话历史
└── result: str             ← 最终输出
```

## API 设计

```
POST   /api/crews                    # 创建团队
GET    /api/crews                    # 团队列表
GET    /api/crews/{id}               # 团队详情
PUT    /api/crews/{id}               # 更新团队
DELETE /api/crews/{id}               # 删除团队

POST   /api/crews/{id}/agents        # 添加成员
PUT    /api/agents/{id}              # 更新成员
DELETE /api/agents/{id}              # 删除成员

POST   /api/crews/{id}/run          # 执行任务（启动协作）
WS     /api/crews/{id}/stream       # 实时流订阅

GET    /api/crews/{id}/tasks        # 任务历史
GET    /api/tasks/{id}              # 任务详情（含完整对话）
```

## 前端路由

```
/                          → 首页，Crew 列表
/crews/:id                 → Crew 详情（成员列表、Workflow 配置）
/crews/:id/run             → 任务执行页（输入任务 + 实时对话展示）
/tasks/:id                 → 历史任务详情
```

## CLI 命令

```bash
crewcraft run <crew_id> --task "写一篇关于AI的博客"
crewcraft run <crew_id> --task "..." --stream
crewcraft ls
```

## 项目结构

```
CrewCraft/
├── backend/
│   ├── app/
│   │   ├── api/              # FastAPI 路由
│   │   ├── models/           # Pydantic + SQLAlchemy 模型
│   │   ├── engine/           # LangGraph 执行引擎
│   │   │   ├── compiler.py   # 配置 → Graph 编译器
│   │   │   ├── workflows/    # sequential / hierarchical / roundtable
│   │   │   └── agents.py     # Agent 运行循环
│   │   ├── llm/              # DeepSeek API 封装
│   │   └── ws/               # WebSocket 管理
│   ├── alembic/              # 数据库迁移
│   ├── requirements.txt
│   └── main.py
├── frontend/
│   ├── src/
│   │   ├── pages/            # 对应路由页面
│   │   ├── components/       # 共用组件
│   │   └── api/              # 后端 API 调用封装
│   └── package.json
├── cli/
│   ├── main.py               # Typer CLI 入口
│   └── client.py             # 对接后端 API
├── docker-compose.yml
└── README.md
```

## 技术选型

| 层 | 选型 | 原因 |
|---|---|---|
| 后端框架 | FastAPI | 异步支持好，WebSocket 原生 |
| 数据库 | SQLite（开发）/ PostgreSQL（生产） | 轻量起步，按需升级 |
| Agent 引擎 | LangGraph | StateGraph + checkpoint，复用成熟能力 |
| LLM | DeepSeek API | 当前唯一适配，后续扩展多 API |
| 前端 | React + Vite | 轻量快速 |
| 状态管理 | Zustand | 比 Redux 轻，够用 |
| CLI | Typer | 和 FastAPI 同生态 |
| 部署 | Docker Compose | 前后端 + 数据库一键启动 |

## 非目标（V1 不做）

- 多 LLM 提供商适配（V1 仅 DeepSeek）
- 用户认证与权限系统
- 工具插件市场
- Agent 记忆/长期上下文
- 团队模板市场
- 多语言国际化
