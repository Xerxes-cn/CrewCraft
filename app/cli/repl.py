"""交互式 REPL，支持斜杠命令界面。

用法：
    crewcraft          # 进入交互模式
    crewcraft> /help   # 显示命令列表
    crewcraft> 帮我...  # 默认为任务编排
"""

import shlex
import sys
import time

import httpx

from app.config import config

GATEWAY_URL = f"http://{config.gateway_host}:{config.gateway_port}"

# ── 帮助文本 ────────────────────────────────────────────────────────────

HELP = """
CrewCraft Interactive Mode — type a command or just describe your task.

  Start gateway first (in another terminal):
    crewcraft gateway start

  Slash Commands:
    /agent create <name> --model <model> [--desc <text>]
    /agent list
    /agent inspect <name>
    /agent delete <name>
    /agent generate-prompt <name> [--desc <text>]

    /task run <content>              auto-orchestrate
    /task run <content> --agent <a>  direct dispatch
    /task status <task_id>
    /task list

    /session list --agent <name>
    /session show <session_id> --agent <name>

    /tool list

    /help     show this message
    /exit     quit (Ctrl+D also works)

  Or just type your task to auto-orchestrate:
    crewcraft> 帮我研究 Python 3.13 的新特性
"""

COMMANDS = sorted(["/agent", "/task", "/session", "/tool", "/help", "/exit"])

# ── 命令处理器 ──────────────────────────────────────────────────────────


def _api(method: str, path: str, **kwargs) -> dict | list | None:
    """向网关发送 HTTP 请求。"""
    url = f"{GATEWAY_URL}{path}"
    try:
        resp = getattr(httpx, method)(url, **kwargs)
        resp.raise_for_status()
        return resp.json()
    except httpx.ConnectError:
        print(f"✗ Cannot connect to gateway at {GATEWAY_URL}")
        print("  Start it with: crewcraft gateway start (in another terminal)")
        return None
    except httpx.HTTPStatusError as e:
        try:
            detail = e.response.json().get("detail", str(e))
        except Exception:
            detail = str(e)
        print(f"✗ {detail}")
        return None


def _parse_args(args_str: str) -> tuple[dict, str]:
    """解析 key=value 和 --flag value 风格的参数。
    返回 (flags_dict, remaining_text)。
    """
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


# ── Agent ─────────────────────────────────────────────────────────────────

def cmd_agent_create(args_str: str):
    """处理 /agent create。"""
    flags, rest = _parse_args(args_str)
    name = flags.get("name") or (rest.split()[0] if rest else "")
    model = flags.get("model", "deepseek:chat")
    desc = flags.get("desc", rest if rest else "")

    if not name:
        print("✗ Usage: /agent create <name> --model <model> [--desc <text>]")
        return

    data = {"name": name, "model": model, "description": desc}
    result = _api("post", "/api/agents", json=data)
    if result:
        print(f"✓ Agent '{name}' created (port {result['port']})")


def cmd_agent_list(args_str: str):
    result = _api("get", "/api/agents")
    if result is None:
        return
    if not result:
        print("No agents configured.")
        return
    for a in result:
        status = "●" if a["online"] else "○"
        print(f"  {status} {a['name']:<16} port:{a['port']:<5} model:{a['model']}")


def cmd_agent_inspect(args_str: str):
    flags, rest = _parse_args(args_str)
    name = rest.split()[0] if rest else ""
    if not name:
        print("✗ Usage: /agent inspect <name>")
        return
    a = _api("get", f"/api/agents/{name}")
    if a is None:
        return
    print(f"  Name:        {a['name']}")
    print(f"  Model:       {a['model']}")
    print(f"  Description: {a.get('description', '')}")
    print(f"  Port:        {a['port']}")
    print(f"  Idle timeout: {a['idle_timeout']}s")
    print(f"  Online:      {'yes' if a['online'] else 'no'}")
    if a.get("system_prompt"):
        print(f"  Prompt:      ({len(a['system_prompt'])} chars, use /agent generate-prompt to modify)")


def cmd_agent_delete(args_str: str):
    flags, rest = _parse_args(args_str)
    name = rest.split()[0] if rest else ""
    if not name:
        print("✗ Usage: /agent delete <name>")
        return
    confirm = input(f"  Delete agent '{name}'? [y/N] ").strip().lower()
    if confirm != "y":
        return
    result = _api("delete", f"/api/agents/{name}")
    if result:
        print(f"✓ Agent '{name}' deleted")


