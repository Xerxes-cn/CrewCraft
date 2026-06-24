"""Agent tools library.

Provides commonly used tools that can be attached to agent configurations.
Each tool is a callable with metadata for registration and discovery.
"""

import asyncio
import base64 as _base64
import hashlib
import json
import logging
import math
import os
import random
import re
import subprocess
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# ── Tool metadata ───────────────────────────────────────────────────────

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
                name: {"type": info.get("type", "string"), "description": info.get("description", "")}
                for name, info in self.parameters.items()
            },
        }


# ── Tool registry ────────────────────────────────────────────────────────

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


registry = ToolRegistry()


def register(name: str, description: str, parameters: dict = None):
    """Decorator to register a function as a tool."""
    def decorator(func):
        tool = Tool(name=name, description=description, func=func, parameters=parameters)
        registry.register(tool)
        return func
    return decorator


# ── Tool implementations ─────────────────────────────────────────────────

# 1. web_fetch — Fetch URL content
@register(
    "web_fetch",
    "Fetch content from a URL and return the text. Use for reading web pages, APIs, or any HTTP resource.",
    {
        "url": {"type": "string", "description": "The URL to fetch"},
        "method": {"type": "string", "description": "HTTP method: GET or POST"},
        "body": {"type": "string", "description": "Request body (for POST, JSON string)"},
    },
)
async def web_fetch(url: str, method: str = "GET", body: str = ""):
    """Fetch a URL and return its text content."""
    import httpx
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        if method.upper() == "POST":
            kwargs = {"content": body} if body else {"json": json.loads(body) if body else {}}
            resp = await client.post(url, **kwargs)
        else:
            resp = await client.get(url)
        resp.raise_for_status()
        text = resp.text[:10000]  # Truncate to 10k chars
        if len(resp.text) > 10000:
            text += f"\n... [truncated, original length: {len(resp.text)}]"
        return text


# 2. web_search — Search via DuckDuckGo HTML (no API key)
@register(
    "web_search",
    "Search the web. Returns titles, snippets, and URLs for the given query.",
    {
        "query": {"type": "string", "description": "Search query"},
        "max_results": {"type": "integer", "description": "Maximum number of results (default 5)"},
    },
)
async def web_search(query: str, max_results: int = 5):
    """Search the web using DuckDuckGo HTML (no API key required)."""
    import httpx
    from html import unescape

    url = "https://html.duckduckgo.com/html/"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, data={"q": query})
        resp.raise_for_status()

    # Simple HTML extraction for results
    results = []
    # Extract result blocks
    blocks = re.findall(r'<a rel="nofollow" class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>', resp.text)
    snippets = re.findall(r'<a class="result__snippet"[^>]*>(.*?)</a>', resp.text)

    for i, (href, title) in enumerate(blocks[:max_results]):
        title_clean = unescape(re.sub(r'<[^>]+>', '', title)).strip()
        snippet_clean = unescape(re.sub(r'<[^>]+>', '', snippets[i] if i < len(snippets) else "")).strip()
        results.append({
            "title": title_clean,
            "url": unescape(href),
            "snippet": snippet_clean,
        })

    if not results:
        return f"No results found for '{query}'."

    return json.dumps(results, indent=2, ensure_ascii=False)


# 3. time_now — Current date/time
@register(
    "time_now",
    "Get the current date and time. Returns ISO format, unix timestamp, and human-readable formats.",
    {
        "tz": {"type": "string", "description": "Timezone name, e.g. 'Asia/Shanghai', 'UTC' (default: system local)"},
    },
)
async def time_now(tz: str = ""):
    """Return the current date/time in multiple formats."""
    now = datetime.now(timezone.utc)

    try:
        import zoneinfo
        if tz:
            zone = zoneinfo.ZoneInfo(tz)
            now = datetime.now(zone)
    except Exception:
        pass

    return json.dumps({
        "iso": now.isoformat(),
        "unix": int(now.timestamp()),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "weekday": now.strftime("%A"),
        "tz": str(now.tzinfo) if now.tzinfo else "system",
    }, indent=2)


# 4. calculator — Safe math expression evaluator
@register(
    "calculator",
    "Safely evaluate a mathematical expression. Supports +, -, *, /, **, %, sqrt, sin, cos, log, abs, etc.",
    {
        "expression": {"type": "string", "description": "Mathematical expression to evaluate"},
    },
)
async def calculator(expression: str):
    """Evaluate a mathematical expression safely."""
    # Allowed builtins
    allowed_names = {
        "abs": abs, "round": round, "min": min, "max": max,
        "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos,
        "tan": math.tan, "log": math.log, "log10": math.log10,
        "pi": math.pi, "e": math.e, "ceil": math.ceil, "floor": math.floor,
        "pow": pow, "int": int, "float": float,
    }

    # Remove any dangerous characters
    cleaned = re.sub(r'[^0-9+\-*/().%a-zA-Z_\s,]', '', expression)

    try:
        result = eval(cleaned, {"__builtins__": {}}, allowed_names)
        return json.dumps({"expression": expression, "result": result})
    except Exception as e:
        return json.dumps({"expression": expression, "error": str(e)})


