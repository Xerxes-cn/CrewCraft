"""Agent 间协作工具。"""

import json

from .registry import register


@register(
    "send_to_agent",
    "向另一个 Agent 发送消息。用于 Agent 间协作：求助、传递中间结果、确认信息。",
    {
        "to": {"type": "string", "description": "目标 Agent 名称"},
        "content": {"type": "string", "description": "要发送的消息内容"},
    },
    permission="read",
)
async def send_to_agent(to: str, content: str):
    """向另一个 Agent 发送消息（通过 Gateway WebSocket 转发）。"""
    from app.agent.server import send_to_agent as _send
    success = await _send(to, content)
    if success:
        return f"消息已发送给 {to}"
    else:
        return f"发送失败：{to} 不在线或连接已断开"


@register(
    "broadcast_to_agents",
    "向所有其他在线 Agent 广播消息。",
    {
        "content": {"type": "string", "description": "要广播的消息内容"},
    },
    permission="read",
)
async def broadcast_to_agents(content: str):
    """向所有其他 Agent 广播消息。"""
    from app.agent.server import _current_ws, _current_session_id
    import json as _json
    if _current_ws is None:
        return "广播失败：未连接到 Gateway"
    await _current_ws.send(_json.dumps({
        "type": "agent_broadcast",
        "session_id": _current_session_id,
        "content": content,
    }))
    return "广播已发送"
