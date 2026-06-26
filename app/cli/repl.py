"""交互式 REPL，支持斜杠命令界面。

用法：
    crewcraft          # 进入交互模式
    crewcraft> /help   # 显示命令列表
    crewcraft> 帮我...  # 默认为任务编排
"""

import shlex
import sys
import threading
import time

import httpx
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from app.config import config

console = Console()
GATEWAY_URL = f"http://{config.gateway_host}:{config.gateway_port}"

# ── 样式常量 ──────────────────────────────────────────────────────────

OK = "[green]✓[/green]"
ERR = "[red]✗[/red]"
WARN = "[yellow]⚠[/yellow]"

HELP = f"""
CrewCraft Interactive Mode — 输入命令或直接描述你的任务。

  {OK} 先启动 Gateway: [bold]crewcraft gateway start[/bold]

  Slash 命令:
    /agent create <name> --model <model> [--desc <text>]
    /agent list
    /agent inspect <name>
    /agent delete <name>

    /task run <content>              自动编排
    /task run <content> --agent <a>  指定 Agent
    /task status <task_id>
    /task list

    /session list --agent <name>
    /session show <session_id> --agent <name>

    /tool list

    /help     显示此消息
    /exit     退出 (Ctrl+D 同理)

  直接输入任务描述 → 自动编排:
    crewcraft> 帮我研究 Python 3.13 的新特性
"""

COMMANDS = sorted(["/agent", "/task", "/session", "/tool", "/help", "/exit"])


# ── 格式化输出 ────────────────────────────────────────────────────────

def _ok(msg: str):
    console.print(f"  {OK} {msg}")


def _err(msg: str):
    console.print(f"  {ERR} {msg}")


def _warn(msg: str):
    console.print(f"  {WARN} {msg}")


# ── HTTP 辅助 ─────────────────────────────────────────────────────────

def _api(method: str, path: str, **kwargs):
    url = f"{GATEWAY_URL}{path}"
    try:
        resp = getattr(httpx, method)(url, **kwargs)
        resp.raise_for_status()
        return resp.json()
    except httpx.ConnectError:
        _err(f"Cannot connect to gateway at {GATEWAY_URL}")
        console.print("  Start it with: [bold]crewcraft gateway start[/bold] (in another terminal)")
        return None
    except httpx.HTTPStatusError as e:
        try:
            detail = e.response.json().get("detail", str(e))
        except Exception:
            detail = str(e)
        _err(str(detail))
        return None


def _parse_args(args_str: str) -> tuple[dict, str]:
    flags = {}
    remaining = []
    parts = shlex.split(args_str)
    i = 0
    while i < len(parts):
        part = parts[i]
        if part.startswith("--"):
            key = part[2:]
            if i + 1 < len(parts) and not parts[i + 1].startswith("--"):
                flags[key] = parts[i + 1]
                i += 2
            else:
                flags[key] = True
                i += 1
        else:
            remaining.append(part)
            i += 1
    return flags, " ".join(remaining)


# ── Agent 命令 ──────────────────────────────────────────────────────

def cmd_agent_create(args_str: str):
    flags, rest = _parse_args(args_str)
    name = flags.get("name") or (rest.split()[0] if rest else "")
    model = flags.get("model", "deepseek:chat")
    desc = flags.get("desc", rest if rest else "")
    if not name:
        _err("Usage: /agent create <name> --model <model> [--desc <text>]")
        return
    r = _api("post", "/api/agents", json={"name": name, "model": model, "description": desc})
    if r:
        _ok(f"Agent '{name}' created (port {r['port']})")


def cmd_agent_list(args_str: str):
    r = _api("get", "/api/agents")
    if r is None:
        return
    if not r:
        console.print("  No agents configured.")
        return
    table = Table(box=box.SIMPLE)
    table.add_column("", width=2)
    table.add_column("Name")
    table.add_column("Port")
    table.add_column("Model")
    for a in r:
        icon = "[green]●[/green]" if a["online"] else "[dim]○[/dim]"
        table.add_row(icon, a["name"], str(a["port"]), a["model"])
    console.print(table)