# 5. json_tool — Parse/validate/format JSON
@register(
    "json_tool",
    "Parse, validate, or format a JSON string. Returns formatted JSON or validation errors.",
    {
        "input": {"type": "string", "description": "JSON string to parse/format"},
        "action": {"type": "string", "description": "Action: 'format', 'validate', or 'query' with a dot-path"},
    },
)
async def json_tool(input: str, action: str = "format"):
    """Parse, validate, or query JSON."""
    try:
        data = json.loads(input)
    except json.JSONDecodeError as e:
        return f"Invalid JSON: {e}"

    if action == "validate":
        return f"Valid JSON. Type: {type(data).__name__}, Top-level keys: {list(data.keys()) if isinstance(data, dict) else 'N/A (array)'}"

    if action == "format":
        return json.dumps(data, indent=2, ensure_ascii=False)

    if action.startswith("query"):
        # Simple dot-path query: "query foo.bar.0"
        path = action.replace("query", "").strip()
        parts = path.split(".")
        current = data
        for part in parts:
            if not part:
                continue
            if isinstance(current, list):
                try:
                    current = current[int(part)]
                except (ValueError, IndexError):
                    return f"Index '{part}' out of range"
            elif isinstance(current, dict):
                if part in current:
                    current = current[part]
                else:
                    return f"Key '{part}' not found. Available: {list(current.keys())}"
            else:
                return f"Cannot traverse into {type(current).__name__}"
        return json.dumps(current, indent=2, ensure_ascii=False)

    return json.dumps(data, indent=2, ensure_ascii=False)


# 6. text_stats — Count characters, words, lines
@register(
    "text_stats",
    "Analyze text: count characters, words, lines, paragraphs. Useful for content length checks.",
    {
        "text": {"type": "string", "description": "Text to analyze"},
    },
)
async def text_stats(text: str):
    """Count stats for a text string."""
    lines = text.split("\n")
    return json.dumps({
        "characters": len(text),
        "characters_no_spaces": len(text.replace(" ", "").replace("\n", "").replace("\t", "")),
        "words": len(text.split()),
        "lines": len(lines),
        "paragraphs": len([l for l in lines if l.strip()]),
        "bytes": len(text.encode("utf-8")),
    }, indent=2)


# 7. uuid_gen — Generate UUIDs
@register(
    "uuid_gen",
    "Generate UUIDs. Supports v4 (random) and v7 (time-ordered). Returns one or multiple.",
    {
        "version": {"type": "string", "description": "UUID version: 'v4' (random) or 'v7' (time-ordered)"},
        "count": {"type": "integer", "description": "Number of UUIDs to generate (default 1)"},
    },
)
async def uuid_gen(version: str = "v4", count: int = 1):
    """Generate UUID(s)."""
    count = max(1, min(count, 100))
    results = []
    for _ in range(count):
        if version == "v7":
            results.append(str(uuid.uuid7()))
        else:
            results.append(str(uuid.uuid4()))
    if count == 1:
        return results[0]
    return json.dumps(results, indent=2)


# 8. base64 — Encode/decode
@register(
    "base64",
    "Encode or decode base64 strings. Useful for handling binary data in text.",
    {
        "input": {"type": "string", "description": "Text to encode/decode"},
        "action": {"type": "string", "description": "'encode' or 'decode'"},
    },
)
async def base64(input: str, action: str = "encode"):
    """Base64 encode or decode."""
    try:
        if action == "encode":
            return _base64.b64encode(input.encode("utf-8")).decode("utf-8")
        else:
            return _base64.b64decode(input.encode("utf-8")).decode("utf-8")
    except Exception as e:
        return f"Base64 {action} failed: {e}"


# 9. hash — Compute hashes
@register(
    "hash",
    "Compute cryptographic hash (MD5, SHA1, SHA256, SHA512) of a text string.",
    {
        "input": {"type": "string", "description": "Text to hash"},
        "algorithm": {"type": "string", "description": "Hash algorithm: md5, sha1, sha256, sha512"},
    },
)
async def hash(input: str, algorithm: str = "sha256"):
    """Compute hash of input string."""
    algorithms = {
        "md5": hashlib.md5,
        "sha1": hashlib.sha1,
        "sha256": hashlib.sha256,
        "sha512": hashlib.sha512,
    }
    algo = algorithms.get(algorithm.lower())
    if not algo:
        return f"Unknown algorithm '{algorithm}'. Use: {', '.join(algorithms.keys())}"
    h = algo(input.encode("utf-8"))
    return json.dumps({"algorithm": algorithm.lower(), "hash": h.hexdigest()})


