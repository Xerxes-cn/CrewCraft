"""Tool registry — core classes, decorator, and sync wrappers."""

import asyncio
import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class Tool:
    """A callable tool with metadata for registration."""

    def __init__(
        self,
        name: str,
        description: str,
        func: Callable,
        parameters: dict = None,
    ):
        self.name = name
        self.description = description
        self.func = func
        self.parameters = parameters or {}

    def __call__(self, **kwargs):
        return self.func(**kwargs)

    def to_openai_schema(self) -> dict:
        """Convert to OpenAI-compatible function schema."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.parameters,
                    "required": list(self.parameters.keys()),
                },
            },
        }

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                k: {"type": v.get("type", "string"), "description": v.get("description", "")}
                for k, v in self.parameters.items()
            },
        }


class ToolRegistry:
    """Registry of all available tools."""

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool):
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def list_all(self) -> list[Tool]:
        return sorted(self._tools.values(), key=lambda t: t.name)

    def list_names(self) -> list[str]:
        return sorted(self._tools.keys())

    def build_for_agent(self, tool_names: list[str]) -> list:
        """Build a list of tool schemas for passing to deepagents."""
        schemas = []
        for name in tool_names:
            tool = self._tools.get(name)
            if tool:
                schemas.append(tool.to_openai_schema())
        return schemas

    def build_callables(self, tool_names: list[str]) -> list[Callable]:
        """Build a list of callable functions for passing to deepagents."""
        return [self._tools[name].func for name in tool_names if name in self._tools]


# Singleton registry
registry = ToolRegistry()


def register(name: str, description: str, parameters: dict = None):
    """Decorator to register a function as a tool."""

    def decorator(func):
        tool = Tool(name=name, description=description, func=func, parameters=parameters)
        registry.register(tool)
        return func

    return decorator


# ── Sync wrappers ──────────────────────────────────────────────────────

def _sync_wrapper(async_func):
    """Wrap an async function into a sync function for deepagents."""

    def wrapper(**kwargs):
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, async_func(**kwargs))
                    return future.result(timeout=30)
            else:
                return asyncio.run(async_func(**kwargs))
        except RuntimeError:
            return asyncio.run(async_func(**kwargs))

    return wrapper


def get_tool_callable(name: str) -> Optional[Callable]:
    """Get a sync callable for a tool by name, ready for deepagents."""
    tool = registry.get(name)
    if not tool:
        return None

    func = tool.func
    if asyncio.iscoroutinefunction(func):
        return _sync_wrapper(func)
    return func


def get_tool_callables(names: list[str]) -> list[Callable]:
    """Get sync callables for a list of tool names."""
    tools = []
    for name in names:
        fn = get_tool_callable(name)
        if fn:
            tools.append(fn)
    return tools