def cmd_agent_generate_prompt(args_str: str):
    flags, rest = _parse_args(args_str)
    name = rest.split()[0] if rest else flags.get("name", "")
    desc = flags.get("desc", rest[len(name):].strip() if len(rest) > len(name) else "")
    if not name:
        print("✗ Usage: /agent generate-prompt <name> --desc <text>")
        return
    result = _api("post", f"/api/agents/{name}/generate-prompt", json={"description": desc})
    if result:
        print(f"✓ Prompt regenerated for '{name}' ({len(result.get('prompt', ''))} chars)")


AGENT_CMDS = {
    "create": cmd_agent_create,
    "list": cmd_agent_list,
    "inspect": cmd_agent_inspect,
    "delete": cmd_agent_delete,
    "generate-prompt": cmd_agent_generate_prompt,
}


# ── Task ──────────────────────────────────────────────────────────────────

def _poll_task(task_id: str):
    """轮询任务状态直到完成。"""
    dots = 0
    while True:
        try:
            data = _api("get", f"/api/tasks/{task_id}")
            if data is None:
                return
            status = data["status"]
            if status == "completed":
                print(f"\r✓ Task {task_id} completed")
                if data.get("result"):
                    print(f"\n{data['result']}")
                if data.get("plan"):
                    print(f"\n  Plan: {data['plan']}")
                return
            elif status == "failed":
                print(f"\r✗ Task {task_id} failed: {data.get('error', 'unknown')}")
                return
            else:
                dots = (dots + 1) % 4
                print(f"\r  ... {status} {'.' * dots}  ", end="", flush=True)
                time.sleep(1)
        except KeyboardInterrupt:
            print(f"\n  Polling stopped. Check status: /task status {task_id}")
            return
        except httpx.ConnectError:
            print("\n✗ Lost connection to gateway.")
            return


def cmd_task_run(args_str: str):
    flags, rest = _parse_args(args_str)
    content = rest
    agent = flags.get("agent", "")

    if not content:
        print("✗ Usage: /task run <content> [--agent <name>]")
        return

    payload = {"content": content}
    if agent:
        payload["agent_name"] = agent

    result = _api("post", "/api/tasks", json=payload)
    if result is None:
        return

    tid = result["task_id"]
    print(f"Task created: {tid}")
    if result.get("plan"):
        for item in result["plan"]:
            print(f"  → {item['agent']}: {item['task']}")

    if flags.get("no-poll"):
        return
    _poll_task(tid)


def cmd_task_status(args_str: str):
    flags, rest = _parse_args(args_str)
    tid = rest.split()[0] if rest else ""
    if not tid:
        print("✗ Usage: /task status <task_id>")
        return
    data = _api("get", f"/api/tasks/{tid}")
    if data is None:
        return
    print(f"  Task:    {data['task_id']}")
    print(f"  Status:  {data['status']}")
    if data.get("session_id"):
        print(f"  Session: {data['session_id']}")
    if data.get("result"):
        print(f"\n  Result:\n  {data['result'][:500]}")
    if data.get("error"):
        print(f"\n  Error: {data['error']}")


def cmd_task_list(args_str: str):
    result = _api("get", "/api/tasks")
    if result is None:
        return
    if not result:
        print("No tasks.")
        return
    for t in result:
        print(f"  {t['task_id']:<18} {t['status']:<12} {t.get('result', '')[:50]}")


TASK_CMDS = {
    "run": cmd_task_run,
    "status": cmd_task_status,
    "list": cmd_task_list,
}


# ── Session ───────────────────────────────────────────────────────────────

def cmd_session_list(args_str: str):
    flags, _ = _parse_args(args_str)
    agent = flags.get("agent", "")
    if not agent:
        print("✗ Usage: /session list --agent <name>")
        return
    result = _api("get", f"/api/agents/{agent}/sessions")
    if result is None:
        return
    if not result:
        print("No sessions.")
        return
    for s in result:
        print(f"  {s['session_id'][:12]}...  {s['message_count']:>3} msgs  {s['first_message']}")


def cmd_session_show(args_str: str):
    flags, rest = _parse_args(args_str)
    sid = rest.split()[0] if rest else ""
    agent = flags.get("agent", "")
    if not sid or not agent:
        print("✗ Usage: /session show <session_id> --agent <name>")
        return
    messages = _api("get", f"/api/agents/{agent}/sessions/{sid}")
    if messages is None:
        return
    for msg in messages:
        role_icon = {"user": "🧑", "assistant": "🤖", "tool": "🔧"}.get(msg["role"], "  ")
        print(f"\n{role_icon} [{msg['role']}] {msg['content'][:500]}")


SESSION_CMDS = {
    "list": cmd_session_list,
    "show": cmd_session_show,
}


# ── Tool ──────────────────────────────────────────────────────────────────

def cmd_tool_list(args_str: str):
    try:
        result = _api("get", "/api/tools")
        if result is None:
            return
        for t in result:
            params = ", ".join(t.get("parameters", {}).keys()) or "none"
            print(f"  {t['name']:<16} ({params})")
            print(f"  {'':16} {t['description'][:80]}")
    except Exception:
        pass


