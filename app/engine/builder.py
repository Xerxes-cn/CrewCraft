"""Build CrewAI objects from agent configuration."""
from __future__ import annotations

from crewai import Agent, Crew, Process, Task

from app.llm.manager import build_crewai_llm
from app.engine.tools import get_crewai_tools


def _resolve_tools(crew_tools: list | None, agent_tools: list | None) -> list:
    """Resolve tool names for an agent by merging crew-level and agent-level tools."""
    if crew_tools is not None:
        names = crew_tools
    else:
        names = agent_tools or []
    result = []
    for t in names:
        if isinstance(t, str):
            result.append(t)
        elif isinstance(t, dict):
            result.append(t.get("name", ""))
    return [n for n in result if n]


def build_crewai_agent(agent_data: dict, tools: list) -> Agent:
    """Convert an agent dict (from ORM) into a CrewAI Agent."""
    llm = build_crewai_llm(agent_data.get("llm_config"))
    return Agent(
        role=agent_data["name"],
        goal=agent_data["role"],
        backstory=agent_data.get("system_prompt") or "",
        tools=tools,
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )


def build_crew_and_tasks(
    agents_orm: list[dict], task_input: str,
    workflow_type: str = "sequential", tools: list | None = None,
) -> tuple[Crew, list[Task]]:
    """Build a CrewAI Crew and Tasks from agent configs."""

    crewai_agents: list[Agent] = []
    for a in agents_orm:
        tool_names = _resolve_tools(tools, a.get("tools", []))
        agent_tools = get_crewai_tools(tool_names)
        crewai_agents.append(build_crewai_agent(a, agent_tools))

    if workflow_type == "sequential":
        tasks = _build_sequential_tasks(crewai_agents, task_input)
        process = Process.sequential
        crew_kwargs = {}
    elif workflow_type == "hierarchical":
        tasks = _build_hierarchical_task(task_input)
        process = Process.hierarchical
        manager_llm = build_crewai_llm(agents_orm[0].get("llm_config") if agents_orm else None)
        crew_kwargs = {"manager_llm": manager_llm}
    else:
        return None, None

    crew = Crew(
        agents=crewai_agents,
        tasks=tasks,
        process=process,
        verbose=True,
        stream=True,
        **crew_kwargs,
    )
    return crew, tasks


def _build_sequential_tasks(agents: list[Agent], task_input: str) -> list[Task]:
    tasks: list[Task] = []
    for i, agent in enumerate(agents):
        context = None
        if i > 0:
            context = [tasks[-1]]
        tasks.append(Task(
            description=task_input,
            expected_output=f"{agent.role} 的执行结果",
            agent=agent,
            context=context,
        ))
    return tasks


def _build_hierarchical_task(task_input: str) -> list[Task]:
    return [
        Task(
            description=task_input,
            expected_output="任务完成后的综合结果",
        )
    ]


def build_roundtable_agents(
    agents_orm: list[dict], tools: list | None = None,
) -> list[Agent]:
    """Build CrewAI Agents for roundtable discussion (without Crew/Task)."""
    agents: list[Agent] = []
    for a in agents_orm:
        tool_names = _resolve_tools(tools, a.get("tools", []))
        agent_tools = get_crewai_tools(tool_names)
        agents.append(build_crewai_agent(a, agent_tools))
    return agents
