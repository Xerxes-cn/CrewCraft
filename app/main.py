"""CrewCraft - Multi-agent collaboration platform.

Usage:
    crewcraft                  # Interactive REPL (default)
    crewcraft gateway start    # Start the gateway server
    crewcraft -V               # Show version
"""

import sys

import typer

from . import __version__

cli = typer.Typer(
    name="crewcraft",
    help="Multi-agent collaboration platform",
    no_args_is_help=False,
)


@cli.callback(invoke_without_command=True)
def main(
    version: bool = typer.Option(False, "--version", "-V", help="Show version"),
):
    if version:
        print(f"CrewCraft v{__version__}")
        raise typer.Exit()
    # No subcommand → enter REPL
    from .cli.repl import repl
    repl()


def register_commands():
    """Register all subcommands (kept for backward compatibility)."""
    from .cli.main import agent_app, task_app, session_app, gateway_app, tool_app

    cli.add_typer(agent_app, name="agent", help="Manage agents")
    cli.add_typer(task_app, name="task", help="Manage tasks")
    cli.add_typer(session_app, name="session", help="Manage sessions")
    cli.add_typer(gateway_app, name="gateway", help="Gateway server")
    cli.add_typer(tool_app, name="tool", help="Manage tools")


register_commands()

if __name__ == "__main__":
    cli()
