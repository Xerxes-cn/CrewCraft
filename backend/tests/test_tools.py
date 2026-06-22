"""Tests for tool registry, path sandboxing, file tools, and agent tool execution."""
import os
from pathlib import Path

import pytest

from app.engine.tools import (
    Tool,
    _resolve_path,
    ReadFile,
    WriteFile,
    ListFiles,
)


class TestToolRegistry:
    def test_auto_registered(self):
        assert Tool.get("read_file") is ReadFile
        assert Tool.get("write_file") is WriteFile
        assert Tool.get("list_files") is ListFiles

    def test_get_nonexistent(self):
        assert Tool.get("no_such_tool") is None

    def test_get_openai_format(self):
        tool_cls = Tool.get("read_file")
        assert tool_cls.name == "read_file"
        assert "file_path" in tool_cls.parameters["properties"]

    def test_get_openai_definitions_by_name(self):
        defs = Tool.get_openai_definitions(["read_file", "list_files"])
        assert len(defs) == 2
        names = {d["function"]["name"] for d in defs}
        assert names == {"read_file", "list_files"}

    def test_get_openai_definitions_by_dict(self):
        defs = Tool.get_openai_definitions([{"name": "read_file"}])
        assert len(defs) == 1

    def test_get_openai_definitions_empty(self):
        assert Tool.get_openai_definitions([]) == []

    def test_get_openai_definitions_unknown_skipped(self):
        defs = Tool.get_openai_definitions(["read_file", "unknown_tool"])
        assert len(defs) == 1

    def test_list_names(self):
        names = Tool.list_names()
        assert "read_file" in names
        assert "write_file" in names
        assert "list_files" in names


class TestPathSandboxing:
    def test_normal_path(self, tmp_path):
        (tmp_path / "subdir").mkdir()
        result = _resolve_path("subdir", str(tmp_path))
        assert result == (tmp_path / "subdir")

    def test_dot_path(self, tmp_path):
        result = _resolve_path(".", str(tmp_path))
        assert result == tmp_path

    def test_traversal_raises(self, tmp_path):
        with pytest.raises(ValueError, match="越界"):
            _resolve_path("../../../etc/passwd", str(tmp_path))

    def test_absolute_path(self, tmp_path):
        with pytest.raises(ValueError, match="越界"):
            _resolve_path("/etc/passwd", str(tmp_path))

    def test_traversal_with_dots(self, tmp_path):
        with pytest.raises(ValueError):
            _resolve_path("subdir/../../../etc", str(tmp_path))


class TestReadFileTool:
    async def test_read_existing(self, tmp_path):
        (tmp_path / "test.txt").write_text("hello world", encoding="utf-8")
        result = await ReadFile().execute(file_path="test.txt", workspace=str(tmp_path))
        assert result == "hello world"

    async def test_read_nonexistent(self, tmp_path):
        result = await ReadFile().execute(file_path="missing.txt", workspace=str(tmp_path))
        assert "不存在" in result

    async def test_read_large_file(self, tmp_path):
        content = "x" * 15000
        (tmp_path / "large.txt").write_text(content, encoding="utf-8")
        result = await ReadFile().execute(file_path="large.txt", workspace=str(tmp_path))
        assert "截断" in result
        assert len(result) < 11000

    async def test_read_outside_workspace(self, tmp_path):
        result = await ReadFile().execute(file_path="../../../etc/passwd", workspace=str(tmp_path))
        assert "越界" in result or "错误" in result


class TestWriteFileTool:
    async def test_write(self, tmp_path):
        result = await WriteFile().execute(file_path="output.txt", content="written content", workspace=str(tmp_path))
        assert "written content" == (tmp_path / "output.txt").read_text("utf-8")
        assert "15" in result

    async def test_write_creates_parent_dirs(self, tmp_path):
        await WriteFile().execute(file_path="a/b/c/file.txt", content="nested", workspace=str(tmp_path))
        assert (tmp_path / "a" / "b" / "c" / "file.txt").exists()

    async def test_write_outside_workspace(self, tmp_path):
        result = await WriteFile().execute(file_path="../../../etc/hack", content="bad", workspace=str(tmp_path))
        assert "错误" in result or "越界" in result


class TestListFilesTool:
    async def test_list_root(self, tmp_path):
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.txt").write_text("b")
        (tmp_path / "sub").mkdir()
        result = await ListFiles().execute(path=".", workspace=str(tmp_path))
        assert "a.txt" in result
        assert "b.txt" in result
        assert "sub/" in result

    async def test_list_empty(self, tmp_path):
        result = await ListFiles().execute(path=".", workspace=str(tmp_path))
        assert "空" in result

    async def test_list_subdir(self, tmp_path):
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "x.txt").write_text("x")
        result = await ListFiles().execute(path="sub", workspace=str(tmp_path))
        assert "x.txt" in result

    async def test_list_nonexistent(self, tmp_path):
        result = await ListFiles().execute(path="nonexistent", workspace=str(tmp_path))
        assert "不存在" in result

    async def test_list_outside(self, tmp_path):
        result = await ListFiles().execute(path="../../../", workspace=str(tmp_path))
        assert "错误" in result or "越界" in result


class TestToolCallClassMethod:
    async def test_call_existing(self, tmp_path):
        result = await Tool.call("read_file", file_path="test.txt", workspace=str(tmp_path))
        assert "不存在" in result

    async def test_call_unknown(self):
        result = await Tool.call("no_such", x=1)
        assert "未知工具" in result

    async def test_call_missing_required_params(self):
        result = await Tool.call("write_file", workspace="/tmp")
        assert "缺少参数" in result
        assert "file_path" in result or "content" in result


class TestToolExecutionInAgent:
    """Integration tests: verify tool execution flow through agent loop."""

    async def test_agent_without_tools_uses_fast_path(self, mock_llm):
        from app.engine.agent_loop import run_agent
        agent = {"name": "Tester", "role": "测试", "tools": [], "llm_config": {}}
        result = await run_agent(agent, "say hello")
        assert result["agent_name"] == "Tester"
        assert "Mock" in result["content"]
        assert "tool_calls" not in result

    async def test_agent_without_tools_key(self, mock_llm):
        from app.engine.agent_loop import run_agent
        agent = {"name": "Tester", "role": "测试", "llm_config": {}}
        result = await run_agent(agent, "hello")
        assert result["agent_name"] == "Tester"
        assert "Mock" in result["content"]

    async def test_agent_stream_without_tools(self, mock_llm):
        from app.engine.agent_loop import run_agent_stream
        agent = {"name": "S", "role": "测试", "tools": [], "llm_config": {}}
        events = []
        async for event in run_agent_stream(agent, "hello"):
            events.append(event)
        assert events[-1]["type"] == "done"
        assert "Mock" in events[-1]["content"]

    async def test_tool_definitions_passed_to_llm(self, mock_llm, tmp_path):
        from app.engine.agent_loop import run_agent
        agent = {
            "name": "ToolUser",
            "role": "工具使用者",
            "tools": ["read_file", "write_file"],
            "llm_config": {},
            "workspace": str(tmp_path),
        }
        result = await run_agent(agent, "test task")
        assert result["agent_name"] == "ToolUser"
        assert "Mock" in result["content"]