def cmd_agent_inspect(args_str: str):
    _, rest = _parse_args(args_str)
    name = rest.split()[0] if rest else ""
    if not name:
        _err("Usage: /agent inspect <name>")
        return
    a = _api("get", f"/api/agents/{name}")
    if a is None:
        return
    table = Table(box=box.SIMPLE, show_header=False)
    table.add_column("Key", style="bold")
    table.add_column("Value")
    table.add_row("Name", a["name"])
    table.add_row("Model", a["model"])
    table.add_row("Description", a.get("description", ""))
    table.add_row("Port", str(a["port"]))
    table.add_row("Idle timeout", f"{a['idle_timeout']}s")
    table.add_row("Online", "yes" if a["online"] else "no")
    table.add_row("Tools", f"{len(a['tools'])} available")
    if a.get("system_prompt"):
        table.add_row("Prompt", f"{len(a['system_prompt'])} chars")
    console.print(table)


def cmd_agent_delete(args_str: str):
    _, rest = _parse_args(args_str)
    name = rest.split()[0] if rest else ""
    if not name:
        _err("Usage: /agent delete <name>")
        return
    console.print(f"  Delete agent '{name}'? [y/N]", end=" ")
    if input().strip().lower() != "y":
        return
    if _api("delete", f"/api/agents/{name}"):
        _ok(f"Agent '{name}' deleted")


AGENT_CMDS = {
    "create": cmd_agent_create,
    "list": cmd_agent_list,
    "inspect": cmd_agent_inspect,
    "delete": cmd_agent_delete,
}


# ── Task 命令 ───────────────────────────────────────────────────────

def _poll_task(task_id: str):
    with console.status(f"[bold]Task {task_id} running...[/bold]"):
        while True:
            try:
                data = _api("get", f"/api/tasks/{task_id}")
                if data is None:
                    return
                if data["status"] == "completed":
                    console.print(f"\n  {OK} Task {task_id} completed")
                    if data.get("result"):
                        console.print(Panel(data["result"][:2000], title="Result"))
                    if data.get("plan"):
                        console.print(f"  Plan: {data['plan']}")
                    return
                elif data["status"] == "failed":
                    _err(f"Task {task_id} failed: {data.get('error', 'unknown')}")
                    return
                time.sleep(1)
            except KeyboardInterrupt:
                console.print(f"\n  Polling stopped. Check: /task status {task_id}")
                return
            except httpx.ConnectError:
                _err("Lost connection to gateway.")
                return


def cmd_task_run(args_str: str):
    flags, rest = _parse_args(args_str)
    content = rest
    agent = flags.get("agent", "")
    if not content:
        _err("Usage: /task run <content> [--agent <name>]")
        return
    r = _api("post", "/api/tasks", json={"content": content, "agent_name": agent})
    if r is None:
        return
    console.print(f"  Task created: [bold]{r['task_id']}[/bold]")
    if r.get("plan"):
        for item in r["plan"]:
            console.print(f"    → {item['agent']}: {item['task']}")
    if flags.get("no-poll"):
        return
    _poll_task(r["task_id"])


def cmd_task_status(args_str: str):
    _, rest = _parse_args(args_str)
    tid = rest.split()[0] if rest else ""
    if not tid:
        _err("Usage: /task status <task_id>")
        return
    data = _api("get", f"/api/tasks/{tid}")
    if data is None:
        return
    color = {"completed": "green", "running": "yellow", "pending": "dim", "failed": "red"}.get(data["status"], "")
    console.print(f"  Task:    {data['task_id']}")
    console.print(f"  Status:  [{color}]{data['status']}[/{color}]")
    if data.get("result"):
        console.print(Panel(data["result"][:2000], title="Result"))
    if data.get("error"):
        _err(data["error"])


def cmd_task_list(args_str: str):
    r = _api("get", "/api/tasks")
    if r is None:
        return
    if not r:
        console.print("  No tasks.")
        return
    table = Table(box=box.SIMPLE)
    table.add_column("Task ID")
    table.add_column("Status")
    table.add_column("Preview")
    for t in r:
        color = {"completed": "green", "running": "yellow", "pending": "dim", "failed": "red"}.get(t["status"], "")
        table.add_row(t["task_id"], f"[{color}]{t['status']}[/{color}]", t.get("result", "")[:50])
    console.print(table)


