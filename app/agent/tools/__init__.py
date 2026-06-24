"""Agent 工具包。

导入所有工具模块以触发注册，然后重新导出注册表和辅助函数供外部使用。

可用工具（14 个）：
    web       — web_search, web_fetch
    system    — shell_exec, file_ops
    utility   — time_now, calculator, random_number, text_stats,
                json_tool, base64, hash, uuid_gen
    collab    — send_to_agent, broadcast_to_agents
"""

from .registry import (
    Tool,
    ToolRegistry,
    registry,
    register,
    get_tool_callable,
    get_tool_callables,
)

from . import web       # noqa: F401
from . import system    # noqa: F401
from . import utility   # noqa: F401
from . import collab    # noqa: F401

__all__ = [
    "Tool",
    "ToolRegistry",
    "registry",
    "register",
    "get_tool_callable",
    "get_tool_callables",
]
