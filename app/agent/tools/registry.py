"""工具注册表 — 核心类、装饰器和同步包装器。"""

import asyncio
import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class Tool:
    """一个带有元数据的可调用工具，用于注册。"""

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
        """转换为 OpenAI 兼容的函数 schema。"""
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
    """所有可用工具的注册表。"""

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
        """构建工具 schema 列表，用于传递给 deepagents。"""
        schemas = []
        for name in tool_names:
            tool = self._tools.get(name)
            if tool:
                schemas.append(tool.to_openai_schema())
        return schemas

    def build_callables(self, tool_names: list[str]) -> list[Callable]:
        """构建可调用函数列表，用于传递给 deepagents。"""
        return [self._tools[name].func for name in tool_names if name in self._tools]


# 单例注册表
registry = ToolRegistry()


def register(name: str, description: str, parameters: dict = None):
    """装饰器，用于将函数注册为一个工具。"""

    def decorator(func):
        tool = Tool(name=name, description=description, func=func, parameters=parameters)
        registry.register(tool)
        return func

    return decorator


# ── 同步包装器 ───────────────────────────────────────────────────────────

def _sync_wrapper(async_func):
    """将异步函数包装为同步函数，供 deepagents 使用。"""

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
    """按名称获取工具的同步可调用对象，可直接用于 deepagents。"""
    tool = registry.get(name)
    if not tool:
        return None

    func = tool.func
    if asyncio.iscoroutinefunction(func):
        return _sync_wrapper(func)
    return func


def get_tool_callables(names: list[str]) -> list[Callable]:
    """获取给定名称列表的同步可调用对象。"""
    tools = []
    for name in names:
        fn = get_tool_callable(name)
        if fn:
            tools.append(fn)
    return tools
