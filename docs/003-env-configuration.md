# 003: Environment Configuration

## 概述

提取所有硬编码配置项到 `.env` 文件，由 `app/config.py` 集中管理。值在导入时一次性缓存，避免重复 `os.getenv` 调用。

## 设计

### 配置优先级

```
.env 文件 > 环境变量 > 默认值
```

### Config 单例

```python
# app/config.py
class Config:
    def __init__(self):
        self._load_dotenv()     # 加载 .env
        self._cache_values()    # 一次性读取所有 env
        self._print_summary()   # 启动时打印配置摘要
```

属性为普通实例变量（非 `@property`），O(1) 访问。

### 可配置项

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| CREWCRAFT_DATA_DIR | data | 数据目录 |
| CREWCRAFT_GATEWAY_HOST | 127.0.0.1 | REST 地址 |
| CREWCRAFT_GATEWAY_PORT | 8000 | REST 端口 |
| CREWCRAFT_WS_HOST | 127.0.0.1 | WS 地址 |
| CREWCRAFT_WS_PORT | 8765 | WS 端口 |
| CREWCRAFT_AGENT_PORT_START | 9001 | Agent 起始端口 |
| CREWCRAFT_AGENT_IDLE_TIMEOUT | 300 | 空闲超时 |
| CREWCRAFT_AGENT_HEARTBEAT_INTERVAL | 15 | 心跳间隔 |
| CREWCRAFT_LOG_LEVEL | INFO | 日志级别 |

### 使用

```bash
cp .env.example .env
# 编辑 .env 自定义配置
```

## 改动文件

- `app/config.py` — 新增
- `.env.example` — 新增
- `app/gateway/main.py`、`ws_manager.py`、`agent_manager.py` — 替换硬编码
- `app/agent/server.py` — 替换硬编码
- `app/cli/main.py` — 替换硬编码
- `pyproject.toml` — 添加 python-dotenv 依赖
- `.gitignore` — 忽略 .env
