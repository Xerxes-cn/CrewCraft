import asyncio
import json
from typing import Optional

import typer

from client import CrewCraftClient

app = typer.Typer(name="crewcraft", help="CrewCraft CLI — 多智能体协作工具")
agent_app = typer.Typer(name="agent", help="管理 Agent")
app.add_typer(agent_app, name="agent")

# --- Helpers ---

async def _get_client() -> CrewCraftClient:
    return CrewCraftClient()


def _print_crew(c: dict):
    agents = c.get("agents", [])
    agent_count = len(agents)
    desc = c.get("description") or "(无描述)"
    typer.echo(f"  [{c['id']}] {c['name']}")
    typer.echo(f"      工作流: {c['workflow_type']} | Agent 数: {agent_count}")
    typer.echo(f"      描述: {desc}")
    for a in agents:
        role = a.get("role", "")
        prompt = a.get("system_prompt", "")
        prompt_preview = (prompt[:60] + "...") if prompt and len(prompt) > 60 else prompt
        typer.echo(f"        ├─ [{a['id']}] {a['name']} ({role})")
        if prompt_preview:
            typer.echo(f"        │   {prompt_preview}")
    typer.echo()


# --- Crew Commands ---

@app.command("ls")
def list_crews():
    """列出所有团队。"""
    async def _run():
        client = CrewCraftClient()
        try:
            crews = await client.list_crews()
            if not crews:
                typer.echo("没有找到团队。使用 crewcraft create 创建一个。")
                return
            for c in crews:
                _print_crew(c)
        finally:
            await client.close()
    asyncio.run(_run())


@app.command("create")
def create_crew(
    name: str = typer.Option(..., "--name", "-n", help="团队名称"),
    description: str = typer.Option("", "--desc", "-d", help="团队描述"),
    workflow: str = typer.Option("roundtable", "--workflow", "-w", help="工作流类型 (roundtable/sequential/hierarchical)"),
    max_rounds: int = typer.Option(2, "--max-rounds", "-r", help="最大讨论轮数 (roundtable 专用)"),
):
    """创建新团队。"""
    async def _run():
        client = CrewCraftClient()
        try:
            data = {
                "name": name,
                "description": description,
                "workflow_type": workflow,
                "workflow_config": {"max_rounds": max_rounds} if workflow == "roundtable" else {},
            }
            crew = await client.create_crew(data)
            typer.echo(f"✓ 团队已创建: [{crew['id']}] {crew['name']}")
        finally:
            await client.close()
    asyncio.run(_run())


@app.command("inspect")
def inspect_crew(
    crew_id: int = typer.Argument(..., help="团队 ID"),
):
    """查看团队详情。"""
    async def _run():
        client = CrewCraftClient()
        try:
            crew = await client.get_crew(crew_id)
            _print_crew(crew)
        finally:
            await client.close()
    asyncio.run(_run())


@app.command("update")
def update_crew(
    crew_id: int = typer.Argument(..., help="团队 ID"),
    name: str = typer.Option(None, "--name", "-n", help="新名称"),
    description: str = typer.Option(None, "--desc", "-d", help="新描述"),
    workflow: str = typer.Option(None, "--workflow", "-w", help="工作流类型"),
    max_rounds: int = typer.Option(None, "--max-rounds", "-r", help="最大讨论轮数"),
    tools: str = typer.Option(None, "--tools", "-t", help="工具列表 (JSON 数组)"),
):
    """更新团队配置。"""
    async def _run():
        client = CrewCraftClient()
        try:
            data = {}
            if name is not None:
                data["name"] = name
            if description is not None:
                data["description"] = description
            if workflow is not None:
                data["workflow_type"] = workflow
            if max_rounds is not None:
                data["workflow_config"] = {"max_rounds": max_rounds}
            if tools is not None:
                data["tools"] = json.loads(tools)

            if not data:
                typer.echo("请至少指定一个要更新的字段。")
                return

            crew = await client.update_crew(crew_id, data)
            typer.echo(f"✓ 团队已更新: [{crew['id']}] {crew['name']}")
        finally:
            await client.close()
    asyncio.run(_run())


