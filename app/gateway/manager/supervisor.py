"""协作监督 Agent — 监控 Agent 间消息，判断是否放行/警告/拦截。

支持三种模式：
- llm: 每条消息都调用 LLM 判断
- hybrid: 硬规则先拦截明显越界的，通过的交 LLM
- sampling: 硬规则始终生效，接近限制时额外启用 LLM
"""

import json
import logging

logger = logging.getLogger(__name__)

SUPERVISOR_PROMPT = """You are a collaboration supervisor. Your job is to monitor agent-to-agent communication and decide whether to allow, warn, or halt the collaboration.

Context:
- Session ID: {session_id}
- From: {from_agent}
- To: {to_agent}
- Round: {round}/{max_rounds}
- Chain depth: {chain_depth}/{max_depth}
- Elapsed: {elapsed}s/{timeout}s
- Chain: {chain}
- Content: {content}

Analyze the collaboration:
1. Is this collaboration making progress or going in circles?
2. Is the chain depth appropriate for the task?
3. Has the conversation timed out?
4. Is there dangerous, harmful, or inappropriate content?
5. Is the agent loop efficient or wasteful?

Return ONLY a JSON object with exactly this structure:
{{"action": "allow|warn|halt", "reason": "brief explanation in the same language as the content"}}

If everything is fine, return "allow". Use "warn" for minor concerns and "halt" only for serious issues."""


class Supervisor:
    """内置监督 Agent，通过 LLM 判断协作是否正常。"""

    def __init__(self):
        pass

    async def check(
        self, session: dict, from_agent: str, to_agent: str, content: str
    ) -> dict | None:
        """调用 LLM 判断协作消息。返回 None 表示放行，dict 表示拦截/警告。"""
        from app.config import config

        elapsed = 0.0
        started_at = session.get("started_at", 0)
        if started_at:
            import asyncio
            elapsed = asyncio.get_event_loop().time() - started_at

        prompt = SUPERVISOR_PROMPT.format(
            session_id=session.get("session_id", ""),
            from_agent=from_agent,
            to_agent=to_agent,
            round=session.get("round", 0),
            max_rounds=config.collab_max_rounds,
            chain_depth=len(session.get("chain", [])),
            max_depth=config.collab_max_depth,
            elapsed=f"{elapsed:.0f}",
            timeout=config.collab_timeout,
            chain=" → ".join(session.get("chain", [])),
            content=content[:2000],  # 截断避免 token 超限
        )

        try:
            from langchain.chat_models import init_chat_model
            llm = init_chat_model("openai:gpt-4o-mini")
            response = await llm.ainvoke(prompt)
            text = response.content if hasattr(response, "content") else str(response)

            # 提取 JSON
            text = text.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]

            result = json.loads(text)
            action = result.get("action", "allow")

            if action == "allow":
                return None  # 放行

            return {
                "type": "supervisor",
                "action": action,
                "reason": result.get("reason", ""),
                "session_id": session.get("session_id", ""),
            }

        except Exception as e:
            logger.warning(f"Supervisor LLM check failed, allowing by default: {e}")
            return None  # LLM 挂了就放行，避免阻塞协作
