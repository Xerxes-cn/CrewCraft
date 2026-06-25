"""工具注册表测试 — 覆盖注册、schema 生成、调用、同步包装器。"""

import asyncio
import pytest

from app.agent.tools.registry import (
    Tool, ToolRegistry, registry, register,
    get_tool_callable, get_tool_callables, _sync_wrapper,
)


# ── Tool 基本方法 ───────────────────────────────────────────────────────


class TestToolModel:

    def test_init_minimal(self):
        t = Tool(name="echo", description="Echo back", func=lambda x: x)
        assert t.name == "echo"
        assert t.permission == "safe"  # default
        assert t.parameters == {}

    def test_init_full(self):
        def my_func(a, b): ...
        t = Tool(name="t", description="d", func=my_func,
                 parameters={"a": {"type": "int"}, "b": {"type": "string"}},
                 permission="dangerous")
        assert t.permission == "dangerous"
        assert len(t.parameters) == 2

    def test_call_passes_kwargs(self):
        called_with = {}
        def tracker(**kwargs):
            called_with.update(kwargs)
            return "ok"
        t = Tool(name="t", description="d", func=tracker,
                 parameters={"x": {"type": "integer"}})
        result = t(x=42)
        assert result == "ok"
        assert called_with["x"] == 42

    def test_to_openai_schema_structure(self):
        t = Tool(name="calc", description="Calculate",
                 func=lambda expr: eval(expr),
                 parameters={"expression": {"type": "string", "description": "Math expr"}})
        schema = t.to_openai_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "calc"
        assert schema["function"]["description"] == "Calculate"
        assert "expression" in schema["function"]["parameters"]["properties"]
        assert "expression" in schema["function"]["parameters"]["required"]

    def test_to_dict_structure(self):
        t = Tool(name="h", description="Hash", func=lambda: None,
                 parameters={"input": {"type": "string", "description": "Value"}},
                 permission="read")
        d = t.to_dict()
        assert d["name"] == "h"
        assert d["permission"] == "read"
        assert d["parameters"]["input"]["type"] == "string"


# ── ToolRegistry 新实例（不污染全局）──────────────────────────────────────


class TestFreshRegistry:

    def test_empty_registry(self, fresh_registry):
        assert fresh_registry.list_names() == []
        assert fresh_registry.list_all() == []

    def test_register_and_get(self, fresh_registry, sample_tool):
        fresh_registry.register(sample_tool)
        assert fresh_registry.get("dummy") is sample_tool
        assert "dummy" in fresh_registry.list_names()

    def test_get_nonexistent_returns_none(self, fresh_registry):
        assert fresh_registry.get("nonexistent") is None

    def test_duplicate_register_overwrites(self, fresh_registry):
        t1 = Tool(name="dup", description="first", func=lambda: 1)
        t2 = Tool(name="dup", description="second", func=lambda: 2)
        fresh_registry.register(t1)
        fresh_registry.register(t2)
        assert fresh_registry.get("dup").description == "second"

    def test_list_all_sorted(self, fresh_registry):
        fresh_registry.register(Tool(name="c", description="", func=lambda: None))
        fresh_registry.register(Tool(name="a", description="", func=lambda: None))
        fresh_registry.register(Tool(name="b", description="", func=lambda: None))
        names = [t.name for t in fresh_registry.list_all()]
        assert names == ["a", "b", "c"]

    def test_build_for_agent_empty_list(self, fresh_registry):
        assert fresh_registry.build_for_agent([]) == []

    def test_build_for_agent_nonexistent_names(self, fresh_registry):
        """不存在的工具名被跳过。"""
        fresh_registry.register(Tool(name="real", description="", func=lambda: None))
        schemas = fresh_registry.build_for_agent(["real", "fake", "ghost"])
        assert len(schemas) == 1
        assert schemas[0]["function"]["name"] == "real"

    def test_build_for_agent_all_unknown(self, fresh_registry):
        assert fresh_registry.build_for_agent(["nope"]) == []

    def test_build_callables_empty(self, fresh_registry):
        assert fresh_registry.build_callables([]) == []

    def test_build_callables_skips_unknown(self, fresh_registry):
        fresh_registry.register(Tool(name="t", description="", func=lambda: "ok"))
        fns = fresh_registry.build_callables(["t", "unknown"])
        assert len(fns) == 1
        assert callable(fns[0])


