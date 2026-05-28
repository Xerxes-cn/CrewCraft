from typing import Any

from langgraph.graph import StateGraph, END


class RoundtableState(dict):
    task_input: str
    messages: list
    agents: list
    current_round: int
    max_rounds: int
    final_result: str


async def discuss_node(state: RoundtableState) -> RoundtableState:
    from app.engine.agent_loop import run_agent
    from app.llm.deepseek import chat_completion

    agents = state["agents"]
    discussion = "\n".join(
        [m["content"] for m in state["messages"] if isinstance(m, dict) and "content" in m]
    )

    discussion_context = ""
    if discussion:
        discussion_context = f"Previous discussion:\n{discussion}\n\n"

    for agent in agents:
        prompt = f"{discussion_context}Task: {state['task_input']}\n\nShare your perspective on this task."
        result = await run_agent(agent, prompt)
        state["messages"].append(result)

    state["current_round"] += 1

    if state["current_round"] >= state["max_rounds"]:
        summary_prompt = f"Based on the discussion, summarize the consensus:\n{discussion}"
        summary = await chat_completion(
            messages=[{"role": "user", "content": summary_prompt}],
            temperature=0.3,
        )
        state["final_result"] = summary
        state["messages"].append(
            {"agent_name": "Summary", "agent_role": "Summarizer", "content": summary}
        )

    return state


def should_continue_roundtable(state: RoundtableState) -> str:
    return "end" if state["current_round"] >= state["max_rounds"] else "discuss"


def build_roundtable_graph(agents: list[dict], max_rounds: int = 2) -> StateGraph:
    graph = StateGraph(RoundtableState)
    graph.add_node("discuss", discuss_node)

    graph.set_entry_point("discuss")
    graph.add_conditional_edges("discuss", should_continue_roundtable, {"discuss": "discuss", "end": END})

    return graph.compile()
