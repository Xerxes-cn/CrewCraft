# 004: Orchestrator & Auto Prompt Generation

## 概述

1. 内置 Orchestrator Agent — 自动分析任务并分派给最合适的子 Agent
2. Prompt 自动生成 — 用户只需描述 Agent 用途，系统调 LLM 生成 system_prompt

## 设计

### Orchestrator

```
用户发布任务 → Orchestrator
  ├─ 读取各 Agent 的 description + prompt 了解能力
  ├─ 调 LLM 生成分派计划 (JSON)
  ├─ 逐个分派子任务到对应 Agent
  └─ (后续) 收集结果、验收、汇总返回
```

- Gateway 启动时自动初始化 `_orchestrator`
- `POST /api/tasks` 不传 `agent_name` 时走 orchestrator
- CLI: `crewcraft task run "..."` 不加 `--agent` 即自动编排

### Prompt 生成

```bash
# 用户只需描述
crewcraft agent create --name researcher --desc "擅长搜索和整理技术资料"

# 系统自动:
# 1. 调 LLM 生成 system_prompt
# 2. 保存到 data/agents/researcher.prompt.md (用户可修改)
# 3. CLI: crewcraft agent generate-prompt <name> --desc "..." → 重新生成
```

### Agent 配置简化

- 移除 `tools` 字段 — 所有 Agent 默认可用全部内置工具
- 新增 `description` 字段
- `system_prompt` 独立保存在 `.prompt.md` 文件中

## 改动文件

- `app/agent/prompt_generator.py` — 新增
- `app/gateway/orchestrator.py` — 新增
- `app/gateway/manager/agent_manager.py` — AgentConfig 重构
- `app/gateway/api/agents.py` — generate-prompt 端点
- `app/gateway/api/tasks.py` — agent_name 可选
- `app/cli/main.py` — --desc 替代 --prompt/--tools