# 10. random_number — Random number generation
@register(
    "random_number",
    "Generate random numbers. Supports integer ranges and floating point with decimal places.",
    {
        "lo": {"type": "number", "description": "Minimum value (inclusive, default 0)"},
        "hi": {"type": "number", "description": "Maximum value (inclusive, default 100)"},
        "count": {"type": "integer", "description": "Number of values to generate (default 1, max 100)"},
        "decimals": {"type": "integer", "description": "Decimal places (0 for integer, default 0)"},
    },
)
async def random_number(lo: float = 0, hi: float = 100, count: int = 1, decimals: int = 0):
    """Generate random number(s)."""
    count = 1 if count < 1 else (100 if count > 100 else count)
    results = []
    for _ in range(count):
        val = random.uniform(lo, hi)
        if decimals <= 0:
            val = random.randint(int(lo), int(hi))
        else:
            val = round(val, decimals)
        results.append(val)
    if count == 1:
        return str(results[0])
    return json.dumps(results)


# 11. shell_exec — Execute shell command
@register(
    "shell_exec",
    "Execute a shell command and return stdout and stderr. Commands time out after 30 seconds. "
    "Use with caution. Best for read-only commands: ls, cat, grep, find, wc, head, tail, ps, df, etc.",
    {
        "command": {"type": "string", "description": "Shell command to execute"},
        "working_dir": {"type": "string", "description": "Working directory (default: current)"},
    },
)
async def shell_exec(command: str, working_dir: str = "."):
    """Execute a shell command and return output."""
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=working_dir,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        return json.dumps({
            "command": command,
            "exit_code": proc.returncode,
            "stdout": stdout.decode("utf-8", errors="replace")[:8000],
            "stderr": stderr.decode("utf-8", errors="replace")[:2000],
        }, indent=2)
    except asyncio.TimeoutError:
        return json.dumps({"command": command, "error": "Command timed out (30s)"})
    except Exception as e:
        return json.dumps({"command": command, "error": str(e)})


# 12. file_ops — Read/write/list files in workspace
@register(
    "file_ops",
    "Perform file operations: read, write, list, or delete files in the workspace directory.",
    {
        "action": {"type": "string", "description": "Action: 'read', 'write', 'list', 'delete'"},
        "path": {"type": "string", "description": "File or directory path (relative to workspace)"},
        "content": {"type": "string", "description": "Content to write (required for 'write' action)"},
    },
)
async def file_ops(action: str, path: str, content: str = ""):
    """File operations helper."""
    # Resolve relative to current working dir
    full_path = os.path.abspath(path)

    try:
        if action == "read":
            if not os.path.isfile(full_path):
                return f"File not found: {path}"
            text = open(full_path, "r", encoding="utf-8", errors="replace").read()
            if len(text) > 8000:
                text = text[:8000] + f"\n... [truncated, {len(text)} total chars]"
            return text

        elif action == "write":
            os.makedirs(os.path.dirname(full_path) or ".", exist_ok=True)
            open(full_path, "w", encoding="utf-8").write(content)
            return f"Written {len(content)} bytes to {path}"

        elif action == "list":
            if not os.path.isdir(full_path):
                full_path = os.path.dirname(full_path) or "."
            items = []
            for entry in sorted(os.listdir(full_path)):
                entry_path = os.path.join(full_path, entry)
                kind = "dir" if os.path.isdir(entry_path) else "file"
                size = os.path.getsize(entry_path) if os.path.isfile(entry_path) else 0
                items.append(f"  [{kind}] {entry} ({size} bytes)")
            return f"Contents of {full_path}:\n" + "\n".join(items[:50]) + (
                f"\n... and {len(items) - 50} more" if len(items) > 50 else ""
            )

        elif action == "delete":
            if not os.path.exists(full_path):
                return f"Path not found: {path}"
            if os.path.isdir(full_path):
                import shutil
                shutil.rmtree(full_path)
            else:
                os.remove(full_path)
            return f"Deleted: {path}"

        else:
            return f"Unknown action: {action}. Use: read, write, list, delete"

    except Exception as e:
        return f"File operation '{action}' on '{path}' failed: {e}"


# ── Sync wrappers for all async tools ────────────────────────────────────

# deepagents expects sync callables. We wrap async tools with asyncio.run().
def _sync_wrapper(async_func):
    """Wrap an async function into a sync function."""
    def wrapper(**kwargs):
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Running in async context, create new loop
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
