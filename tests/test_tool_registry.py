"""工具注册表测试。"""

import asyncio
from app.agent.tools.registry import Tool, ToolRegistry, get_tool_callable, get_tool_callables, registry


def test_tool_registration():
    """测试工具注册。"""
    names = registry.list_names()
    assert "time_now" in names
    assert "calculator" in names
    assert "web_search" in names
    assert "shell_exec" in names
    assert "send_to_agent" in names
    assert len(names) == 14


def test_tool_schema():
    """测试 OpenAI schema 生成。"""
    schemas = registry.build_for_agent(["calculator", "time_now"])
    assert len(schemas) == 2
    for s in schemas:
        assert s["type"] == "function"
        assert "name" in s["function"]
        assert "description" in s["function"]


def test_tool_permissions():
    """测试工具权限级别。"""
    assert registry.get("time_now").permission == "safe"
    assert registry.get("web_search").permission == "read"
    assert registry.get("shell_exec").permission == "write"
    assert registry.get("file_ops").permission == "write"


def test_tool_callables():
    """测试获取可调用工具。"""
    tools = get_tool_callables(["calculator"])
    assert len(tools) == 1
    assert callable(tools[0])


async def test_calculator():
    """测试 calculator 工具。"""
    tool = registry.get("calculator")
    result = await tool.func(expression="2+3*4")
    assert "14" in result


async def test_time_now():
    """测试 time_now 工具。"""
    tool = registry.get("time_now")
    result = await tool.func()
    assert "iso" in result


def test_tool_dict():
    """测试 Tool.to_dict()。"""
    tool = registry.get("hash")
    d = tool.to_dict()
    assert d["name"] == "hash"
    assert d["permission"] == "safe"
    assert "input" in d["parameters"]
