from langgraph.graph import StateGraph, END

from app.engine.agent_loop import run_agent


class SequentialState(dict):
    task_input: str
    messages: list
    current_index: int
    agents: list
    final_result: str


async def run_agent_node(state: SequentialState) -> SequentialState:
    agents = state["agents"]
    idx = state["current_index"]
    if idx >= len(agents):
        return state

    agent = agents[idx]
    result = await run_agent(agent, state["task_input"], state.get("final_result", ""))
    state["messages"].append(result)
    state["final_result"] = result["content"]
    state["current_index"] = idx + 1
    return state


def should_continue(state: SequentialState) -> str:
    if state["current_index"] >= len(state["agents"]):
        return "end"
    return "next"


def build_sequential_graph(agents: list[dict]) -> StateGraph:
    graph = StateGraph(SequentialState)
    graph.add_node("agent", run_agent_node)

    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", should_continue, {"next": "agent", "end": END})

    return graph.compile()
