"""Agent tools package.

Import all tool modules to trigger registration, then re-export
the registry and helpers for external use.

Available tools (12):
    web       — web_search, web_fetch
    system    — shell_exec, file_ops
    utility   — time_now, calculator, random_number, text_stats,
                json_tool, base64, hash, uuid_gen
"""

from .registry import (
    Tool,
    ToolRegistry,
    registry,
    register,
    get_tool_callable,
    get_tool_callables,
)

# Import tool modules to trigger @register decorators
from . import web       # noqa: F401
from . import system    # noqa: F401
from . import utility   # noqa: F401

__all__ = [
    "Tool",
    "ToolRegistry",
    "registry",
    "register",
    "get_tool_callable",
    "get_tool_callables",
]
