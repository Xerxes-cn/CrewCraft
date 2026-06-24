# 005: Interactive REPL

## 概述

用交互式 REPL 替代复杂的多级 Typer 子命令。默认 `crewcraft` 进入交互模式，`crewcraft gateway start` 等命令作为独立 CLI 命令保留。

## 设计

### 两个入口

```bash
# 交互模式（默认）
crewcraft

# 独立命令（脚本/启动用）
crewcraft gateway start
crewcraft agent create --name X --model X --desc "..."
```

两者不冲突：`crewcraft` 无参进 REPL，有子命令走 Typer 路由。

### REPL 斜杠命令

| 命令 | 说明 |
|------|------|
| `/agent create/list/inspect/delete/generate-prompt` | Agent 管理 |
| `/task run/status/list` | 任务管理 |
| `/session list/show` | 会话查看 |
| `/tool list` | 工具列表 |
| `/help` | 帮助 |
| `/exit` | 退出 |

直接输入文字（无 `/` 前缀）自动作为任务发给 Orchestrator。

### REPL 实现

- `app/cli/repl.py` — REPL 循环 + 命令路由 + HTTP 客户端
- 参数解析：`--key value` / `--flag` 风格
- 轮询任务状态直到完成

### 交互流程

```bash
# 终端 1: 启动服务
crewcraft gateway start

# 终端 2: 交互
crewcraft
> /agent create researcher --desc "擅长搜索"
> 帮我研究 Python 3.13 新特性   # 自动编排
```

## 改动文件

- `app/cli/repl.py` — 新增
- `app/main.py` — 无参时进入 REPL
