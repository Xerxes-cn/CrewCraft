# 002: Tools System

## 概述

为 Agent 实现可扩展的工具系统，提供 12 个常用工具，支持工具注册与发现。

## 设计

### 包结构

```
app/agent/tools/
├── __init__.py      # 导入所有模块触发注册，重新导出
├── registry.py      # Tool / ToolRegistry / @register / sync wrappers
├── web.py           # web_search, web_fetch
├── system.py        # shell_exec, file_ops
└── utility.py       # time_now, calculator, random_number,
                     # text_stats, json_tool, base64, hash, uuid_gen
```

### 工具注册

每个工具通过 `@register(name, description, params)` 装饰器注册到全局 `registry` 单例。Async 工具通过 `_sync_wrapper` 转为同步供 deepagents 调用。

### CLI & API

- `crewcraft tool list` — 查看所有可用工具
- `GET /api/tools` — API 端点

## 工具列表

| 工具 | 分类 | 说明 |
|------|------|------|
| web_search | web | DuckDuckGo 搜索 |
| web_fetch | web | HTTP 请求 |
| shell_exec | system | Shell 命令 |
| file_ops | system | 文件读写 |
| time_now | utility | 当前时间 |
| calculator | utility | 数学计算 |
| random_number | utility | 随机数 |
| text_stats | utility | 文本统计 |
| json_tool | utility | JSON 操作 |
| base64 | utility | 编解码 |
| hash | utility | 哈希 |
| uuid_gen | utility | UUID 生成 |

## 改动文件

- `app/agent/tools/` (package)
- `app/agent/server.py` — `_build_tools()` 接入
- `app/gateway/api/tools.py` — API
- `app/cli/main.py` — CLI 命令
