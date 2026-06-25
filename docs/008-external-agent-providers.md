# 008: 外部 Agent 接入

## 概述

支持接入 Claude Code、Codex、OpenClaw 等外部 CLI Agent 作为 CrewCraft 的一等公民 Agent。通过抽象 `AgentProvider` 接口，Gateway 可以像管理内置 Agent 一样管理这些外部 Agent。

## 设计

### AgentProvider 抽象

```python
class AgentProvider(ABC):
    """外部 Agent 的适配器接口。"""

    @abstractmethod
    async def start(self, config: AgentConfig) -> bool: ...
    @abstractmethod
    async def stop(self) -> None: ...
    @abstractmethod
    async def send_task(self, content: str, session_id: str) -> dict: ...
    @abstractmethod
    def is_running(self) -> bool: ...
```

### 内置 Provider

| Provider | Agent | 通信方式 |
|----------|-------|----------|
| `SubprocessProvider` | 内置 deepagents Agent | 子进程 + WebSocket（现有） |
| `DockerProvider` | Docker 容器 Agent | Docker SDK（现有） |
| `ClaudeCodeProvider` | Claude Code CLI | 子进程 + stdin/stdout/文件 |
| `CodexProvider` | Codex CLI | 子进程 + stdin/stdout/文件 |
| `OpenClawProvider` | OpenClaw CLI | 子进程 + stdin/stdout/文件 |

### Provider 选择逻辑

```
AgentManager.start_agent(name)
  ├─ config.provider == "builtin"   → SubprocessProvider or DockerProvider
  ├─ config.provider == "claude"    → ClaudeCodeProvider
  ├─ config.provider == "codex"     → CodexProvider
  └─ config.provider == "openclaw"  → OpenClawProvider
```

### 数据流（以 Claude Code 为例）

```
Gateway                           Claude Code 进程
  │                                    │
  │── claude --print ─────────────────→│  启动（无交互模式）
  │   --append-system-prompt "..."     │
  │                                    │
  │── 写任务到 /tmp/task.md ──────────→│  通过文件传递大段 prompt
  │── claude --prompt "见 /tmp/task.md"│
  │                                    │
  │←── stdout: 结果 ──────────────────│  读输出
  │←── 写结果到 sessions/{name}/       │  持久化
  │                                    │
  │── SIGTERM ────────────────────────→│  空闲超时/任务完成
```

### Claude Code Provider 实现

```python
class ClaudeCodeProvider(AgentProvider):
    async def start(self, config):
        # 1. 将 system_prompt 写入项目目录的 CLAUDE.md
        # 2. 启动 claude --print --dangerously-skip-permissions
        #    --append-system-prompt 注入任务上下文
        # 3. 通过文件传递任务内容
        # 4. 从 stdout 读取结果

    async def send_task(self, content, session_id):
        # 写 content 到临时文件
        # 通过 stdin 发送 /prompt 或文件路径
        # 等待输出完成（读取 stdout 直到分隔符）
        # 解析输出，提取结果
```

### CLI 扩展

```bash
# 创建 Claude Code agent
crewcraft agent create --name coder --provider claude \
  --desc "写代码和修 bug"

# 创建 Codex agent
crewcraft agent create --name reviewer --provider codex \
  --desc "代码审查"

# 查看支持的 provider
crewcraft provider list
```

### 配置

```env
# .env
CREWCRAFT_AGENT_PROVIDERS=builtin,claude,codex,openclaw

# Claude Code 路径
CREWCRAFT_CLAUDE_PATH=claude

# Codex 路径
CREWCRAFT_CODEX_PATH=codex

# OpenClaw 路径  
CREWCRAFT_OPENCLAW_PATH=openclaw
```

### 目录结构

```
app/agent/
├── providers/
│   ├── __init__.py          # Provider 注册表
│   ├── base.py              # AgentProvider 抽象基类
│   ├── subprocess.py        # SubprocessProvider (现有逻辑迁移)
│   ├── docker.py            # DockerProvider (现有逻辑迁移)
│   ├── claude.py            # ClaudeCodeProvider
│   ├── codex.py             # CodexProvider
│   └── openclaw.py          # OpenClawProvider
├── server.py                # Agent 服务 (保留，供 builtin 使用)
└── tools/
```

### 通信协议对比

| 维度 | 内置 Agent | Claude Code | Codex | OpenClaw |
|------|-----------|-------------|-------|----------|
| 启动方式 | subprocess | subprocess | subprocess | subprocess |
| 通信 | WebSocket | stdin/stdout/文件 | stdin/stdout/文件 | stdin/stdout/文件 |
| 流式 | WS 推送 | stdout 流 | stdout 流 | stdout 流 |
| 结果持久化 | 内置 | Provider 负责写入 sessions/ | 同 | 同 |
| 超时控制 | 心跳 | 进程监控 | 进程监控 | 进程监控 |
| 并发任务 | 串行 | 串行（单进程） | 串行 | 串行 |

### 实施计划

1. **Phase 1**：重构现有 `agent_manager.py`，提取 `SubprocessProvider` 和 `DockerProvider`
2. **Phase 2**：实现 `ClaudeCodeProvider`
3. **Phase 3**：实现 `CodexProvider` 和 `OpenClawProvider`
4. **Phase 4**：CLI 命令和配置完善
