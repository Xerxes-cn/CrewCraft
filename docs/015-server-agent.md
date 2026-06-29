# 015: 服务器 Agent 集群设计方案

## 核心思路

每个 Agent 绑定一台物理服务器，负责这台机器上的一切。不再把 Agent 当作"专家角色"（Python 专家、QA 专家），而是当作**服务器的 AI 管理员**。

```
"部署服务到 3 台机器" → Gateway → node-1 agent 执行 + node-2 agent 执行 + node-3 agent 执行 → 汇总结果
```

## 架构图

```mermaid
graph TB
    subgraph Human["👤 用户"]
        CLI["CLI REPL"]
        IM["钉钉/飞书/微信"]
    end

    subgraph Gateway["🏗️ Gateway"]
        REST["REST API"]
        Orch["Orchestrator<br/>按服务器粒度拆任务"]
        HITL["人机交互<br/>confirm/select/input"]
        AM["AgentManager<br/>配置 & 生命周期"]
        WS["WS Server :8765"]
    end

    subgraph Node1["🖥️ 192.168.1.10"]
        A1["Agent<br/>node-1"]
        T1["Tools"]
        P1["进程/容器/文件<br/>本机资源"]
        A1 --> T1
        T1 --> P1
    end

    subgraph Node2["🖥️ 192.168.1.11"]
        A2["Agent<br/>node-2"]
        T2["Tools"]
        P2["进程/容器/文件<br/>本机资源"]
        A2 --> T2
        T2 --> P2
    end

    subgraph Node3["🖥️ 192.168.1.12"]
        A3["Agent<br/>node-3"]
        T3["Tools"]
        P3["进程/容器/文件<br/>本机资源"]
        A3 --> T3
        T3 --> P3
    end

    CLI -->|"REST"| REST
    IM -->|"消息"| REST
    REST --> AM
    REST --> Orch
    Orch --> HITL
    AM --> WS
    Orch -->|"按节点分派任务"| WS
    WS <-->|"WebSocket"| A1
    WS <-->|"WebSocket"| A2
    WS <-->|"WebSocket"| A3

    A1 -.->|"agent 间通信<br/>跨节点协调"| A2
    A2 -.->|"agent 间通信"| A3

    style Gateway fill:#1a1a2e,stroke:#16213e,color:#e0e0e0
    style Node1 fill:#1b4332,stroke:#2d6a4f,color:#e0e0e0
    style Node2 fill:#1b4332,stroke:#2d6a4f,color:#e0e0e0
    style Node3 fill:#1b4332,stroke:#2d6a4f,color:#e0e0e0
    style Human fill:#0f3460,stroke:#16213e,color:#e0e0e0
```

## 完整流转逻辑

### 场景 A：用户下达任务（主动执行）

```mermaid
sequenceDiagram
    participant U as 用户 (IM/CLI)
    participant GW as Gateway
    participant O as Orchestrator
    participant A1 as Agent (node-1)
    participant A2 as Agent (node-2)

    U->>GW: "在三台机器上部署 myapp:v2.0"
    GW->>O: 解析任务
    O->>O: 1. 识别目标节点: node-1, node-2, node-3
    O->>O: 2. 拆分子任务: git pull → docker build → restart
    O->>O: 3. 生成执行计划: 先部署 node-1，验证 → 继续 node-2,3
    O->>A1: "git pull && docker build -t myapp:v2.0 && systemctl restart myapp"
    A1->>A1: 执行命令
    A1-->>GW: OK myapp:v2.0 running on node-1
    O->>U: "node-1 部署成功，继续部署 node-2 和 node-3？"
    U->>GW: "继续"
    O->>A2: "同上操作"
    A2-->>GW: OK node-2 done
    O->>U: "3 台机器部署完成 ✅"
```

### 场景 B：Agent 自主监测 + 处理

```mermaid
sequenceDiagram
    participant A as Agent (node-1)
    participant GW as Gateway
    participant U as 用户 (IM)

    Note over A: 每 N 分钟一次

    A->>A: 采集指标: CPU 32% / RAM 58% / DISK 91% ⚠️

    alt 静态阈值（DISK > 90%）
        A->>A: docker system df → overlay2 占 45G
        A->>A: 判断: stopped 容器 + dangling images 可清理 ~15G
        A->>GW: 发起 confirm 交互
        GW->>U: "node-1 磁盘 91%。可以清理 stopped 容器和未使用镜像，预计释放 15G。执行吗？"
        U->>GW: "y"
        GW->>A: approved
        A->>A: docker system prune -f ✓
        A-->>U: "清理完成，磁盘降至 74%"
    else CPU 突然飙升
        A->>A: top → 发现 node-app CPU 300%
        A->>A: 查日志 → "OOM killed node-app, restarted 3 times in 10min"
        A->>GW: 发起 select 交互
        GW->>U: "node-app 频繁 OOM。选项: 1) 重启服务 2) 增加内存限制 3) 回滚上一版本"
        U->>GW: "2"
        A->>A: 修改 compose 文件 memory: 512M → 1G, docker compose up -d
        A-->>U: "node-app 已重启，内存上限 1G"
    else 一切正常
        A->>A: log: "node-1 healthy (CPU 32% RAM 58% DISK 74%)"
    end
```

