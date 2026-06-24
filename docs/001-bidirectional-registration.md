# 001: Bidirectional Agent Registration

## 概述

将 Agent 注册从单向（Agent → Gateway）改为双向握手。Gateway 验证 Agent 身份后下发完整配置。

## 动机

- 之前：Agent 从本地 `data/agents/{name}.json` 加载配置，Gateway 不验证
- 问题：配置分散在 Agent 和 Gateway 两端，不一致风险
- 目标：Gateway 为单一配置源，Agent 启动时不带配置

## 设计

```
Agent                          Gateway
  │                               │
  │──── register {name} ────────→│  验证 config 存在
  │                               │  拒绝未注册 agent
  │←─── registered + config ────│  下发完整 config
  │                               │
  │ 开始接受任务                   │
```

### 变更点

- **Gateway**: `ws_manager.handle_agent()` 收到 register 后查 agent_manager 验证配置，回复 `registered` + `config.to_dict()`
- **Agent**: `server.agent_loop()` 发 register 后等待 `registered` 响应，用 Gateway 下发的 config 初始化，移除 `load_agent_config()` 本地加载

## 改动文件

- `app/gateway/manager/ws_manager.py`
- `app/agent/server.py`
