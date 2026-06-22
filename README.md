# CrewCraft

**CrewCraft — 多智能体协作开发平台，轻松构建 AI 团队。**

启动即有一个默认团队，只需创建 Agent 即可开始协作。支持 Roundtable（圆桌讨论）、Sequential（顺序执行）、Hierarchical（层级协作）三种工作流。

## 特性

- **纯 CLI 体验** — 所有操作通过命令行完成，适合脚本集成和自动化
- **零配置启动** — 启动即有一个默认团队，无需创建/管理团队
- **Agent 管理** — 添加、更新、删除 Agent，自定义角色和提示词
- **工具调用** — Agent 可调用文件读写、命令执行等工具
- **技能预设** — 可配置技能组合，一键赋予 Agent 专业能力
- **DeepSeek 驱动** — 默认使用 DeepSeek API，支持 OpenAI 兼容的 LLM

## 架构

```
CLI (Typer) → FastAPI REST → 引擎运行时 (CrewAI + LangGraph) → LLM API
```

| 层 | 技术 |
|---|---|
| CLI | Python + Typer + httpx |
| API | FastAPI (异步) |
| Agent 引擎 | CrewAI + LangGraph StateGraph |
| LLM | DeepSeek API (OpenAI 兼容) |
| 数据库 | SQLite (开发) / PostgreSQL (生产) |

## 快速开始

### 环境要求

- Python 3.10+
- [uv](https://docs.astral.sh/uv/)（Python 包管理器）
- DeepSeek API Key

### 1. 安装

```bash
uv sync
```

### 2. 启动服务

```bash
export DEEPSEEK_API_KEY=your-api-key
uv run uvicorn app.main:app --port 8000
```

### 3. 使用 CLI

```bash
# 添加 Agent
uv run python main.py agent add -n "研究员" -r "研究专家" -p "你是一个研究专家，擅长搜集和分析信息。"
uv run python main.py agent add -n "作者" -r "内容作者" -p "你是一个内容作者，擅长撰写清晰易读的文章。"
uv run python main.py agent add -n "审核" -r "审核编辑" -p "你是一个审核编辑，擅长发现文章中的问题。"

# 列出所有 Agent
uv run python main.py agent ls

# 执行任务
uv run python main.py run --task "写一篇关于 AI 的博客"

# 查看任务历史
uv run python main.py tasks

# 查看任务详情
uv run python main.py task 1
```

## CLI 命令参考

### Agent 管理

| 命令 | 说明 |
|------|------|
| `crewcraft agent add -n <名称> -r <角色> [-p 提示词] [-o 顺序] [-t 工具]` | 添加 Agent |
| `crewcraft agent ls` | 列出所有 Agent |
| `crewcraft agent update <AgentID> [--name] [--role] [--prompt] [--order] [--tools]` | 更新 Agent |
| `crewcraft agent remove <AgentID> [-f]` | 移除 Agent |

### 发现

| 命令 | 说明 |
|------|------|
| `crewcraft tools` | 列出可用工具 |
| `crewcraft skills` | 列出技能预设 |

### 任务

| 命令 | 说明 |
|------|------|
| `crewcraft run --task <内容>` | 执行任务 |
| `crewcraft tasks` | 任务历史 |
| `crewcraft task <任务ID>` | 任务详情 |

## 配置

通过环境变量或 `.env` 文件配置：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `DEEPSEEK_API_KEY` | - | DeepSeek API 密钥（必填） |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | API 地址 |
| `DEEPSEEK_MODEL` | `deepseek-chat` | 模型名称 |
| `DATABASE_URL` | `sqlite+aiosqlite:///crewcraft.db` | 数据库连接 |

## 运行测试

```bash
uv run pytest tests/ -v
```

## Docker 部署

```bash
DEEPSEEK_API_KEY=your-key docker compose up -d
```

## 项目结构

```
CrewCraft/
├── app/
│   ├── api/              # REST 路由
│   ├── models/           # SQLAlchemy ORM 模型
│   ├── schemas/          # Pydantic 请求/响应模型
│   ├── engine/           # 工作流引擎
│   │   ├── builder.py    # 配置 → Crew 构建器
│   │   ├── runner.py     # CrewAI 执行器
│   │   ├── agent_loop.py # Agent LLM 调用循环
│   │   ├── tools.py      # 工具系统
│   │   ├── skills.py     # 技能加载器
│   │   └── workflows/    # 工作流实现
│   ├── llm/              # LLM 封装
│   └── services/         # 工作区等服务
├── skills/               # 技能预设 Markdown 文件
├── tests/                # 测试
├── main.py               # CLI 入口
├── client.py             # API 客户端
├── pyproject.toml
├── uv.lock
├── Dockerfile
├── docker-compose.yml
└── docs/
```

## License

MIT