### 场景 C：跨节点协调操作

```mermaid
sequenceDiagram
    participant U as 用户
    participant GW as Gateway
    participant A1 as Agent (node-1)
    participant A2 as Agent (node-2)
    participant A3 as Agent (node-3)

    U->>GW: "在所有节点上重启 nginx<br/>每次 2 台，确认健康再继续"

    GW->>A1: restart nginx
    GW->>A2: restart nginx
    A1-->>GW: node-1 nginx OK (PID 12345)
    A2-->>GW: node-2 nginx OK (PID 23456)

    Note over GW: 等待 5s 健康检查

    GW->>A1: curl localhost:80/health
    GW->>A2: curl localhost:80/health
    A1-->>GW: 200 OK
    A2-->>GW: 200 OK

    GW->>A3: restart nginx
    A3-->>GW: node-3 nginx OK (PID 34567)

    GW->>U: "3 台 nginx 全部重启完成 ✅"
```

## Agent 系统提示词设计

```markdown
You are the AI administrator of server {hostname} ({ip}).

## Your responsibilities
- Monitor system health (CPU, memory, disk, processes, containers)
- Execute user tasks on this server
- Diagnose and fix issues autonomously when safe
- Escalate to human when operation is dangerous or ambiguous

## Server context
- Hostname: {hostname}
- IP: {ip}
- OS: {os}
- Containers: {containers}
- Services: {services}
- Important paths: {paths}

## Rules
1. read operations (df, ps, top, docker ps, cat configs) → auto-approve
2. safe operations (restart service, clean temp files) → execute, log, notify
3. dangerous operations (rm, docker prune, modify system config) → confirm with human
4. NEVER modify /etc/passwd, /etc/shadow, /etc/ssh/sshd_config
5. ALWAYS log your actions to data/sessions/{agent_name}/actions.log
6. If unsure, escalate rather than guess
```

## 新增工具

| 工具 | 权限 | 说明 |
|------|------|------|
| `system_info` | read | 采集 CPU/内存/磁盘/负载 |
| `process_list` | read | 列出进程（top/ps） |
| `process_kill` | dangerous | 终止进程 |
| `service_ctl` | write | 启动/停止/重启 systemd 服务 |
| `container_ctl` | write | 管理 Docker 容器 |
| `container_clean` | dangerous | 清理 stopped 容器/未用镜像 |
| `log_read` | read | 读取系统日志/服务日志 |
| `deploy_app` | write | git pull + docker build + restart |
| `file_edit` | write | 编辑配置文件 |
| `health_check` | read | 检查服务健康状态 |

## 监控循环

```python
# 每个 Agent 独立运行的监控循环
async def monitor_loop(agent_name: str, interval: int = 300):
    while True:
        try:
            metrics = collect_system_metrics()
            if is_critical(metrics):
                # 磁盘 > 95% / 内存 > 98% → 立即告警
                await escalate_to_human(metrics)
            elif needs_attention(metrics):
                # 磁盘 80-95% / 异常进程 → LLM 判断
                action = await llm_check(metrics)
                if action.risk == "safe":
                    await execute(action)
                    await log_and_notify(f"自动处理: {action}")
                else:
                    await request_confirmation(action)
            else:
                logger.info(f"{agent_name}: all good")
        except Exception:
            logger.exception("monitor loop error")

        await asyncio.sleep(interval)
```

## 跟现有架构的改动点

| 模块 | 现状 | 需要改 |
|------|------|--------|
| Agent system prompt | "你是 XX 专家" | "你是 XX 服务器的管理员" |
| Orchestrator | 按专家角色拆任务 | 按服务器粒度拆任务 |
| 工具注册表 | 14 个通用工具 | + 6 个服务器管理工具 |
| 人机交互 | confirm/select/input | 不用改 |
| Agent 间通信 | agent_message | 保留，用于跨节点协调 |
| 心跳/生命周期 | 正常 | 不用改 |
| IM Channel | 正常 | 不用改 |

## 从单台到集群的渐进路径

```
Phase 1: 单机 agent（本机或 Docker）
  └── 在一台机器上跑通: 采集 → 判断 → 执行 → 通知

Phase 2: 单机 agent + 真实任务
  └── 部署服务、查日志、改配置、重启

Phase 3: 双机 agent
  └── "在两台机器上部署" → 验证跨节点编排

Phase 4: N 机集群
  └── 批量操作、健康汇总、统一告警
```
