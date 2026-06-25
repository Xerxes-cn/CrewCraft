# 013: 测试套件

## 概述

为 CrewCraft 核心模块编写单元测试和集成测试，确保代码质量和回归防护。

## 设计

### 测试结构

```
tests/
├── __init__.py
├── conftest.py                  # 共享 fixtures
├── test_config.py               # Config 模块
├── test_agent_manager.py        # AgentManager CRUD + Provider
├── test_ws_manager.py           # WebSocket 管理器
├── test_orchestrator.py         # Orchestrator 编排
├── test_tools.py                # 14 个工具
├── test_tool_registry.py        # 工具注册表 + 权限
├── test_channels.py             # Channel 系统
├── test_bus.py                  # MsgManager 消息总线
├── test_prompt_generator.py     # Prompt 生成
├── test_approval_queue.py       # 审批队列
└── test_providers.py            # Agent Providers
```

### 覆盖目标

| 模块 | 测试数 | 覆盖 |
|------|--------|------|
| Config | 5 | 默认值、env 覆盖、缓存 |
| AgentManager | 8 | CRUD、端口分配、迁移 |
| Tools Registry | 5 | 注册、查找、schema 生成 |
| Tools (14) | 10 | 核心功能（跳过网络） |
| MsgManager | 4 | 发布、消费、路由 |
| Channels | 3 | CLI、加载、启动 |
| Approval Queue | 4 | 添加、查询、批准、拒绝 |
| Orchestrator | 3 | 计划、分派 |
| Providers | 3 | 注册、查找 |
| Prompt Gen | 2 | 生成、保存、加载 |

### 运行

```bash
uv sync --dev
uv run pytest -v --tb=short
```

### 变更范围

- `tests/` 目录 — 新增
- `pytest.ini` 或 `pyproject.toml` — pytest 配置
