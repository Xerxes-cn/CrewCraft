# 006: Docker Agent Deployment

## 概述

支持以 Docker 容器方式运行 Agent，与 Gateway 解耦。Gateway 通过 Docker CLI 管理 Agent 容器的生命周期。

## 设计

### 部署模式

通过 `.env` 配置切换：

```env
CREWCRAFT_AGENT_DEPLOY_MODE=docker   # docker | subprocess (default)
```

### 架构

```
┌─────────────────────────────────────────────────────┐
│                    Host                              │
│  ┌──────────┐   docker run    ┌──────────────────┐  │
│  │ Gateway  │ ──────────────→ │ Agent Container  │  │
│  │ (host)   │                 │ :9001 → host:9001│  │
│  └──────────┘                 │ Vol: data/       │  │
│       │                       └──────────────────┘  │
│       │ WebSocket (host:8765)                        │
│       └──────────────────────→ Agent registers       │
└─────────────────────────────────────────────────────┘
```

### Gateway 变更

- `agent_manager.py`: 添加 `deploy_mode`，Docker 模式下用 Python Docker SDK 管理容器
- 容器名: `crewcraft-agent-{name}`
- 端口映射: `{port}:{port}`
- 数据卷: `{data_dir}:/data`
- 状态管理: 通过 SDK 获取容器状态、日志

### 依赖

- 新增 `docker>=7.0` pip 包 (Python Docker SDK)

### Agent Docker 镜像

`Dockerfile.agent`:
- 基础镜像: `python:3.13-slim`
- 安装 crewcraft + 依赖
- 入口: `python -m app.agent.server`
- 通过环境变量配置: `CREWCRAFT_AGENT_NAME`, `CREWCRAFT_AGENT_PORT`, `CREWCRAFT_GATEWAY_WS`

### 部署方式

**方式一：docker compose（推荐）**

```bash
docker build -f Dockerfile.agent -t crewcraft-agent .
docker compose up -d
crewcraft  # 交互
```

**方式二：手动部署**

```bash
docker build -t crewcraft-gateway .
docker build -f Dockerfile.agent -t crewcraft-agent .
echo "CREWCRAFT_AGENT_DEPLOY_MODE=docker" >> .env
crewcraft gateway start  # 或 docker run crewcraft-gateway
```

### 文件

| 文件 | 用途 |
|------|------|
| `Dockerfile` | Gateway 镜像 |
| `Dockerfile.agent` | Agent 运行时镜像 |
| `docker-compose.yml` | 一键部署 |

## 改动文件

- `Dockerfile.agent` — 新增
- `app/gateway/manager/agent_manager.py` — Docker 模式
- `app/config.py` — 新增 deploy_mode 配置
- `.env.example` — 新增配置项
