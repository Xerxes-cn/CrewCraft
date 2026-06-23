"""CrewCraft - Multi-agent collaboration platform.

Usage:
    crewcraft gateway start     # Start the gateway server
    crewcraft agent ...         # CLI commands (see crewcraft --help)
"""

import typer

from app import __version__

cli = typer.Typer(
    name="crewcraft",
    help="Multi-agent collaboration platform",
    no_args_is_help=True,
)


@cli.callback(invoke_without_command=True)
def main(
    version: bool = typer.Option(False, "--version", "-V", help="Show version"),
):
    if version:
        print(f"CrewCraft v{__version__}")
        raise typer.Exit()


def register_commands():
    """Register all subcommands."""
    from app.cli.main import agent_app, task_app, session_app, gateway_app

    cli.add_typer(agent_app, name="agent", help="Manage agents")
    cli.add_typer(task_app, name="task", help="Manage tasks")
    cli.add_typer(session_app, name="session", help="Manage sessions")
    cli.add_typer(gateway_app, name="gateway", help="Gateway server")


register_commands()

if __name__ == "__main__":
    cli()
