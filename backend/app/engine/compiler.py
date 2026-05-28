from langgraph.graph import StateGraph

from app.engine.workflows.sequential import build_sequential_graph
from app.engine.workflows.hierarchical import build_hierarchical_graph
from app.engine.workflows.roundtable import build_roundtable_graph
from app.models.orm import Crew


def compile_crew_graph(crew: Crew) -> StateGraph:
    agents_data = [
        {
            "id": a.id,
            "name": a.name,
            "role": a.role,
            "system_prompt": a.system_prompt,
            "tools": a.tools or [],
            "model_config": a.model_config or {},
            "order": a.order,
        }
        for a in crew.agents
    ]

    workflow_type = crew.workflow_type
    if workflow_type == "sequential":
        return build_sequential_graph(agents_data)
    elif workflow_type == "hierarchical":
        return build_hierarchical_graph(agents_data)
    elif workflow_type == "roundtable":
        max_rounds = (crew.workflow_config or {}).get("max_rounds", 2)
        return build_roundtable_graph(agents_data, max_rounds)
    else:
        raise ValueError(f"Unknown workflow type: {workflow_type}")