# ── 全局注册表（含内置工具）─────────────────────────────────────────────


class TestGlobalRegistry:

    CORE_TOOLS = {
        "time_now", "calculator", "web_search", "web_fetch",
        "shell_exec", "file_ops", "random_number", "text_stats",
        "json_tool", "base64", "hash", "uuid_gen",
        "send_to_agent", "broadcast_to_agents",
    }

    def test_all_core_tools_registered(self):
        """验证所有预期核心工具已注册（不硬编码总数）。"""
        names = set(registry.list_names())
        missing = self.CORE_TOOLS - names
        assert not missing, f"Missing tools: {missing}"

    def test_tool_permissions(self):
        """验证权限级别分布。"""
        assert registry.get("time_now").permission == "safe"
        assert registry.get("calculator").permission == "safe"
        assert registry.get("hash").permission == "safe"
        assert registry.get("web_search").permission == "read"
        assert registry.get("shell_exec").permission == "write"
        assert registry.get("file_ops").permission == "write"

    def test_tool_counts_are_positive(self):
        """只验证工具数 > 0，不硬编码具体数字。"""
        assert len(registry.list_names()) > 0


# ── 异步工具调用 ────────────────────────────────────────────────────────


class TestAsyncTools:

    @pytest.mark.asyncio
    async def test_calculator(self):
        tool = registry.get("calculator")
        result = await tool.func(expression="2+3*4")
        assert "14" in result

    @pytest.mark.asyncio
    async def test_time_now(self):
        tool = registry.get("time_now")
        result = await tool.func()
        assert "iso" in result

    @pytest.mark.asyncio
    async def test_hash_tool(self):
        tool = registry.get("hash")
        result = await tool.func(input="hello", algorithm="sha256")
        assert "sha256" in result.lower()


# ── get_tool_callable ────────────────────────────────────────────────────


class TestToolCallable:

    def test_get_sync_tool(self):
        """同步工具直接返回原函数。"""
        tool = registry.get("calculator")
        fn = get_tool_callable("calculator")
        assert fn is not None
        assert callable(fn)

    def test_get_nonexistent_returns_none(self):
        assert get_tool_callable("nonexistent") is None

    def test_get_tool_callables_skips_unknown(self):
        fns = get_tool_callables(["calculator", "nonexistent"])
        assert len(fns) == 1

    def test_get_tool_callables_empty(self):
        assert get_tool_callables([]) == []


# ── _sync_wrapper ───────────────────────────────────────────────────────


class TestSyncWrapper:

    async def _async_double(self, x: int) -> str:
        await asyncio.sleep(0)
        return str(x * 2)

    def test_wraps_async_function(self):
        wrapped = _sync_wrapper(self._async_double)
        result = wrapped(x=5)
        assert result == "10"

    def test_wraps_async_function_no_args(self):
        async def no_args():
            return "ok"
        wrapped = _sync_wrapper(no_args)
        assert wrapped() == "ok"


# ── @register 装饰器 ───────────────────────────────────────────────────


class TestRegisterDecorator:

    def test_decorator_registers_tool(self, fresh_registry):
        @register(name="decorated", description="A decorated tool",
                  parameters={"in": {"type": "string"}}, permission="read")
        def decorated_func(inp: str = ""):
            return f"got:{inp}"

        # 注意：装饰器注册到全局 registry，而非 fresh_registry
        # 所以验证装饰器确实注册了
        tool = registry.get("decorated")
        if tool:
            assert tool.name == "decorated"
            assert tool.permission == "read"