TASK_CMDS = {"run": cmd_task_run, "status": cmd_task_status, "list": cmd_task_list}


# ── Session 命令 ────────────────────────────────────────────────────

def cmd_session_list(args_str: str):
    flags, _ = _parse_args(args_str)
    agent = flags.get("agent", "")
    if not agent:
        _err("Usage: /session list --agent <name>")
        return
    r = _api("get", f"/api/agents/{agent}/sessions")
    if r is None:
        return
    if not r:
        console.print("  No sessions.")
        return
    table = Table(box=box.SIMPLE)
    table.add_column("Session ID")
    table.add_column("Msgs", justify="right")
    table.add_column("Time")
    for s in r:
        table.add_row(s["session_id"][:16], str(s["message_count"]), s["first_message"])
    console.print(table)


def cmd_session_show(args_str: str):
    flags, rest = _parse_args(args_str)
    sid = rest.split()[0] if rest else ""
    agent = flags.get("agent", "")
    if not sid or not agent:
        _err("Usage: /session show <session_id> --agent <name>")
        return
    messages = _api("get", f"/api/agents/{agent}/sessions/{sid}")
    if messages is None:
        return
    for msg in messages:
        icon = {"user": "🧑", "assistant": "🤖", "tool": "🔧"}.get(msg["role"], "  ")
        role_color = {"user": "cyan", "assistant": "green", "tool": "yellow"}.get(msg["role"], "")
        console.print(f"\n  {icon} [{role_color}]{msg['role']}[/{role_color}]")
        console.print(f"  {msg['content'][:500]}")


SESSION_CMDS = {"list": cmd_session_list, "show": cmd_session_show}


# ── Tool 命令 ────────────────────────────────────────────────────────

def cmd_tool_list(args_str: str):
    try:
        r = _api("get", "/api/tools")
        if r is None:
            return
        table = Table(box=box.SIMPLE)
        table.add_column("Name", style="bold")
        table.add_column("Params")
        table.add_column("Level")
        table.add_column("Description")
        for t in r:
            perm_color = {"safe": "green", "read": "cyan", "write": "yellow", "dangerous": "red"}.get(t.get("permission", ""), "")
            params = ", ".join(t.get("parameters", {}).keys()) or "-"
            table.add_row(t["name"], params, f"[{perm_color}]{t['permission']}[/{perm_color}]", t["description"][:60])
        console.print(table)
    except Exception:
        pass


# ── 交互监听 ─────────────────────────────────────────────────────────

_interaction_running = False


def _resolve_interaction(item: dict, response: str):
    httpx.post(f"{GATEWAY_URL}/api/interactions/{item['request_id']}/resolve",
               json={"response": response}, timeout=3)


def _poll_interactions():
    last_count = 0
    while _interaction_running:
        try:
            resp = httpx.get(f"{GATEWAY_URL}/api/interactions/pending", timeout=2)
            if resp.status_code == 200:
                pending = resp.json()
                if pending and len(pending) > last_count:
                    _show_interaction(pending[0])
                last_count = len(pending)
        except Exception:
            pass
        time.sleep(1)


