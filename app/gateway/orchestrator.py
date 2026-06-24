"""Built-in orchestrator agent.

Runs inside the gateway process (not as a subprocess). Receives tasks
without a target agent, analyzes them, and dispatches sub-tasks to
the most appropriate registered agents.

Flow:
    1. User submits task → orchestrator receives it
    2. Orchestrator analyzes task + reads agent descriptions
    3. Orchestrator decides which agent(s) to use
    4. Sub-tasks dispatched via WS manager
    5. Results collected, verified, returned to user
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

ORCHESTRATOR_NAME = "_orchestrator"

ORCHESTRATOR_PROMPT = """You are an AI task orchestrator. Your job is to analyze incoming tasks
and decide how to delegate them to the available agents.

For each task:
1. Read the task description carefully
2. Review the available agents and their capabilities
3. Decide which agent should handle this task
4. If the task requires multiple steps, break it down
5. Return a JSON dispatch plan

Available agents:
{agent_list}

Return ONLY a JSON object with this structure:
{{
    "plan": [
        {{
            "agent": "agent_name",
            "task": "sub-task description",
            "reason": "why this agent was chosen"
        }}
    ]
}}

If no agent fits, return: {{"error": "reason"}}"""


class Orchestrator:
    """Built-in agent that routes tasks to the best-suited sub-agent."""

    def __init__(self, agent_manager, ws_manager):
        self._am = agent_manager
        self._ws = ws_manager

    def _build_agent_list(self) -> str:
        """Build a description of available agents for the prompt."""
        agents = self._am.list_configs()
        # Exclude self
        agents = [a for a in agents if a.name != ORCHESTRATOR_NAME]
        if not agents:
            return "(no agents configured)"

        lines = []
        for a in agents:
            desc = a.description or "(no description)"
            lines.append(f"- {a.name}: {desc} (model: {a.model})")
        return "\n".join(lines)

    async def _plan(self, content: str) -> dict:
        """Ask LLM to create a dispatch plan for the task."""
        agent_list = self._build_agent_list()

        try:
            from langchain.chat_models import init_chat_model
            llm = init_chat_model("openai:gpt-4o-mini")
            prompt = ORCHESTRATOR_PROMPT.format(agent_list=agent_list)
            full = f"{prompt}\n\nTask: {content}"
            response = await llm.ainvoke(full)
            text = response.content if hasattr(response, "content") else str(response)

            # Extract JSON from response
            text = text.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]

            plan = json.loads(text)
            logger.info(f"Orchestrator plan: {json.dumps(plan, indent=2)}")
            return plan
        except Exception as e:
            logger.warning(f"Orchestrator LLM planning failed: {e}")
            return {"plan": [], "error": str(e)}

    async def handle_task(self, content: str) -> dict:
        """Handle a task — plan and dispatch to sub-agents.

        Returns a dict with task_id and session_id for status tracking.
        """
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        session_id = str(uuid.uuid4())

        plan = await self._plan(content)

        if plan.get("error"):
            logger.error(f"Orchestrator failed: {plan['error']}")
            return {
                "task_id": task_id,
                "session_id": session_id,
                "status": "failed",
                "error": plan["error"],
            }

        sub_tasks = plan.get("plan", [])
        if not sub_tasks:
            return {
                "task_id": task_id,
                "session_id": session_id,
                "status": "failed",
                "error": "No suitable agent found for this task",
            }

        # Dispatch sub-tasks
        results = []
        for item in sub_tasks:
            agent_name = item["agent"]
            sub_content = item["task"]

            if not self._am.load_config(agent_name):
                logger.warning(f"Agent '{agent_name}' not found, skipping")
                continue

            # Ensure agent is running
            if not self._am.is_online(agent_name):
                await self._am.start_agent(agent_name)
                for _ in range(20):
                    if self._am.is_online(agent_name):
                        break
                    await asyncio.sleep(0.5)

            try:
                info = await self._ws.dispatch_task(agent_name, sub_content)
                results.append({
                    "agent": agent_name,
                    "task_id": info["task_id"],
                    "status": "dispatched",
                })
            except Exception as e:
                results.append({
                    "agent": agent_name,
                    "status": "error",
                    "error": str(e),
                })

        return {
            "task_id": task_id,
            "session_id": session_id,
            "status": "pending",
            "plan": results,
        }


# Singleton
_orchestrator: Orchestrator | None = None


def get_orchestrator(agent_manager=None, ws_manager=None) -> Orchestrator:
    global _orchestrator
    if _orchestrator is None and agent_manager and ws_manager:
        _orchestrator = Orchestrator(agent_manager, ws_manager)
        logger.info("Orchestrator initialized")
    return _orchestrator
