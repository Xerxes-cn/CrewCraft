"""CLI Channel — 终端交互作为一等 Channel。"""

import asyncio
import sys
import threading
import time

import httpx
from rich.console import Console
from rich.panel import Panel

from app.config import config as app_config
from .base import BaseChannel
from .bus import OutboundMsg, msg_manager
from . import register_channel_type

console = Console()
GATEWAY_URL = f"http://{app_config.gateway_host}:{app_config.gateway_port}"

_approval_running = False


def _poll_approvals():
    """后台线程：轮询审批队列。"""
    global _approval_running
    last_count = 0
    while _approval_running:
        try:
            resp = httpx.get(f"{GATEWAY_URL}/api/approvals/pending", timeout=2)
            if resp.status_code == 200:
                pending = resp.json()
                if pending and len(pending) > last_count:
                    item = pending[0]
                    _show_popup(item)
                last_count = len(pending)
        except Exception:
            pass
        time.sleep(1)


def _show_popup(item: dict):
    perm_color = {"write": "yellow", "dangerous": "red"}.get(item["permission"], "white")
    content = (
        f"Agent: [bold]{item['agent']}[/bold]\n"
        f"Tool:  [bold]{item['tool']}[/bold]\n"
        f"Level: [{perm_color}]{item['permission']}[/{perm_color}]\n\n"
        f"[dim]{item['action'][:200]}[/dim]"
    )
    console.print()
    console.print(Panel(content, title="[bold yellow]⚠ 需要确认[/bold yellow]", border_style="yellow"))
    console.print("  [[green]Y[/green]] 允许  [[red]N[/red]] 拒绝  [[blue]A[/blue]] 全部允许")

    try:
        choice = console.input("  [bold]> [/bold]").strip().lower()
    except (KeyboardInterrupt, EOFError):
        choice = "n"

    try:
        if choice in ("y", "yes"):
            httpx.post(f"{GATEWAY_URL}/api/approvals/{item['request_id']}/approve", timeout=3)
            console.print("  [green]✓ 已批准[/green]\n")
        elif choice == "a":
            httpx.post(f"{GATEWAY_URL}/api/approvals/{item['request_id']}/approve", timeout=3)
            console.print("  [green]✓ 已批准（全部允许）[/green]\n")
        else:
            httpx.post(f"{GATEWAY_URL}/api/approvals/{item['request_id']}/deny", timeout=3)
            console.print("  [red]✗ 已拒绝[/red]\n")
    except Exception:
        console.print("  [red]✗ 审批通信失败[/red]\n")


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
                self._handle_legacy(raw)
                continue

            # 发消息到总线
            await self.channel._on_message(raw, "cli-user", "cli-session")

        self._running = False
        _approval_running = False

    def _show_help(self):
        console.print("""
  Slash 命令（旧版兼容）:
    /agent create <name> --model <m> --desc <d>
    /agent list
    /agent inspect <name>
    /agent delete <name>
    /tool list
    /exit
""")

    def _handle_legacy(self, raw: str):
        """代理旧的 /agent 等命令到 REST API。"""
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
