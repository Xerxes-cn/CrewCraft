"""CrewCraft CLI 客户端。

通过 REST API 与网关通信。
"""

import os
import time

import httpx
import typer

from app.config import config

GATEWAY_URL = os.getenv("CREWCRAFT_GATEWAY_URL", f"http://{config.gateway_host}:{config.gateway_port}")

# ── Agent 命令 ───────────────────────────────────────────────────────────

agent_app = typer.Typer(help="管理智能体", no_args_is_help=True)


@agent_app.command("create")
def agent_create(
    name: str = typer.Option(..., "--name", "-n", help="Agent 名称（唯一标识符）"),
    model: str = typer.Option(..., "--model", "-m", help="LLM 模型（例如 deepseek:chat）"),
    desc: str = typer.Option("", "--desc", "-d", help="描述 Agent 的功能（系统提示词自动生成）"),
):
    """创建新 Agent。系统提示词根据 --desc 自动生成。"""
    try:
        resp = httpx.post(
            f"{GATEWAY_URL}/api/agents",
            json={
                "name": name,
                "model": model,
                "description": desc,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        typer.echo(f"✓ Agent '{name}' created (port {data['port']})")
    except httpx.HTTPStatusError as e:
        typer.echo(f"✗ {e.response.json().get('detail', e)}", err=True)
        raise typer.Exit(1)
    except httpx.ConnectError:
        typer.echo("✗ Cannot connect to gateway. Is it running?", err=True)
        raise typer.Exit(1)


@agent_app.command("list")
def agent_list():
    """列出所有 Agent。"""
    try:
        resp = httpx.get(f"{GATEWAY_URL}/api/agents")
        resp.raise_for_status()
        agents = resp.json()

        if not agents:
            typer.echo("No agents configured.")
            return

        for a in agents:
            status = "● online" if a["online"] else "○ offline"
            typer.echo(f"  {a['name']:<20} port:{a['port']:<6} model:{a['model']:<20} {status}")
    except httpx.ConnectError:
        typer.echo("✗ Cannot connect to gateway. Is it running?", err=True)
        raise typer.Exit(1)


@agent_app.command("inspect")
def agent_inspect(
    name: str = typer.Argument(..., help="Agent 名称"),
):
    """查看 Agent 配置。"""
    try:
        resp = httpx.get(f"{GATEWAY_URL}/api/agents/{name}")
        resp.raise_for_status()
        a = resp.json()
        typer.echo(f"Name:         {a['name']}")
        typer.echo(f"Model:        {a['model']}")
        typer.echo(f"Description:  {a.get('description', '')}")
        typer.echo(f"Port:         {a['port']}")
        typer.echo(f"Tools:        {len(a['tools'])} available (all built-in)")
        typer.echo(f"Idle timeout: {a['idle_timeout']}s")
        typer.echo(f"Online:       {'yes' if a['online'] else 'no'}")
        typer.echo(f"Created:      {a['created_at']}")
        if a.get("system_prompt"):
            preview = a["system_prompt"][:500]
            typer.echo(f"\nSystem Prompt (first 500 chars):\n{preview}")
    except httpx.HTTPStatusError as e:
        typer.echo(f"✗ {e.response.json().get('detail', e)}", err=True)
        raise typer.Exit(1)
    except httpx.ConnectError:
        typer.echo("✗ Cannot connect to gateway.", err=True)
        raise typer.Exit(1)


@agent_app.command("delete")
def agent_delete(
    name: str = typer.Argument(..., help="Agent 名称"),
    force: bool = typer.Option(False, "--force", "-f", help="跳过确认"),
):
    """删除一个 Agent。"""
    if not force:
        confirm = typer.confirm(f"Delete agent '{name}'? This cannot be undone.")
        if not confirm:
            raise typer.Abort()

    try:
        resp = httpx.delete(f"{GATEWAY_URL}/api/agents/{name}")
        resp.raise_for_status()
        typer.echo(f"✓ Agent '{name}' deleted")
    except httpx.HTTPStatusError as e:
        typer.echo(f"✗ {e.response.json().get('detail', e)}", err=True)
        raise typer.Exit(1)
    except httpx.ConnectError:
        typer.echo("✗ Cannot connect to gateway.", err=True)
        raise typer.Exit(1)


@agent_app.command("generate-prompt")
def agent_generate_prompt(
    name: str = typer.Argument(..., help="Agent 名称"),
    desc: str = typer.Option("", "--desc", "-d", help="用于重新生成提示词的新描述"),
):
    """根据描述重新生成 Agent 的系统提示词。"""
    try:
        resp = httpx.post(
            f"{GATEWAY_URL}/api/agents/{name}/generate-prompt",
            json={"description": desc},
        )
        resp.raise_for_status()
        typer.echo(f"✓ Prompt regenerated for '{name}'")
    except httpx.HTTPStatusError as e:
        typer.echo(f"✗ {e.response.json().get('detail', e)}", err=True)
        raise typer.Exit(1)
    except httpx.ConnectError:
        typer.echo("✗ Cannot connect to gateway.", err=True)
        raise typer.Exit(1)


# ── 任务命令 ─────────────────────────────────────────────────────────────

task_app = typer.Typer(help="管理任务", no_args_is_help=True)


@task_app.command("run")
def task_run(
    content: str = typer.Argument(..., help="任务描述"),
    agent: str = typer.Option(None, "--agent", "-a", help="目标 Agent（省略则自动编排）"),
    poll: bool = typer.Option(True, "--poll/--no-poll", help="轮询结果直到完成"),
):
    """创建任务。不带 --agent 时，编排器自动分配。"""
    try:
        payload = {"content": content}
        if agent:
            payload["agent_name"] = agent
        resp = httpx.post(f"{GATEWAY_URL}/api/tasks", json=payload)
        resp.raise_for_status()
        data = resp.json()
        task_id = data["task_id"]

        typer.echo(f"Task created: {task_id} [pending]")

        if poll:
            _poll_task(task_id)

    except httpx.HTTPStatusError as e:
        typer.echo(f"✗ {e.response.json().get('detail', e)}", err=True)
        raise typer.Exit(1)
    except httpx.ConnectError:
        typer.echo("✗ Cannot connect to gateway.", err=True)
        raise typer.Exit(1)


def _poll_task(task_id: str):
    """轮询任务状态直到完成。"""
    try:
        while True:
            resp = httpx.get(f"{GATEWAY_URL}/api/tasks/{task_id}")
            resp.raise_for_status()
            data = resp.json()
            status = data["status"]

            if status == "completed":
                typer.echo(f"\n✓ Task {task_id} completed")
                if data.get("result"):
                    typer.echo(f"\n{data['result']}")
                break
            elif status == "failed":
                typer.echo(f"\n✗ Task {task_id} failed: {data.get('error', 'unknown')}")
                break
            else:
                typer.echo(f"  ... {status}")
                time.sleep(1)

    except httpx.ConnectError:
        typer.echo("✗ Lost connection to gateway.", err=True)
        raise typer.Exit(1)


@task_app.command("status")
def task_status(
    task_id: str = typer.Argument(..., help="任务 ID"),
):
    """查看任务状态。"""
    try:
        resp = httpx.get(f"{GATEWAY_URL}/api/tasks/{task_id}")
        resp.raise_for_status()
        data = resp.json()
        typer.echo(f"Task:    {data['task_id']}")
        typer.echo(f"Status:  {data['status']}")
        if data.get("session_id"):
            typer.echo(f"Session: {data['session_id']}")
        if data.get("result"):
            typer.echo(f"\nResult:\n{data['result']}")
        if data.get("error"):
            typer.echo(f"\nError: {data['error']}")
    except httpx.HTTPStatusError as e:
        typer.echo(f"✗ {e.response.json().get('detail', e)}", err=True)
        raise typer.Exit(1)
    except httpx.ConnectError:
        typer.echo("✗ Cannot connect to gateway.", err=True)
        raise typer.Exit(1)


@task_app.command("list")
def task_list():
    """列出所有任务。"""
    try:
        resp = httpx.get(f"{GATEWAY_URL}/api/tasks")
        resp.raise_for_status()
        tasks = resp.json()

        if not tasks:
            typer.echo("No tasks.")
            return

        for t in tasks:
            typer.echo(f"  {t['task_id']:<20} {t['status']:<12} {t.get('result', '')[:60]}")
    except httpx.ConnectError:
        typer.echo("✗ Cannot connect to gateway.", err=True)
        raise typer.Exit(1)


# ── 会话命令 ─────────────────────────────────────────────────────────────

session_app = typer.Typer(help="管理会话", no_args_is_help=True)


@session_app.command("list")
def session_list(
    agent: str = typer.Option(..., "--agent", "-a", help="Agent 名称"),
):
    """列出某个 Agent 的会话。"""
    try:
        resp = httpx.get(f"{GATEWAY_URL}/api/agents/{agent}/sessions")
        resp.raise_for_status()
        sessions = resp.json()

        if not sessions:
            typer.echo("No sessions.")
            return

        for s in sessions:
            typer.echo(f"  {s['session_id']:<38} {s['message_count']:>3} msgs  {s['first_message']}")
    except httpx.HTTPStatusError as e:
        typer.echo(f"✗ {e.response.json().get('detail', e)}", err=True)
        raise typer.Exit(1)
    except httpx.ConnectError:
        typer.echo("✗ Cannot connect to gateway.", err=True)
        raise typer.Exit(1)


@session_app.command("show")
def session_show(
    session_id: str = typer.Argument(..., help="会话 ID"),
    agent: str = typer.Option(None, "--agent", "-a", help="Agent 名称（如省略则自动检测）"),
):
    """查看某个会话的完整对话历史。"""
    if not agent:
        typer.echo("✗ --agent is required (auto-detect not yet supported)", err=True)
        raise typer.Exit(1)

    try:
        resp = httpx.get(f"{GATEWAY_URL}/api/agents/{agent}/sessions/{session_id}")
        resp.raise_for_status()
        messages = resp.json()

        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            prefix = {"user": "🧑 You", "assistant": "🤖 Agent", "tool": "🔧 Tool"}.get(role, role)
            tool_info = f" [{msg.get('tool_name', '')}]" if role == "tool" else ""
            typer.echo(f"\n{prefix}{tool_info}:")
            typer.echo(f"  {content[:500]}")
    except httpx.HTTPStatusError as e:
        typer.echo(f"✗ {e.response.json().get('detail', e)}", err=True)
        raise typer.Exit(1)
    except httpx.ConnectError:
        typer.echo("✗ Cannot connect to gateway.", err=True)
        raise typer.Exit(1)


# ── 网关命令 ─────────────────────────────────────────────────────────────

gateway_app = typer.Typer(help="网关服务器", no_args_is_help=True)


@gateway_app.command("start")
def gateway_start(
    host: str = typer.Option(None, "--host", "-h", help="绑定地址"),
    port: int = typer.Option(None, "--port", "-p", help="绑定端口"),
):
    """启动 CrewCraft 网关服务器。"""
    host = host or config.gateway_host
    port = port or config.gateway_port
    typer.echo(f"Starting CrewCraft Gateway on http://{host}:{port}")
    typer.echo(f"Agent WebSocket server on {config.ws_url}")

    from app.gateway.main import start_gateway
    start_gateway(host=host, port=port)


# ── 工具命令 ──────────────────────────────────────────────────────────────

tool_app = typer.Typer(help="管理工具", no_args_is_help=True)


@tool_app.command("list")
def tool_list():
    """列出所有可分配给 Agent 的可用工具。"""
    try:
        resp = httpx.get(f"{GATEWAY_URL}/api/tools")
        resp.raise_for_status()
        tools = resp.json()

        if not tools:
            typer.echo("No tools available.")
            return

        typer.echo(f"\nAvailable tools ({len(tools)}):\n")
        for t in tools:
            params = ", ".join(t.get("parameters", {}).keys()) or "none"
            typer.echo(f"  {t['name']:<18} {params}")
            typer.echo(f"  {'':18} {t['description'][:80]}")
            typer.echo()
    except httpx.HTTPError:
        # 网关不可用或版本过旧 — 回退到本地列表
        _tool_list_local()


def _tool_list_local():
    """在本地列出工具，无需网关。"""
    from app.agent.tools import registry
    tools = registry.list_all()
    typer.echo(f"\nAvailable tools ({len(tools)}):\n")
    for t in tools:
        params = ", ".join(t.parameters.keys()) or "none"
        typer.echo(f"  {t.name:<18} {params}")
        typer.echo(f"  {'':18} {t.description[:80]}")
        typer.echo()
