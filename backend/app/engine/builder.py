"""Build CrewAI objects from ORM records."""
from __future__ import annotations

from crewai import Agent, Crew, Process, Task

from app.llm.manager import build_crewai_llm
from app.engine.tools import get_crewai_tools


def _resolve_tools(crew_tools: list | None, agent_tools: list | None) -> list:
    """Resolve tool names for an agent by merging crew-level and agent-level tools."""
    # crew_tools None means use agent-level; otherwise use crew-level (override)
    if crew_tools is not None:
        names = crew_tools
    else:
        names = agent_tools or []
    # Normalize: tools can be strings or {"name": "..."} dicts
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
    crew_orm, agents_orm: list[dict], task_input: str
) -> tuple[Crew, list[Task]]:
    """Build a CrewAI Crew and Tasks from ORM data.

    Returns (crew, tasks) for sequential/hierarchical workflows.
    For roundtable, returns (None, None) — handled separately.
    """
    crew_tools = crew_orm.tools  # crew-level tool names

    # Build agents
    crewai_agents: list[Agent] = []
    for a in agents_orm:
        tool_names = _resolve_tools(crew_tools, a.get("tools", []))
        agent_tools = get_crewai_tools(tool_names)
        crewai_agents.append(build_crewai_agent(a, agent_tools))

    workflow_type = crew_orm.workflow_type

    if workflow_type == "sequential":
        tasks = _build_sequential_tasks(crewai_agents, task_input)
        process = Process.sequential
        crew_kwargs = {}
    elif workflow_type == "hierarchical":
        tasks = _build_hierarchical_task(task_input)
        process = Process.hierarchical
        # CrewAI needs manager_llm or manager_agent for hierarchical process
        manager_llm = build_crewai_llm(agents_orm[0].get("llm_config") if agents_orm else None)
        crew_kwargs = {"manager_llm": manager_llm}
    else:
        # Roundtable — caller should use run_roundtable() instead
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
    """Create one Task per agent for sequential execution.

    Each agent gets the user's input. CrewAI's sequential process pipes
    previous task output as context to the next task automatically.
    """
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
    """Create a single task for hierarchical execution.

    The first agent in the crew acts as the manager; CrewAI's
    Process.hierarchical handles delegation automatically.
    """
    return [
        Task(
            description=task_input,
            expected_output="任务完成后的综合结果",
        )
    ]


def build_roundtable_agents(
    crew_orm, agents_orm: list[dict]
) -> list[Agent]:
    """Build CrewAI Agents for roundtable discussion (without Crew/Task)."""
    crew_tools = crew_orm.tools
    agents: list[Agent] = []
    for a in agents_orm:
        tool_names = _resolve_tools(crew_tools, a.get("tools", []))
        agent_tools = get_crewai_tools(tool_names)
        agents.append(build_crewai_agent(a, agent_tools))
    return agents
