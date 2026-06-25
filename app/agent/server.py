"""Agent 服务进程。

每个 Agent 作为独立的子进程运行：
1. 通过 WebSocket 连接到网关
2. 使用其 Agent 名称进行注册
3. 接收任务并通过 deepagents 执行
4. 将进度更新和结果发送回网关
5. 处理心跳和空闲关闭
6. 将会话历史保存到 sessions/{name}/
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone

import websockets

from app.config import config

logging.basicConfig(
    level=config.log_level,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── 从环境变量读取配置 ───────────────────────────────────────────────────

AGENT_NAME = os.getenv("CREWCRAFT_AGENT_NAME", "default")
AGENT_PORT = int(os.getenv("CREWCRAFT_AGENT_PORT", "9001"))

TOOL_RESULT_TRUNCATE = 100  # sessions.json 中保留的字符数

SESSION_DIR = config.data_dir / "sessions" / AGENT_NAME


# ── 会话持久化 ──────────────────────────────────────────────────────────


def save_message(session_id: str, role: str, content: str, tool_name: str = ""):
    """将一条消息追加到 sessions.json 文件。"""
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    session_file = SESSION_DIR / "sessions.json"

    # 加载已有数据
    messages = []
    if session_file.exists():
        try:
            messages = json.loads(session_file.read_text())
        except json.JSONDecodeError:
            messages = []

    msg = {
        "session_id": session_id,
        "role": role,
        "content": content,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if tool_name:
        msg["tool_name"] = tool_name

    messages.append(msg)
    session_file.write_text(json.dumps(messages, indent=2, ensure_ascii=False))


def save_tool_log(session_id: str, tool_name: str, input_data: dict, output_data: str):
    """将工具调用详情保存到 tool_logs.json。"""
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    tool_file = SESSION_DIR / "tool_logs.json"

    logs = []
    if tool_file.exists():
        try:
            logs = json.loads(tool_file.read_text())
        except json.JSONDecodeError:
            logs = []

    logs.append({
        "session_id": session_id,
        "tool_name": tool_name,
        "input": input_data,
        "output": output_data,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    tool_file.write_text(json.dumps(logs, indent=2, ensure_ascii=False))


# ── 审批 ────────────────────────────────────────────────────────────

async def _request_approval(tool_name: str, action: str, permission: str, session_id: str):
    """向 Gateway 发送审批请求并等待结果。"""
    import httpx
    try:
        from app.config import config as app_config
        url = f"http://{app_config.gateway_host}:{app_config.gateway_port}/api/approvals/pending"
        # 先检查是否已有待审批的
        resp = httpx.get(url, timeout=3)
        already = [p for p in resp.json() if p["session_id"] == session_id
                   and p["tool"] == tool_name] if resp.status_code == 200 else []
        if already:
            # 已有相同审批在队列中，跳过
            logger.info(f"审批已在队列中: {tool_name}")
            return
    except Exception:
        pass

    # 向 Gateway 提交审批
    try:
        from app.config import config as app_config
        agent_name = os.getenv("CREWCRAFT_AGENT_NAME", "unknown")
        httpx.post(
            f"http://{app_config.gateway_host}:{app_config.gateway_port}/api/approvals/submit",
            json={
                "agent": agent_name,
                "session_id": session_id,
                "tool": tool_name,
                "action": action,
                "permission": permission,
            },
            timeout=3,
        )
        logger.info(f"已提交审批: {tool_name} ({permission})")
    except Exception as e:
        logger.warning(f"提交审批失败: {e}")


# ── Agent 运行器（封装 deepagents）───────────────────────────────────────

async def run_task(session_id: str, content: str, ws, config: dict) -> str:
    """使用 deepagents 运行任务并通过 WebSocket 流式传输结果。

    参数：
        session_id: 唯一的会话标识符。
        content: 用户的消息内容。
        ws: 与网关的 WebSocket 连接。
        config: 从网关接收的 Agent 配置（model, system_prompt, tools）。
    """
    model = config.get("model", "openai:gpt-4o")
    system_prompt = config.get("system_prompt", "")
    tools_list = config.get("tools", [])

    # 加载公共 + 私有 Skill，注入 system_prompt
    from app.agent.skills import inject_skills_to_prompt
    system_prompt = inject_skills_to_prompt(system_prompt, config.get("name"), None)

    # 连接 MCP Server，合并 MCP tools
    from app.agent.mcp import mcp_client
    try:
        await mcp_client.connect_all(config.get("name", ""))
        # 将 MCP tools 注册为工具 callables
        for name, info in mcp_client.tools.items():
            logger.info(f"MCP tool available: {name}")
    except Exception as e:
        logger.warning(f"MCP 连接失败: {e}")

    # 保存用户消息
    save_message(session_id, "user", content)

    try:
        # 尝试使用 deepagents
        from deepagents import create_deep_agent

        agent = create_deep_agent(
            model=model,
            system_prompt=system_prompt,
            tools=_build_tools(tools_list),
        )

        # 流式执行
        full_response = ""
        async for event in agent.astream_events(
            {"messages": [{"role": "user", "content": content}]},
            version="v2",
        ):
            kind = event.get("event")

            # 收集 assistant 消息
            if kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    full_response += chunk.content

            # 工具执行前 — 权限检查
            elif kind == "on_tool_start":
                tool_name = event.get("name", "unknown")
                tool_input = event.get("data", {}).get("input", {})
                # 查工具权限
                from .tools import registry
                tool = registry.get(tool_name)
                if tool and tool.permission in ("write", "dangerous"):
                    action = str(tool_input.get(list(tool_input.keys())[0], "")) if tool_input else str(tool_input)
                    await _request_approval(tool_name, action, tool.permission, session_id)

            # 记录工具调用
            elif kind == "on_tool_end":
                tool_input = event.get("data", {}).get("input", {})
                tool_output = str(event.get("data", {}).get("output", ""))
                tool_name = event.get("name", "unknown")

                # 保存截断版本到 sessions
                truncated = tool_output[:TOOL_RESULT_TRUNCATE]
                if len(tool_output) > TOOL_RESULT_TRUNCATE:
                    truncated += "..."
                save_message(session_id, "tool", truncated, tool_name=tool_name)

                # 保存完整版本到 tool_logs
                save_tool_log(session_id, tool_name, tool_input, tool_output)

                # 发送进度更新
                await ws.send(json.dumps({
                    "type": "task_update",
                    "task_id": _current_task_id,
                    "session_id": session_id,
                    "status": "running",
                    "progress": f"Tool {tool_name} completed",
                }))

        # 保存 assistant 消息
        if full_response:
            save_message(session_id, "assistant", full_response)

        return full_response

    except ImportError:
        logger.warning("deepagents not installed, using fallback")
        return await _fallback_run(session_id, content, model, system_prompt, ws, config)


def _build_tools(tools_list: list[str]) -> list:
    """根据配置名称使用工具注册表构建工具列表。"""
    from .tools import get_tool_callable, registry

    if not tools_list:
        return []

    # 验证所有请求的工具是否存在
    available = set(registry.list_names())
    tools = []
    for name in tools_list:
        if name not in available:
            logger.warning(f"Tool '{name}' not found. Available: {', '.join(sorted(available))}")
            continue
        fn = get_tool_callable(name)
        if fn:
            tools.append(fn)
            logger.info(f"Tool '{name}' loaded")

    return tools


# ── Agent 间通信 ────────────────────────────────────────────────────

_current_task_id = ""
_current_ws = None
_current_session_id = ""


def _handle_agent_message(msg: dict):
    """处理来自其他 Agent 的点对点消息。"""
    from_agent = msg.get("from", "unknown")
    content = msg.get("content", "")
    logger.info(f"Agent 消息 from={from_agent}: {content[:100]}")


def _handle_agent_broadcast(msg: dict):
    """处理来自其他 Agent 的广播。"""
    from_agent = msg.get("from", "unknown")
    content = msg.get("content", "")
    logger.info(f"Agent 广播 from={from_agent}: {content[:100]}")


async def send_to_agent(to_agent: str, content: str, context: dict = None) -> bool:
    """向另一个 Agent 发送消息。返回是否成功。"""
    if _current_ws is None:
        logger.warning("未连接，无法发送 Agent 间消息")
        return False
    try:
        await _current_ws.send(json.dumps({
            "type": "agent_message",
            "to": to_agent,
            "session_id": _current_session_id,
            "content": content,
            "context": context or {},
        }))
        return True
    except Exception as e:
        logger.error(f"发送 Agent 消息失败: {e}")
        return False


async def _fallback_run(
    session_id: str, content: str, model: str, system_prompt: str, ws, config: dict
) -> str:
    """deepagents 不可用时的回退方案：简单的 echo/reflection。"""
    tools = config.get("tools", [])
    response = f"[Fallback mode] Agent {AGENT_NAME} received: {content}"
    if tools:
        response += f"\n[Available tools: {', '.join(tools)}]"
    save_message(session_id, "assistant", response)
    return response


# ── WebSocket 客户端 ────────────────────────────────────────────────────

async def agent_loop():
    """Agent 主循环：连接网关，双向注册，处理消息。"""
    global _current_task_id

    # Agent 以空配置启动 — 网关将在注册时提供配置
    agent_config: dict = {}
    idle_timeout = config.agent_idle_timeout
    last_task_time = asyncio.get_event_loop().time()

    gateway_ws_url = os.getenv("CREWCRAFT_GATEWAY_WS", config.ws_url)
    logger.info(f"Agent {AGENT_NAME} connecting to gateway at {gateway_ws_url}")

    async for ws in websockets.connect(gateway_ws_url):
        try:
            # ── 阶段 1: 双向注册 ──────────────────────────────────────
            await ws.send(json.dumps({
                "type": "register",
                "name": AGENT_NAME,
            }))
            logger.info(f"Agent {AGENT_NAME} sent registration request")

            # 等待网关确认并发送配置
            raw = await asyncio.wait_for(ws.recv(), timeout=10)
            msg = json.loads(raw)

            if msg.get("type") == "error":
                logger.error(f"Registration rejected: {msg.get('message')}")
                return  # 退出 — Agent 不在注册表中

            if msg.get("type") != "registered":
                logger.error(f"Expected 'registered', got '{msg.get('type')}'")
                return

            agent_config = msg.get("config", {})
            idle_timeout = agent_config.get("idle_timeout", config.agent_idle_timeout)
            logger.info(f"Agent {AGENT_NAME} registered (model={agent_config.get('model')}, "
                        f"tools={agent_config.get('tools')}, idle_timeout={idle_timeout}s)")

            # ── 阶段 2: 主消息循环 ───────────────────────────────────
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                msg_type = msg.get("type")

                if msg_type == "ping":
                    await ws.send(json.dumps({"type": "pong"}))

                elif msg_type == "agent_message":
                    _handle_agent_message(msg)

                elif msg_type == "agent_broadcast":
                    _handle_agent_broadcast(msg)

                elif msg_type == "supervisor":
                    logger.warning(f"监督者介入: {msg.get('reason')}")

                elif msg_type == "task":
                    _current_task_id = msg.get("task_id", "")
                    _current_session_id = msg.get("session_id", str(uuid.uuid4()))
                    _current_ws = ws
                    session_id = _current_session_id
                    content = msg.get("content", "")

                    logger.info(f"Received task {_current_task_id}")
                    last_task_time = asyncio.get_event_loop().time()

                    # 发送运行中状态
                    await ws.send(json.dumps({
                        "type": "task_update",
                        "task_id": _current_task_id,
                        "session_id": session_id,
                        "status": "running",
                    }))

                    try:
                        result = await run_task(session_id, content, ws, agent_config)

                        # 发送完成状态
                        await ws.send(json.dumps({
                            "type": "task_update",
                            "task_id": _current_task_id,
                            "session_id": session_id,
                            "status": "completed",
                            "result": result,
                        }))
                    except Exception as e:
                        logger.exception(f"Task {_current_task_id} failed")
                        await ws.send(json.dumps({
                            "type": "task_update",
                            "task_id": _current_task_id,
                            "session_id": session_id,
                            "status": "failed",
                            "error": str(e),
                        }))

                    _current_task_id = ""

                elif msg_type == "shutdown":
                    logger.info("Gateway requested shutdown")
                    return

                # 空闲检查
                elapsed = asyncio.get_event_loop().time() - last_task_time
                if _current_task_id == "" and elapsed > idle_timeout:
                    logger.info(f"Idle timeout ({idle_timeout}s), shutting down")
                    await ws.send(json.dumps({
                        "type": "idle_shutdown",
                        "name": AGENT_NAME,
                    }))
                    return

        except websockets.exceptions.ConnectionClosed:
            logger.warning("Connection to gateway lost, reconnecting...")
            await asyncio.sleep(2)
        except Exception:
            logger.exception("Unexpected error in agent loop")
            await asyncio.sleep(2)


def main():
    """Agent 进程的入口点。"""
    logger.info(f"Starting agent {AGENT_NAME} on port {AGENT_PORT}")
    asyncio.run(agent_loop())


if __name__ == "__main__":
    main()
