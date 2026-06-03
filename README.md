# CrewCraft

多 Agent 角色协作平台 —— 通过可视化界面创建 AI Agent 团队，为每个 Agent 配置不同角色，让一群 Agent 互相协作完成任务。

与 CrewAI、AutoGen 等需要写代码的方案不同，CrewCraft 提供完整的 Web UI，非技术用户也能零代码构建多 Agent 协作系统。

## 特性

- **可视化 Crew 管理** — 在 Web 界面中创建团队、添加 Agent、配置角色和提示词
- **三种协作工作流** — Sequential（流水线）、Hierarchical（Leader/Worker）、Roundtable（圆桌讨论）
- **实时流式展示** — WebSocket 推送 Agent 对话过程，实时查看协作进度
- **CLI 工具** — 支持终端执行任务，方便脚本集成
- **DeepSeek 驱动** — 默认使用 DeepSeek API，后续可扩展更多 LLM

## 架构

```
Browser (React) → FastAPI (REST + WebSocket) → LangGraph 运行时 → DeepSeek API
```

| 层 | 技术 |
|---|---|
| 前端 | React 18 + Vite + Zustand + React Router |
| API | FastAPI (异步) |
| Agent 引擎 | LangGraph StateGraph |
| LLM | DeepSeek API (OpenAI 兼容) |
| 数据库 | SQLite (开发) / PostgreSQL (生产) |
| CLI | Typer |

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 20+
- [uv](https://docs.astral.sh/uv/)（Python 包管理器）
- DeepSeek API Key

### 1. 启动后端

```bash
cd backend
uv sync

# 设置 API Key
export DEEPSEEK_API_KEY=your-api-key

# 启动服务
uv run uvicorn app.main:app --reload --port 8000
```

### 2. 启动前端

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173

### 3. 使用 CLI（可选）

```bash
cd cli
uv run python main.py ls              # 列出所有团队
uv run python main.py run 1 --task "写一篇关于 AI 的博客"  # 执行任务
```

### 4. 运行测试

```bash
cd backend
uv run pytest tests/ -v
```

### Docker 部署

```bash
DEEPSEEK_API_KEY=your-key docker compose up -d
```

## 配置

通过环境变量或 `.env` 文件配置：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `DEEPSEEK_API_KEY` | - | DeepSeek API 密钥（必填） |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | API 地址 |
| `DEEPSEEK_MODEL` | `deepseek-chat` | 模型名称 |
| `DATABASE_URL` | `sqlite+aiosqlite:///crewcraft.db` | 数据库连接 |

## 工作流类型

### Sequential（顺序执行）
Agent 按顺序依次执行，前一个的输出作为后一个的上下文。适合流水线任务：研究 → 撰写 → 审核。

### Hierarchical（层级协作）
Leader Agent 自动拆解任务并分配给 Worker 执行。适合需要规划和分工的复杂任务。

### Roundtable（圆桌讨论）
所有 Agent 自由讨论多轮，最后汇总共识。适合需要多角度分析的任务。

## 项目结构

```
CrewCraft/
├── backend/
│   ├── app/
│   │   ├── api/              # REST + WebSocket 路由
│   │   ├── models/           # SQLAlchemy ORM 模型
│   │   ├── schemas/          # Pydantic 请求/响应模型
│   │   ├── engine/           # LangGraph 工作流引擎
│   │   │   ├── compiler.py   # 配置 → Graph 编译器
│   │   │   ├── agent_loop.py # Agent LLM 调用循环
│   │   │   └── workflows/    # 三种工作流实现
│   │   ├── llm/              # DeepSeek API 封装
│   │   └── ws/               # WebSocket 管理
│   ├── pyproject.toml         # 项目配置与依赖
│   └── uv.lock                # 依赖锁文件
├── frontend/
│   └── src/
│       ├── pages/            # 页面组件
│       ├── components/       # 共用 UI 组件
│       ├── api/              # API 调用封装
│       └── store/            # Zustand 状态
├── cli/                      # 命令行工具
├── docker-compose.yml
└── docs/superpowers/         # 设计文档和实现计划
```

## API 概览

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/crews` | 创建团队 |
| GET | `/api/crews` | 团队列表 |
| GET | `/api/crews/{id}` | 团队详情 |
| PUT | `/api/crews/{id}` | 更新团队 |
| DELETE | `/api/crews/{id}` | 删除团队 |
| POST | `/api/crews/{id}/agents` | 添加成员 |
| PUT | `/api/agents/{id}` | 更新成员 |
| DELETE | `/api/agents/{id}` | 删除成员 |
| POST | `/api/crews/{id}/run` | 执行任务 |
| WS | `/api/crews/{id}/stream` | 实时流订阅 |
| GET | `/api/crews/{id}/tasks` | 任务历史 |
| GET | `/api/tasks/{id}` | 任务详情 |

## License

MIT
