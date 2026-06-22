"""Tool system for agent function calling — class-based with auto-registration."""
from __future__ import annotations

from pathlib import Path

from crewai.tools import BaseTool as CrewAIBaseTool


# --- Path sandboxing ---


def _resolve_path(user_path: str, workspace: str) -> Path:
    ws = Path(workspace).resolve()
    target = (ws / user_path).resolve()
    if not str(target).startswith(str(ws)):
        raise ValueError(f"路径越界: {user_path}")
    return target


# --- Base Tool ---


class Tool:
    """Base class for all tools. Subclass to auto-register.

    Define `name`, `description`, `parameters` as class attributes and
    implement `execute(**kwargs) -> str`. The class is registered automatically
    via __init_subclass__ as long as `name` is set.
    """

    name: str = ""
    description: str = ""
    parameters: dict = {}

    _tools: dict[str, type["Tool"]] = {}

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        if cls.name:
            Tool._tools[cls.name] = cls

    @classmethod
    def get(cls, name: str) -> type["Tool"] | None:
        return cls._tools.get(name)

    @classmethod
    def list_names(cls) -> list[str]:
        return list(cls._tools.keys())

    @classmethod
    async def call(cls, name: str, **kwargs: object) -> str:
        """Lookup tool by name, instantiate, and call execute with given kwargs."""
        tool_cls = cls.get(name)
        if not tool_cls:
            return f"未知工具: {name}"
        # Filter out None/invalid kwargs that don't match the tool's parameter schema
        valid_params = tool_cls.parameters.get("properties", {}).keys()
        filtered = {k: v for k, v in kwargs.items() if k in valid_params or k == "workspace"}
        # Check required params
        required = set(tool_cls.parameters.get("required", []))
        missing = required - set(filtered.keys())
        if missing:
            return f"错误: 调用 {name} 缺少参数: {', '.join(sorted(missing))}"
        return await tool_cls().execute(**filtered)

    @classmethod
    def get_openai_definitions(cls, agent_tool_configs: list) -> list[dict]:
        """Resolve agent tool config to OpenAI-compatible function definitions."""
        if not agent_tool_configs:
            return []
        result: list[dict] = []
        for cfg in agent_tool_configs:
            name = cfg if isinstance(cfg, str) else cfg.get("name", "")
            tool_cls = cls._tools.get(name)
            if tool_cls:
                result.append({
                    "type": "function",
                    "function": {
                        "name": tool_cls.name,
                        "description": tool_cls.description,
                        "parameters": tool_cls.parameters,
                    },
                })
        return result

    async def execute(self, **kwargs: object) -> str:
        raise NotImplementedError


# --- File Tools ---


class ReadFile(Tool):
    name = "read_file"
    description = "读取工作目录中的文件内容"
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "要读取的文件路径（相对于工作目录）",
            },
        },
        "required": ["file_path"],
    }

    async def execute(self, file_path: str, workspace: str = "") -> str:
        try:
            target = _resolve_path(file_path, workspace)
            if not target.exists():
                return f"错误: 文件不存在: {file_path}"
            if not target.is_file():
                return f"错误: 路径不是文件: {file_path}"
            content = target.read_text(encoding="utf-8")
            if len(content) > 10000:
                content = content[:10000] + "\n...(内容已截断)"
            return content
        except ValueError as e:
            return f"错误: {e}"
        except Exception as e:
            return f"读取文件失败: {e}"


class WriteFile(Tool):
    name = "write_file"
    description = "在工作目录中创建或覆盖文件"
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "要写入的文件路径（相对于工作目录）",
            },
            "content": {
                "type": "string",
                "description": "要写入的文件内容",
            },
        },
        "required": ["file_path", "content"],
    }

    async def execute(self, file_path: str, content: str, workspace: str = "") -> str:
        try:
            target = _resolve_path(file_path, workspace)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            return f"已写入 {len(content)} 个字符到 {file_path}"
        except ValueError as e:
            return f"错误: {e}"
        except Exception as e:
            return f"写入文件失败: {e}"


class ListFiles(Tool):
    name = "list_files"
    description = "列出工作目录中的文件和子目录"
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "要列出内容的目录路径（相对于工作目录），默认为当前目录",
                "default": ".",
            },
        },
    }

    async def execute(self, path: str = ".", workspace: str = "") -> str:
        try:
            target = _resolve_path(path, workspace)
            if not target.exists():
                return f"错误: 目录不存在: {path}"
            if not target.is_dir():
                return f"错误: 路径不是目录: {path}"
            entries = []
            for entry in sorted(target.iterdir()):
                suffix = "/" if entry.is_dir() else ""
                size = ""
                if entry.is_file():
                    try:
                        s = entry.stat().st_size
                        if s < 1024:
                            size = f" ({s}B)"
                        elif s < 1024 * 1024:
                            size = f" ({s / 1024:.1f}KB)"
                        else:
                            size = f" ({s / (1024 * 1024):.1f}MB)"
                    except OSError:
                        pass
                entries.append(f"  {entry.name}{suffix}{size}")
            if not entries:
                return f"目录为空: {path}"
            return f"目录 {path} 的内容:\n" + "\n".join(entries)
        except ValueError as e:
            return f"错误: {e}"
        except Exception as e:
            return f"列出文件失败: {e}"


# --- CrewAI-compatible tool wrappers ---


def _make_crewai_tool(tool_cls: type[Tool]) -> type[CrewAIBaseTool]:
    """Dynamically create a CrewAI BaseTool subclass from a Tool class."""

    class _CrewAIAdaptedTool(CrewAIBaseTool):
        name: str = tool_cls.name
        description: str = tool_cls.description

        async def _run(self, **kwargs) -> str:
            return await tool_cls().execute(**kwargs)

    _CrewAIAdaptedTool.__name__ = f"CrewAI{tool_cls.name}"
    return _CrewAIAdaptedTool


def get_crewai_tools(names: list[str]) -> list[CrewAIBaseTool]:
    """Get instantiated CrewAI-compatible tools by name."""
    tools: list[CrewAIBaseTool] = []
    for name in names:
        tool_cls = Tool.get(name)
        if tool_cls:
            tools.append(_make_crewai_tool(tool_cls)())
    return tools
