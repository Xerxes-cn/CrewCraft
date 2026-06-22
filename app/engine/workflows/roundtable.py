"""Roundtable discussion workflow using CrewAI Agents."""
from __future__ import annotations

from collections.abc import AsyncGenerator

from app.llm.manager import llm


async def run_roundtable_stream(
    agents: list[dict],
    task_input: str,
    max_rounds: int = 2,
) -> AsyncGenerator[dict, None]:
    """Run roundtable discussion: all agents discuss in rounds, then summarize.

    Uses the LLM directly for flexible discussion control.
    Yields events: {type: "agent_message"|"agent_chunk"|"done", ...}
    """
    discussion: list[str] = []

    for round_num in range(max_rounds):
        for agent in agents:
            agent_name = agent["name"]
            agent_role = agent["role"]
            system_prompt = agent.get("system_prompt") or f"你是{agent_name}，{agent_role}。"
            llm_config = agent.get("llm_config") or {}
            temp = llm_config.get("temperature", 0.7)
            max_tok = llm_config.get("max_tokens", 4096)

            # Build discussion context
            discussion_context = ""
            if discussion:
                previous = "\n".join(discussion)
                discussion_context = f"之前的讨论：\n{previous}\n\n"

            user_msg = f"{discussion_context}任务：{task_input}\n\n请分享你的观点和分析。"

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
            ]

            # Stream agent response
            full = ""
            async for chunk in llm.chat_completion_stream(
                messages=messages, temperature=temp, max_tokens=max_tok
            ):
                full += chunk
                yield {
                    "type": "chunk",
                    "agent_name": agent_name,
                    "agent_role": agent_role,
                    "content": chunk,
                }

            discussion.append(f"[{agent_name}（{agent_role}）]: {full}")
            yield {
                "type": "done",
                "agent_name": agent_name,
                "agent_role": agent_role,
                "content": full,
            }

    # Summarize
    full_discussion = "\n".join(discussion)
    summary_prompt = f"基于以下讨论，请总结各方观点并给出共识建议：\n\n{full_discussion}"

    summary_messages = [
        {"role": "system", "content": "你是一位专业的会议总结者，请客观总结各方观点。150字以内。"},
        {"role": "user", "content": summary_prompt},
    ]

    summary = await llm.chat_completion(
        messages=summary_messages, temperature=0.3, max_tokens=512
    )

    yield {
        "type": "done",
        "agent_name": "Summary",
        "agent_role": "Summarizer",
        "content": summary,
    }