@app.command("delete")
def delete_crew(
    crew_id: int = typer.Argument(..., help="团队 ID"),
    force: bool = typer.Option(False, "--force", "-f", help="跳过确认"),
):
    """删除团队。"""
    if not force:
        confirm = typer.confirm(f"确认删除团队 #{crew_id}？此操作不可撤销。")
        if not confirm:
            typer.echo("已取消。")
            return

    async def _run():
        client = CrewCraftClient()
        try:
            await client.delete_crew(crew_id)
            typer.echo(f"✓ 团队 #{crew_id} 已删除。")
        finally:
            await client.close()
    asyncio.run(_run())


# --- Agent Subcommands ---

@agent_app.command("add")
def add_agent(
    crew_id: int = typer.Argument(..., help="目标团队 ID"),
    name: str = typer.Option(..., "--name", "-n", help="Agent 名称"),
    role: str = typer.Option(..., "--role", "-r", help="Agent 角色"),
    system_prompt: str = typer.Option("", "--prompt", "-p", help="系统提示词"),
    order: int = typer.Option(0, "--order", "-o", help="执行顺序"),
    tools: str = typer.Option(None, "--tools", "-t", help="工具列表 (JSON 数组)"),
):
    """向团队添加 Agent。"""
    async def _run():
        client = CrewCraftClient()
        try:
            data = {
                "name": name,
                "role": role,
                "system_prompt": system_prompt,
                "order": order,
            }
            if tools:
                data["tools"] = json.loads(tools)
            agent = await client.create_agent(crew_id, data)
            typer.echo(f"✓ Agent 已添加: [{agent['id']}] {agent['name']} ({agent['role']})")
        finally:
            await client.close()
    asyncio.run(_run())


@agent_app.command("update")
def update_agent(
    agent_id: int = typer.Argument(..., help="Agent ID"),
    name: str = typer.Option(None, "--name", "-n", help="新名称"),
    role: str = typer.Option(None, "--role", "-r", help="新角色"),
    system_prompt: str = typer.Option(None, "--prompt", "-p", help="新系统提示词"),
    order: int = typer.Option(None, "--order", "-o", help="新执行顺序"),
    tools: str = typer.Option(None, "--tools", "-t", help="工具列表 (JSON 数组)"),
):
    """更新 Agent 配置。"""
    async def _run():
        client = CrewCraftClient()
        try:
            data = {}
            if name is not None:
                data["name"] = name
            if role is not None:
                data["role"] = role
            if system_prompt is not None:
                data["system_prompt"] = system_prompt
            if order is not None:
                data["order"] = order
            if tools is not None:
                data["tools"] = json.loads(tools)

            if not data:
                typer.echo("请至少指定一个要更新的字段。")
                return

            agent = await client.update_agent(agent_id, data)
            typer.echo(f"✓ Agent 已更新: [{agent['id']}] {agent['name']} ({agent['role']})")
        finally:
            await client.close()
    asyncio.run(_run())


@agent_app.command("remove")
def remove_agent(
    agent_id: int = typer.Argument(..., help="Agent ID"),
    force: bool = typer.Option(False, "--force", "-f", help="跳过确认"),
):
    """从团队中移除 Agent。"""
    if not force:
        confirm = typer.confirm(f"确认删除 Agent #{agent_id}？")
        if not confirm:
            typer.echo("已取消。")
            return

    async def _run():
        client = CrewCraftClient()
        try:
            await client.delete_agent(agent_id)
            typer.echo(f"✓ Agent #{agent_id} 已删除。")
        finally:
            await client.close()
    asyncio.run(_run())


# --- Discovery Commands ---

@app.command("tools")
def list_tools():
    """列出所有可用工具。"""
    async def _run():
        client = CrewCraftClient()
        try:
            tools = await client.list_tools()
            if not tools:
                typer.echo("没有可用工具。")
                return
            typer.echo("\n可用工具:\n")
            for t in tools:
                typer.echo(f"  {t['name']}")
                typer.echo(f"      {t.get('description', '(无描述)')}")
        finally:
            await client.close()
    asyncio.run(_run())


