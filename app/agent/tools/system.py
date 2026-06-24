"""系统工具：Shell 执行和文件操作。"""

import asyncio
import json
import os

from .registry import register


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
    """执行 Shell 命令并返回输出。"""
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


@register(
    "file_ops",
    "Perform file operations: read, write, list, or delete files in the workspace directory.",
    {
        "action": {"type": "string", "description": "Action: 'read', 'write', 'list', 'delete'"},
        "path": {"type": "string", "description": "File or directory path"},
        "content": {"type": "string", "description": "Content to write (required for 'write' action)"},
    },
)
async def file_ops(action: str, path: str, content: str = ""):
    """文件操作助手。"""
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
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
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
            header = f"Contents of {full_path}:\n"
            body = "\n".join(items[:50])
            suffix = f"\n... and {len(items) - 50} more" if len(items) > 50 else ""
            return header + body + suffix

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