# ── 交互式帮助 ────────────────────────────────────────────────────────────

def _print_help(_=None):
    print(HELP)


# ── 命令路由 ──────────────────────────────────────────────────────────────

ROUTER = {
    "agent": AGENT_CMDS,
    "task": TASK_CMDS,
    "session": SESSION_CMDS,
    "tool": {"list": cmd_tool_list},
    "help": _print_help,
    "exit": lambda _: sys.exit(0),
}


def _dispatch(cmd_line: str):
    """将斜杠命令分发到相应的处理器。"""
    parts = shlex.split(cmd_line)
    if not parts:
        return

    # 查找处理器
    group = parts[0]
    if group in ("exit", "quit"):
        sys.exit(0)

    if group in ("help", "h"):
        print(HELP)
        return

    handler = ROUTER.get(group)
    if handler is None:
        print(f"  Unknown command: {group}")
        print(f"  Available: {', '.join(COMMANDS)}")
        return

    if callable(handler):
        handler(" ".join(parts[1:]))
    elif isinstance(handler, dict):
        if len(parts) < 2:
            sub = ", ".join(handler.keys())
            print(f"  Usage: {group} <{sub}>")
            return
        sub_cmd = handler.get(parts[1])
        if sub_cmd:
            sub_cmd(" ".join(parts[2:]))
        else:
            print(f"  Unknown sub-command '{parts[1]}'. Try: {', '.join(handler.keys())}")
    else:
        print(f"  Internal error: unknown handler type for {group}")


# ── 审批监听 ─────────────────────────────────────────────────────────────

import threading

_approval_running = False


def _poll_approvals():
    """后台线程：轮询 Gateway 的待审批队列，有新请求立即弹出。"""
    global _approval_running
    last_count = 0
    while _approval_running:
        try:
            resp = httpx.get(f"{GATEWAY_URL}/api/approvals/pending", timeout=2)
            if resp.status_code == 200:
                pending = resp.json()
                if pending and len(pending) > last_count:
                    _show_approval_popup(pending[0])
                last_count = len(pending)
        except Exception:
            pass
        time.sleep(1)


def _show_approval_popup(item: dict):
    """在终端显示审批弹窗，等待用户决定。"""
    print(f"\n  ╔{'═'*50}╗")
    print(f"  ║ ⚠ 需要确认{'':38}║")
    print(f"  ║ Agent: {item['agent']:<42}║")
    print(f"  ║ 操作: {item['tool']:<42}║")
    action = item['action'][:40]
    print(f"  ║ 内容: {action:<42}║")
    print(f"  ║ 级别: {item['permission']:<42}║")
    print(f"  ║{'':50}║")
    print(f"  ║ [Y] 允许  [N] 拒绝  [A] 全部允许{'':8}║")
    print(f"  ╚{'═'*50}╝")

    try:
        choice = input("  > ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        choice = "n"

    if choice in ("y", "yes"):
        try:
            httpx.post(f"{GATEWAY_URL}/api/approvals/{item['request_id']}/approve", timeout=3)
            print("  ✓ 已批准\n")
        except Exception:
            print("  ✗ 审批通信失败\n")
    elif choice == "a":
        try:
            httpx.post(f"{GATEWAY_URL}/api/approvals/{item['request_id']}/approve", timeout=3)
            print("  ✓ 已批准（本次会话全部允许）\n")
        except Exception:
            print("  ✗ 审批通信失败\n")
    else:
        try:
            httpx.post(f"{GATEWAY_URL}/api/approvals/{item['request_id']}/deny", timeout=3)
            print("  ✗ 已拒绝\n")
        except Exception:
            print("  ✗ 审批通信失败\n")


# ── REPL 循环 ─────────────────────────────────────────────────────────────

def repl():
    """进入交互式 REPL 模式。"""
    global _approval_running

    print("CrewCraft Interactive")
    print(f"Gateway: {GATEWAY_URL}")
    print("(start gateway first with: crewcraft gateway start)")
    print("Type /help for commands, or just describe your task. Ctrl+D to exit.\n")

    # 启动后台审批监听线程
    _approval_running = True
    poll_thread = threading.Thread(target=_poll_approvals, daemon=True)
    poll_thread.start()

    try:
        while True:
            try:
                raw = input("crewcraft> ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nGoodbye!")
                break

            if not raw:
                continue

            if raw == "?" or raw == "help":
                print(HELP)
                continue

            if raw.startswith("/"):
                _dispatch(raw[1:])
            else:
                cmd_task_run(raw)
    finally:
        _approval_running = False


if __name__ == "__main__":
    repl()
