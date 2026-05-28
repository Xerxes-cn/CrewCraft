import json

from langgraph.graph import StateGraph, END

from app.engine.agent_loop import run_agent
from app.llm.deepseek import chat_completion


class HierarchicalState(dict):
    task_input: str
    messages: list
    agents: list
    plan: list
    final_result: str


async def leader_node(state: HierarchicalState) -> HierarchicalState:
    agents = state["agents"]
    agent_descriptions = [f"- {a['name']} ({a['role']})" for a in agents]
    team_list = "\n".join(agent_descriptions)

    plan_prompt = f"""You are a team leader. Based on the task, create a plan delegating work to team members.

Available team members:
{team_list}

Task: {state['task_input']}

Respond in JSON format:
{{"plan": [{{"agent_index": 0, "instruction": "what to do"}}, ...]}}"""

    response = await chat_completion(
        messages=[{"role": "user", "content": plan_prompt}],
        temperature=0.3,
    )

    try:
        plan_data = json.loads(response)
        raw_plan = plan_data.get("plan", [])
        # Validate agent indices
        state["plan"] = []
        for item in raw_plan:
            idx = item.get("agent_index", 0)
            if 0 <= idx < len(agents):
                state["plan"].append(item)
            else:
                state["plan"].append({"agent_index": 0, "instruction": item.get("instruction", "")})
    except json.JSONDecodeError:
        state["plan"] = [{"agent_index": 0, "instruction": state["task_input"]}]

    state["messages"].append({"agent_name": "Leader", "agent_role": "Leader", "content": response})
    return state


async def worker_node(state: HierarchicalState) -> HierarchicalState:
    if not state["plan"]:
        return state

    step = state["plan"].pop(0)
    agent_data = state["agents"][step["agent_index"]]

    result = await run_agent(
        agent_data,
        step["instruction"],
        state.get("final_result", ""),
    )
    state["messages"].append(result)
    state["final_result"] = result["content"]
    return state


def should_continue_plan(state: HierarchicalState) -> str:
    return "worker" if state["plan"] else "end"


def build_hierarchical_graph(agents: list[dict]) -> StateGraph:
    graph = StateGraph(HierarchicalState)
    graph.add_node("leader", leader_node)
    graph.add_node("worker", worker_node)

    graph.set_entry_point("leader")
    graph.add_edge("leader", "worker")
    graph.add_conditional_edges("worker", should_continue_plan, {"worker": "worker", "end": END})

    return graph.compile()
