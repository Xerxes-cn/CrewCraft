import json
from collections.abc import AsyncGenerator

from app.llm.manager import llm
from app.engine.tools import Tool

MAX_TOOL_ITERATIONS = 10


def build_messages(agent: dict, task_input: str, context: str = "") -> list[dict]:
    system_content = agent.get("system_prompt") or f"你是{agent['name']}，{agent['role']}。"
    if agent.get("workspace"):
        system_content += f"\n\n你的独立工作目录为：{agent['workspace']}。你可以在此目录中读写文件，该目录与其他智能体隔离。"

    messages = [{"role": "system", "content": system_content}]

    if context:
        messages.append({"role": "user", "content": f"之前步骤的上下文：\n{context}"})

    messages.append({"role": "user", "content": task_input})
    return messages


async def run_agent(agent: dict, task_input: str, context: str = "") -> dict:
    messages = build_messages(agent, task_input, context)
    llm_config = agent.get("llm_config") or {}
    tool_defs = Tool.get_openai_definitions(agent.get("tools", []))
    workspace = agent.get("workspace", "")
    temp = llm_config.get("temperature", 0.7)
    max_tok = llm_config.get("max_tokens", 4096)

    if not tool_defs:
        # Fast path: no tools, backward-compatible
        response = await llm.chat_completion(messages=messages, temperature=temp, max_tokens=max_tok)
        return {"agent_name": agent["name"], "agent_role": agent["role"], "content": response}

    # Tool loop
    all_tool_calls = []
    for _ in range(MAX_TOOL_ITERATIONS):
        msg = await llm.chat_completion_raw(messages=messages, temperature=temp, max_tokens=max_tok, tools=tool_defs)

        if msg.tool_calls:
            assistant_msg = {
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in msg.tool_calls
                ],
            }
            messages.append(assistant_msg)

            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}
                result = await Tool.call(tc.function.name, **args, workspace=workspace)
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
                all_tool_calls.append({
                    "name": tc.function.name,
                    "arguments": args,
                    "result": result,
                })
        else:
            content = msg.content or ""
            result = {"agent_name": agent["name"], "agent_role": agent["role"], "content": content}
            if all_tool_calls:
                result["tool_calls"] = all_tool_calls
            return result

    return {"agent_name": agent["name"], "agent_role": agent["role"],
            "content": "[已达到工具调用最大次数]", "tool_calls": all_tool_calls}


async def run_agent_stream(
    agent: dict, task_input: str, context: str = ""
) -> AsyncGenerator[dict, None]:
    messages = build_messages(agent, task_input, context)
    llm_config = agent.get("llm_config") or {}
    tool_defs = Tool.get_openai_definitions(agent.get("tools", []))
    workspace = agent.get("workspace", "")
    temp = llm_config.get("temperature", 0.7)
    max_tok = llm_config.get("max_tokens", 4096)

    if not tool_defs:
        # Fast path: no tools, backward-compatible streaming
        full_response = ""
        async for chunk in llm.chat_completion_stream(messages=messages, temperature=temp, max_tokens=max_tok):
            full_response += chunk
            yield {"type": "chunk", "agent_name": agent["name"], "content": chunk}
        yield {"type": "done", "agent_name": agent["name"], "agent_role": agent["role"], "content": full_response}
        return

    # Tool loop with streaming
    for _ in range(MAX_TOOL_ITERATIONS):
        tool_calls_acc: dict[int, dict] = {}
        content_acc = ""

        async for raw_chunk in llm.chat_completion_stream_raw(messages=messages, temperature=temp, max_tokens=max_tok, tools=tool_defs):
            delta = raw_chunk.choices[0].delta if raw_chunk.choices else None
            if not delta:
                continue

            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in tool_calls_acc:
                        tool_calls_acc[idx] = {"id": "", "name": "", "arguments": ""}
                    if tc_delta.id:
                        tool_calls_acc[idx]["id"] += tc_delta.id
                    if tc_delta.function:
                        if tc_delta.function.name:
                            tool_calls_acc[idx]["name"] += tc_delta.function.name
                        if tc_delta.function.arguments:
                            tool_calls_acc[idx]["arguments"] += tc_delta.function.arguments
            elif delta.content:
                content_acc += delta.content
                yield {"type": "chunk", "agent_name": agent["name"], "content": delta.content}

        if tool_calls_acc:
            openai_tool_calls = []
            for idx in sorted(tool_calls_acc):
                tc = tool_calls_acc[idx]
                openai_tool_calls.append({
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": tc["arguments"]},
                })

            messages.append({
                "role": "assistant",
                "content": None,
                "tool_calls": openai_tool_calls,
            })

            for idx in sorted(tool_calls_acc):
                tc = tool_calls_acc[idx]
                try:
                    args = json.loads(tc["arguments"])
                except json.JSONDecodeError:
                    args = {}
                yield {"type": "tool_call", "agent_name": agent["name"],
                       "tool_name": tc["name"], "arguments": args}

                tool_result = await Tool.call(tc["name"], **args, workspace=workspace)
                messages.append({"role": "tool", "tool_call_id": tc["id"], "content": tool_result})
                yield {"type": "tool_result", "agent_name": agent["name"],
                       "tool_name": tc["name"], "result": tool_result}
        else:
            yield {"type": "done", "agent_name": agent["name"], "agent_role": agent["role"], "content": content_acc}
            return

    yield {"type": "done", "agent_name": agent["name"], "agent_role": agent["role"],
           "content": "[已达到工具调用最大次数]"}
