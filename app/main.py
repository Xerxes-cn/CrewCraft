"""CrewCraft — 多智能体协作平台。

用法：
    crewcraft                  # 交互式 REPL（默认）
    crewcraft gateway start    # 启动网关服务器
    crewcraft -V               # 显示版本号
"""

import typer

from . import __version__

cli = typer.Typer(
    name="crewcraft",
    help="多智能体协作平台",
    no_args_is_help=False,
)


@cli.callback(invoke_without_command=True)
def main(
    version: bool = typer.Option(False, "--version", "-V", help="显示版本号"),
):
    if version:
        print(f"CrewCraft v{__version__}")
        raise typer.Exit()
    # 无子命令 → 启动 CLI Channel 作为本地交互终端
    from app.channels.cli import CLIChannel
    import asyncio
    ch = CLIChannel({"name": "cli-default", "enabled": True})
    asyncio.run(ch.start())


def register_commands():
    """注册所有子命令（保留以保持向后兼容）。"""
    from .cli.main import agent_app, task_app, session_app, gateway_app, tool_app

    cli.add_typer(agent_app, name="agent", help="管理智能体")
    cli.add_typer(task_app, name="task", help="管理任务")
    cli.add_typer(session_app, name="session", help="管理会话")
    cli.add_typer(gateway_app, name="gateway", help="网关服务器")
    cli.add_typer(tool_app, name="tool", help="管理工具")


register_commands()

if __name__ == "__main__":
    cli()
