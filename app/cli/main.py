"""CLI client for CrewCraft.

Communicates with the Gateway via REST API.
"""

import os
import sys
import time

import httpx
import typer

from app.config import config

GATEWAY_URL = os.getenv("CREWCRAFT_GATEWAY_URL", f"http://{config.gateway_host}:{config.gateway_port}")

# ── Agent commands ─────────────────────────────────────────────────────

agent_app = typer.Typer(help="Manage agents", no_args_is_help=True)


@agent_app.command("create")
def agent_create(
    name: str = typer.Option(..., "--name", "-n", help="Agent name (unique identifier)"),
    model: str = typer.Option(..., "--model", "-m", help="LLM model (e.g. deepseek:chat)"),
    prompt: str = typer.Option("", "--prompt", "-p", help="System prompt"),
    tools: str = typer.Option("", "--tools", "-t", help="Comma-separated tool names"),
):
    """Create a new agent."""
    tool_list = [t.strip() for t in tools.split(",") if t.strip()] if tools else []

    try:
        resp = httpx.post(
            f"{GATEWAY_URL}/api/agents",
            json={
                "name": name,
                "model": model,
                "system_prompt": prompt,
                "tools": tool_list,
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
    """List all agents."""
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
    name: str = typer.Argument(..., help="Agent name"),
):
    """Show agent configuration."""
    try:
        resp = httpx.get(f"{GATEWAY_URL}/api/agents/{name}")
        resp.raise_for_status()
        a = resp.json()
        typer.echo(f"Name:         {a['name']}")
        typer.echo(f"Model:        {a['model']}")
        typer.echo(f"Port:         {a['port']}")
        typer.echo(f"Tools:        {', '.join(a['tools']) or '(none)'}")
        typer.echo(f"Idle timeout: {a['idle_timeout']}s")
        typer.echo(f"Online:       {'yes' if a['online'] else 'no'}")
        typer.echo(f"Created:      {a['created_at']}")
        if a["system_prompt"]:
            typer.echo(f"\nSystem Prompt:\n{a['system_prompt']}")
    except httpx.HTTPStatusError as e:
        typer.echo(f"✗ {e.response.json().get('detail', e)}", err=True)
        raise typer.Exit(1)
    except httpx.ConnectError:
        typer.echo("✗ Cannot connect to gateway.", err=True)
        raise typer.Exit(1)


@agent_app.command("delete")
def agent_delete(
    name: str = typer.Argument(..., help="Agent name"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Delete an agent."""
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


# ── Task commands ──────────────────────────────────────────────────────

task_app = typer.Typer(help="Manage tasks", no_args_is_help=True)


@task_app.command("run")
def task_run(
    agent: str = typer.Option(..., "--agent", "-a", help="Target agent name"),
    content: str = typer.Argument(..., help="Task description"),
    poll: bool = typer.Option(True, "--poll/--no-poll", help="Poll for result until complete"),
):
    """Create a task and assign it to an agent."""
    try:
        resp = httpx.post(
            f"{GATEWAY_URL}/api/tasks",
            json={"agent_name": agent, "content": content},
        )
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
    """Poll task status until completion."""
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
    task_id: str = typer.Argument(..., help="Task ID"),
):
    """Check task status."""
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
    """List all tasks."""
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


# ── Session commands ───────────────────────────────────────────────────

session_app = typer.Typer(help="Manage sessions", no_args_is_help=True)


@session_app.command("list")
def session_list(
    agent: str = typer.Option(..., "--agent", "-a", help="Agent name"),
):
    """List sessions for an agent."""
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
    session_id: str = typer.Argument(..., help="Session ID"),
    agent: str = typer.Option(None, "--agent", "-a", help="Agent name (auto-detect if omitted)"),
):
    """Show full conversation history for a session."""
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


# ── Gateway commands ───────────────────────────────────────────────────

gateway_app = typer.Typer(help="Gateway server", no_args_is_help=True)


@gateway_app.command("start")
def gateway_start(
    host: str = typer.Option(None, "--host", "-h", help="Bind address"),
    port: int = typer.Option(None, "--port", "-p", help="Bind port"),
):
    """Start the CrewCraft gateway server."""
    host = host or config.gateway_host
    port = port or config.gateway_port
    typer.echo(f"Starting CrewCraft Gateway on http://{host}:{port}")
    typer.echo(f"Agent WebSocket server on {config.ws_url}")

    from app.gateway.main import start_gateway
    start_gateway(host=host, port=port)


# ── Tool commands ────────────────────────────────────────────────────────

tool_app = typer.Typer(help="Manage tools", no_args_is_help=True)


@tool_app.command("list")
def tool_list():
    """List all available tools that can be assigned to agents."""
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
        # Gateway not available or outdated — fallback to local
        _tool_list_local()


def _tool_list_local():
    """List tools locally without gateway."""
    from app.agent.tools import registry
    tools = registry.list_all()
    typer.echo(f"\nAvailable tools ({len(tools)}):\n")
    for t in tools:
        params = ", ".join(t.parameters.keys()) or "none"
        typer.echo(f"  {t.name:<18} {params}")
        typer.echo(f"  {'':18} {t.description[:80]}")
        typer.echo()
