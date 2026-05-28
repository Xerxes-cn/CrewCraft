from collections.abc import AsyncGenerator

from app.llm.deepseek import chat_completion, chat_completion_stream


def build_messages(agent: dict, task_input: str, context: str = "") -> list[dict]:
    system_content = agent.get("system_prompt") or f"You are {agent['name']}, a {agent['role']}."
    messages = [{"role": "system", "content": system_content}]

    if context:
        messages.append({"role": "user", "content": f"Context from previous step:\n{context}"})

    messages.append({"role": "user", "content": task_input})
    return messages


async def run_agent(agent: dict, task_input: str, context: str = "") -> dict:
    messages = build_messages(agent, task_input, context)
    model_config = agent.get("model_config") or {}
    response = await chat_completion(
        messages=messages,
        temperature=model_config.get("temperature", 0.7),
        max_tokens=model_config.get("max_tokens", 4096),
    )
    return {"agent_name": agent["name"], "agent_role": agent["role"], "content": response}


async def run_agent_stream(
    agent: dict, task_input: str, context: str = ""
) -> AsyncGenerator[dict, None]:
    messages = build_messages(agent, task_input, context)
    model_config = agent.get("model_config") or {}
    full_response = ""
    async for chunk in chat_completion_stream(
        messages=messages,
        temperature=model_config.get("temperature", 0.7),
        max_tokens=model_config.get("max_tokens", 4096),
    ):
        full_response += chunk
        yield {"type": "chunk", "agent_name": agent["name"], "content": chunk}

    yield {"type": "done", "agent_name": agent["name"], "agent_role": agent["role"], "content": full_response}