def _show_interaction(item: dict):
    itype = item.get("type", "confirm")
    agent = item.get("agent", "unknown")
    prompt = item.get("prompt", "")

    if itype == "confirm":
        console.print()
        console.print(Panel(
            f"Agent: [bold]{agent}[/bold]\n\n{prompt[:500]}",
            title="[bold yellow]⚠ 需要确认[/bold yellow]", border_style="yellow"))
        console.print("  [[green]Y[/green]] 允许  [[red]N[/red]] 拒绝")
        try:
            choice = console.input("  [bold]> [/bold]").strip().lower()
        except (KeyboardInterrupt, EOFError):
            choice = "n"
        resp = "approved" if choice in ("y", "yes") else "denied"
        try:
            _resolve_interaction(item, resp)
            console.print(f"  [green]✓ {resp}[/green]\n")
        except Exception:
            console.print("  [red]✗ 通信失败[/red]\n")

    elif itype == "select":
        options = item.get("options", [])
        opts_text = "\n".join(f"  [[green]{i+1}[/green]] {o}" for i, o in enumerate(options))
        console.print()
        console.print(Panel(
            f"Agent: [bold]{agent}[/bold]\n\n{prompt[:300]}\n\n{opts_text}",
            title="[bold cyan]? 请选择[/bold cyan]", border_style="cyan"))
        try:
            choice = console.input("  [bold]> [/bold]").strip()
        except (KeyboardInterrupt, EOFError):
            choice = ""
        if choice.isdigit() and 1 <= int(choice) <= len(options):
            try:
                _resolve_interaction(item, options[int(choice) - 1])
                console.print("  [green]✓ 已选择[/green]\n")
            except Exception:
                console.print("  [red]✗ 通信失败[/red]\n")
        else:
            console.print("  [red]✗ 无效选择[/red]\n")

    elif itype == "input":
        console.print()
        console.print(Panel(
            f"Agent: [bold]{agent}[/bold]\n\n{prompt[:500]}",
            title="[bold cyan]? 需要输入[/bold cyan]", border_style="cyan"))
        try:
            user_input = console.input("  [bold]> [/bold]").strip()
        except (KeyboardInterrupt, EOFError):
            user_input = ""
        try:
            _resolve_interaction(item, user_input)
            console.print("  [green]✓ 已回复[/green]\n")
        except Exception:
            console.print("  [red]✗ 通信失败[/red]\n")


# ── 命令路由 ─────────────────────────────────────────────────────────

def _dispatch(cmd_line: str):
    parts = shlex.split(cmd_line)
    if not parts:
        return
    group = parts[0]
    if group in ("exit", "quit"):
        sys.exit(0)
    if group in ("help", "h"):
        console.print(HELP)
        return
    handler = ROUTER.get(group)
    if handler is None:
        _err(f"Unknown command: {group}")
        console.print(f"  Available: {', '.join(COMMANDS)}")
        return
    if callable(handler):
        handler(" ".join(parts[1:]))
    elif isinstance(handler, dict):
        if len(parts) < 2:
            sub = ", ".join(handler.keys())
            _err(f"Usage: {group} <{sub}>")
            return
        sub_cmd = handler.get(parts[1])
        if sub_cmd:
            sub_cmd(" ".join(parts[2:]))
        else:
            _err(f"Unknown sub-command '{parts[1]}'. Try: {', '.join(handler.keys())}")


ROUTER = {
    "agent": AGENT_CMDS,
    "task": TASK_CMDS,
    "session": SESSION_CMDS,
    "tool": {"list": cmd_tool_list},
    "help": lambda _: console.print(HELP),
    "exit": lambda _: sys.exit(0),
}


# ── REPL 入口 ────────────────────────────────────────────────────────

def repl():
    global _interaction_running

    console.print(Panel.fit(
        "[bold]CrewCraft Interactive[/bold]\n"
        f"Gateway: [dim]{GATEWAY_URL}[/dim]\n"
        "Start gateway first: [bold]crewcraft gateway start[/bold]",
        border_style="blue",
    ))
    console.print("Type [bold]/help[/bold] for commands, or just describe your task. Ctrl+D to exit.\n")

    _interaction_running = True
    poll_thread = threading.Thread(target=_poll_interactions, daemon=True)
    poll_thread.start()

    try:
        while True:
            try:
                raw = console.input("[bold green]crewcraft> [/bold green]").strip()
            except (KeyboardInterrupt, EOFError):
                console.print("\nGoodbye!")
                break

            if not raw:
                continue
            if raw == "?" or raw == "help":
                console.print(HELP)
                continue
            if raw.startswith("/"):
                _dispatch(raw[1:])
            else:
                cmd_task_run(raw)
    finally:
        _interaction_running = False


if __name__ == "__main__":
    repl()