@app.command("skills")
def list_skills():
    """列出所有技能预设。"""
    async def _run():
        client = CrewCraftClient()
        try:
            skills = await client.list_skills()
            if not skills:
                typer.echo("没有可用技能。")
                return
            typer.echo("\n可用技能预设:\n")
            for s in skills:
                typer.echo(f"  {s.get('label', s['name'])}")
                typer.echo(f"      工具: {', '.join(s.get('tools', []))}")
                if s.get("description"):
                    typer.echo(f"      描述: {s['description']}")
        finally:
            await client.close()
    asyncio.run(_run())


# --- Task Commands ---

@app.command("run")
def run_task(
    crew_id: int = typer.Argument(..., help="团队 ID"),
    task: str = typer.Option(..., "--task", "-t", help="任务内容"),
    streaming: bool = typer.Option(False, "--stream", "-s", help="流式输出（当前为批处理模式）"),
):
    """执行任务。"""
    async def _run():
        client = CrewCraftClient()
        try:
            crew = await client.get_crew(crew_id)
            if streaming:
                typer.echo(f"\n⚡ 执行团队: {crew['name']}\n")
            else:
                typer.echo(f"\n执行团队: {crew['name']} ({crew['workflow_type']})\n")
            typer.echo(f"任务: {task}\n")
            typer.echo("-" * 60)

            result = await client.run_task(crew_id, task)
            messages = result.get("messages", [])
            for msg in messages:
                name = msg.get("agent_name", "Unknown")
                role = msg.get("agent_role", "")
                content = msg.get("content", "")
                label = f"[{name}]"
                if role:
                    label += f" ({role})"
                typer.echo(f"\n{label}:\n{content}\n")
                typer.echo("-" * 60)

            if result.get("result"):
                typer.echo(f"\n✓ 最终结果:\n{result['result']}")
            typer.echo(f"\n状态: {result.get('status', 'unknown')}")
        finally:
            await client.close()
    asyncio.run(_run())


@app.command("tasks")
def list_task_history(
    crew_id: int = typer.Argument(..., help="团队 ID"),
):
    """列出团队的任务历史。"""
    async def _run():
        client = CrewCraftClient()
        try:
            tasks = await client.list_tasks(crew_id)
            if not tasks:
                typer.echo("没有任务记录。")
                return
            typer.echo(f"\n任务历史 (最近 {len(tasks)} 条):\n")
            for t in tasks:
                status_icon = "✓" if t["status"] == "completed" else "◌" if t["status"] == "running" else "✗"
                typer.echo(f"  [{t['id']}] {status_icon} {t['input'][:60]}")
                if t.get("result"):
                    result_preview = t["result"][:80]
                    typer.echo(f"      → {result_preview}")
                typer.echo()
        finally:
            await client.close()
    asyncio.run(_run())


@app.command("task")
def get_task_detail(
    task_id: int = typer.Argument(..., help="任务 ID"),
):
    """查看任务详情。"""
    async def _run():
        client = CrewCraftClient()
        try:
            t = await client.get_task(task_id)
            typer.echo(f"\n任务 #{t['id']}")
            typer.echo(f"团队: {t['crew_id']}")
            typer.echo(f"状态: {t['status']}")
            typer.echo(f"输入: {t['input']}")
            typer.echo(f"创建时间: {t['created_at']}")
            typer.echo()

            messages = t.get("messages") or []
            if messages:
                typer.echo("对话记录:\n")
                for msg in messages:
                    name = msg.get("agent_name", "Unknown")
                    role = msg.get("agent_role", "")
                    content = msg.get("content", "")
                    label = f"[{name}]"
                    if role:
                        label += f" ({role})"
                    typer.echo(f"  {label}:")
                    typer.echo(f"  {content[:200]}")
                    typer.echo()

            if t.get("result"):
                typer.echo(f"最终结果:\n{t['result']}")
        finally:
            await client.close()
    asyncio.run(_run())


if __name__ == "__main__":
    app()
