"""CLI Channel — 终端交互作为一等 Channel。"""

import threading
import time

import httpx
from rich.console import Console
from rich.panel import Panel

from app.config import config as app_config
from .base import BaseChannel
from .bus import OutboundMsg
from . import register_channel_type

console = Console()
GATEWAY_URL = f"http://{app_config.gateway_host}:{app_config.gateway_port}"

_approval_running = False


def _poll_approvals():
    """后台线程：轮询交互队列。"""
    last_count = 0
    while _approval_running:
        try:
            resp = httpx.get(f"{GATEWAY_URL}/api/interactions/pending", timeout=2)
            if resp.status_code == 200:
                pending = resp.json()
                if pending and len(pending) > last_count:
                    item = pending[0]
                    _show_popup(item)
                last_count = len(pending)
        except Exception:
            pass
        time.sleep(1)


def _resolve(item: dict, response: str):
    """向 /api/interactions/{id}/resolve 发送用户响应。"""
    httpx.post(f"{GATEWAY_URL}/api/interactions/{item['request_id']}/resolve",
               json={"response": response}, timeout=3)


def _show_popup(item: dict):
    itype = item.get("type", "confirm")
    agent = item.get("agent", "unknown")
    prompt = item.get("prompt", "")

    if itype == "confirm":
        title = "[bold yellow]⚠ 需要确认[/bold yellow]"
        body = f"Agent: [bold]{agent}[/bold]\n\n{prompt[:500]}"
        console.print()
        console.print(Panel(body, title=title, border_style="yellow"))
        console.print("  [[green]Y[/green]] 允许  [[red]N[/red]] 拒绝")

        try:
            choice = console.input("  [bold]> [/bold]").strip().lower()
        except (KeyboardInterrupt, EOFError):
            choice = "n"

        resp = "approved" if choice in ("y", "yes") else "denied"
        try:
            _resolve(item, resp)
            console.print(f"  [green]✓ {resp}[/green]\n")
        except Exception:
            console.print("  [red]✗ 通信失败[/red]\n")

    elif itype == "select":
        options = item.get("options", [])
        title = "[bold cyan]? 请选择[/bold cyan]"
        opts_text = "\n".join(f"  [[green]{i+1}[/green]] {o}" for i, o in enumerate(options))
        body = f"Agent: [bold]{agent}[/bold]\n\n{prompt[:300]}\n\n{opts_text}"
        console.print()
        console.print(Panel(body, title=title, border_style="cyan"))

        try:
            choice = console.input("  [bold]> [/bold]").strip()
        except (KeyboardInterrupt, EOFError):
            choice = ""

        if choice.isdigit() and 1 <= int(choice) <= len(options):
            selection = options[int(choice) - 1]
            try:
                _resolve(item, selection)
                console.print(f"  [green]✓ 已选择: {selection}[/green]\n")
            except Exception:
                console.print("  [red]✗ 通信失败[/red]\n")
        else:
            console.print("  [red]✗ 无效选择[/red]\n")

    elif itype == "input":
        title = "[bold cyan]? 需要输入[/bold cyan]"
        body = f"Agent: [bold]{agent}[/bold]\n\n{prompt[:500]}"
        console.print()
        console.print(Panel(body, title=title, border_style="cyan"))

        try:
            user_input = console.input("  [bold]> [/bold]").strip()
        except (KeyboardInterrupt, EOFError):
            user_input = ""

        try:
            _resolve(item, user_input)
            console.print("  [green]✓ 已回复[/green]\n")
        except Exception:
            console.print("  [red]✗ 通信失败[/red]\n")


class CLILoop:
    """终端交互循环。"""

    def __init__(self, channel: "CLIChannel"):
        self.channel = channel
        self._running = False

    async def run(self):
        self._running = True
        global _approval_running
        _approval_running = True
        poll_thread = threading.Thread(target=_poll_approvals, daemon=True)
        poll_thread.start()

        console.print(Panel.fit(
            "[bold]CrewCraft Interactive[/bold]\n"
            f"Gateway: [dim]{GATEWAY_URL}[/dim]",
            border_style="blue",
        ))
        console.print("输入消息或 /help 查看命令。Ctrl+D 退出。\n")

        while self._running:
            try:
                raw = console.input("[bold green]crewcraft> [/bold green]").strip()
            except (KeyboardInterrupt, EOFError):
                console.print("\nGoodbye!")
                break

            if not raw:
                continue
            if raw in ("/exit", "/quit"):
                break
            if raw.startswith("/help"):
                self._show_help()
                continue
            if raw.startswith("/agent"):
                self._handle_agent_command(raw)
                continue

            # 发消息到总线
            await self.channel._on_message(raw, "cli-user", "cli-session")

        self._running = False
        _approval_running = False

    def _show_help(self):
        console.print("""
  Slash 命令:
    /agent create <name> --model <m> --desc <d>
    /agent list
    /agent inspect <name>
    /agent delete <name>
    /tool list
    /exit
""")

    def _handle_agent_command(self, raw: str):
        """将 /agent 命令转发到 CLI dispatcher。"""
        from app.cli.repl import _dispatch
        _dispatch(raw[1:])


class CLIChannel(BaseChannel):
    """终端交互 Channel。"""

    name = "cli"
    display_name = "CLI"

    def __init__(self, config: dict):
        super().__init__(config)
        self._loop = CLILoop(self)

    async def start(self):
        """进入交互循环。"""
        self._running = True
        await self._loop.run()

    async def stop(self):
        self._running = False
        self._loop._running = False

    async def send(self, msg: OutboundMsg):
        """在终端显示回复。"""
        if msg.metadata.get("_stream_delta"):
            console.print(msg.content, end="", highlight=False)
        else:
            console.print(f"\n[bold cyan]🤖[/bold cyan] {msg.content}")


register_channel_type("cli", CLIChannel)
