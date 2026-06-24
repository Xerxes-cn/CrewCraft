"""内置编排器 Agent。

在网关进程内运行（不作为子进程）。接收没有指定目标 Agent 的任务，
分析任务内容，并将其分派给最合适的已注册 Agent。

流程：
    1. 用户提交任务 → 编排器接收
    2. 编排器分析任务 + 读取 Agent 描述
    3. 编排器决定使用哪个/哪些 Agent
    4. 通过 WS 管理器分派子任务
    5. 收集结果、验证、返回给用户
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
    """内置 Agent，将任务路由到最合适的子 Agent。"""

    def __init__(self, agent_manager, ws_manager):
        self._am = agent_manager
        self._ws = ws_manager

    def _build_agent_list(self) -> str:
        """构建可用 Agent 的描述列表，用于提示词。"""
        agents = self._am.list_configs()
        # 排除自身
        agents = [a for a in agents if a.name != ORCHESTRATOR_NAME]
        if not agents:
            return "(no agents configured)"

        lines = []
        for a in agents:
            desc = a.description or "(no description)"
            lines.append(f"- {a.name}: {desc} (model: {a.model})")
        return "\n".join(lines)

    async def _plan(self, content: str) -> dict:
        """请求 LLM 为任务创建分派计划。"""
        agent_list = self._build_agent_list()

        try:
            from langchain.chat_models import init_chat_model
            llm = init_chat_model("openai:gpt-4o-mini")
            prompt = ORCHESTRATOR_PROMPT.format(agent_list=agent_list)
            full = f"{prompt}\n\nTask: {content}"
            response = await llm.ainvoke(full)
            text = response.content if hasattr(response, "content") else str(response)

            # 从响应中提取 JSON
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
        """处理任务 — 规划并分派给子 Agent。

        返回包含 task_id 和 session_id 的字典，用于状态跟踪。
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

        # 分派子任务
        results = []
        for item in sub_tasks:
            agent_name = item["agent"]
            sub_content = item["task"]

            if not self._am.load_config(agent_name):
                logger.warning(f"Agent '{agent_name}' not found, skipping")
                continue

            # 确保 Agent 正在运行
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


# 单例
_orchestrator: Orchestrator | None = None


def get_orchestrator(agent_manager=None, ws_manager=None) -> Orchestrator:
    global _orchestrator
    if _orchestrator is None and agent_manager and ws_manager:
        _orchestrator = Orchestrator(agent_manager, ws_manager)
        logger.info("Orchestrator initialized")
    return _orchestrator
