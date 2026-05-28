import asyncio

import typer

from client import CrewCraftClient

app = typer.Typer(name="crewcraft", help="CrewCraft CLI - Multi-Agent Collaboration Tool")


@app.command("ls")
def list_crews():
    """List all crews."""

    async def _run():
        client = CrewCraftClient()
        try:
            crews = await client.list_crews()
            if not crews:
                typer.echo("No crews found.")
                return
            for c in crews:
                agent_count = len(c.get("agents", []))
                typer.echo(f"  [{c['id']}] {c['name']} ({c['workflow_type']}) - {agent_count} agents")
        finally:
            await client.close()

    asyncio.run(_run())


@app.command("run")
def run_task(
    crew_id: int = typer.Argument(..., help="Crew ID to execute"),
    task: str = typer.Option(..., "--task", "-t", help="Task input text"),
):
    """Run a task with a crew."""

    async def _run():
        client = CrewCraftClient()
        try:
            crew = await client.get_crew(crew_id)
            typer.echo(f"\nRunning task with crew: {crew['name']}\n")
            typer.echo(f"Task: {task}\n")
            typer.echo("-" * 60)

            result = await client.run_task(crew_id, task)
            messages = result.get("messages", [])
            for msg in messages:
                name = msg.get("agent_name", "Unknown")
                role = msg.get("agent_role", "")
                content = msg.get("content", "")
                typer.echo(f"\n[{name}] ({role}):\n{content}\n")
                typer.echo("-" * 60)

            if result.get("result"):
                typer.echo(f"\nFinal Result:\n{result['result']}")
        finally:
            await client.close()

    asyncio.run(_run())


if __name__ == "__main__":
    app()
