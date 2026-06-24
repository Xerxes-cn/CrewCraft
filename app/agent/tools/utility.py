"""实用工具：时间、数学、文本、加密、编码。"""

import base64 as _base64
import hashlib
import json
import math
import random
import re
import uuid
from datetime import datetime, timezone

from .registry import register


# ── 时间 ───────────────────────────────────────────────────────────────

@register(
    "time_now",
    "Get the current date and time. Returns ISO format, unix timestamp, and human-readable formats.",
    {
        "tz": {"type": "string", "description": "Timezone name, e.g. 'Asia/Shanghai', 'UTC'"},
    },
)
async def time_now(tz: str = ""):
    """返回多种格式的当前日期/时间。"""
    now = datetime.now(timezone.utc)
    try:
        import zoneinfo
        if tz:
            now = datetime.now(zoneinfo.ZoneInfo(tz))
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


# ── 数学 ───────────────────────────────────────────────────────────────

@register(
    "calculator",
    "Safely evaluate a mathematical expression. Supports +, -, *, /, **, %, sqrt, sin, cos, log, abs, etc.",
    {
        "expression": {"type": "string", "description": "Mathematical expression to evaluate"},
    },
)
async def calculator(expression: str):
    """安全地计算数学表达式。"""
    allowed_names = {
        "abs": abs, "round": round,
        "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos,
        "tan": math.tan, "log": math.log, "log10": math.log10,
        "pi": math.pi, "e": math.e, "ceil": math.ceil, "floor": math.floor,
        "pow": pow, "int": int, "float": float,
    }
    cleaned = re.sub(r"[^0-9+\-*/().%a-zA-Z_\s,]", "", expression)
    try:
        result = eval(cleaned, {"__builtins__": {}}, allowed_names)
        return json.dumps({"expression": expression, "result": result})
    except Exception as e:
        return json.dumps({"expression": expression, "error": str(e)})


@register(
    "random_number",
    "Generate random numbers. Supports integer ranges and floating point with decimal places.",
    {
        "lo": {"type": "number", "description": "Minimum value (inclusive, default 0)"},
        "hi": {"type": "number", "description": "Maximum value (inclusive, default 100)"},
        "count": {"type": "integer", "description": "Number of values (default 1, max 100)"},
        "decimals": {"type": "integer", "description": "Decimal places (0 for integer)"},
    },
)
async def random_number(lo: float = 0, hi: float = 100, count: int = 1, decimals: int = 0):
    """生成随机数。"""
    count = 1 if count < 1 else (100 if count > 100 else count)
    results = []
    for _ in range(count):
        if decimals <= 0:
            val = random.randint(int(lo), int(hi))
        else:
            val = round(random.uniform(lo, hi), decimals)
        results.append(val)
    if count == 1:
        return str(results[0])
    return json.dumps(results)


# ── 文本 / JSON ────────────────────────────────────────────────────────

@register(
    "text_stats",
    "Analyze text: count characters, words, lines, paragraphs.",
    {
        "text": {"type": "string", "description": "Text to analyze"},
    },
)
async def text_stats(text: str):
    """统计文本的字符数。"""
    lines = text.split("\n")
    return json.dumps({
        "characters": len(text),
        "characters_no_spaces": len(text.replace(" ", "").replace("\n", "").replace("\t", "")),
        "words": len(text.split()),
        "lines": len(lines),
        "paragraphs": len([l for l in lines if l.strip()]),
        "bytes": len(text.encode("utf-8")),
    }, indent=2)


@register(
    "json_tool",
    "Parse, validate, or format a JSON string. Supports 'format', 'validate', and 'query <dot.path>' actions.",
    {
        "input": {"type": "string", "description": "JSON string to parse/format"},
        "action": {"type": "string", "description": "Action: 'format', 'validate', or 'query <dot.path>'"},
    },
)
async def json_tool(input: str, action: str = "format"):
    """解析、验证或查询 JSON。"""
    try:
        data = json.loads(input)
    except json.JSONDecodeError as e:
        return f"Invalid JSON: {e}"

    if action == "validate":
        keys = list(data.keys()) if isinstance(data, dict) else "N/A (array)"
        return f"Valid JSON. Type: {type(data).__name__}, Top-level keys: {keys}"

    if action == "format":
        return json.dumps(data, indent=2, ensure_ascii=False)

    if action.startswith("query"):
        path = action.replace("query", "").strip()
        current = data
        for part in path.split("."):
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


# ── 编码 / 加密 ──────────────────────────────────────────────────────

@register(
    "base64",
    "Encode or decode base64 strings.",
    {
        "input": {"type": "string", "description": "Text to encode/decode"},
        "action": {"type": "string", "description": "'encode' or 'decode'"},
    },
)
async def base64(input: str, action: str = "encode"):
    """Base64 编码或解码。"""
    try:
        if action == "encode":
            return _base64.b64encode(input.encode("utf-8")).decode("utf-8")
        else:
            return _base64.b64decode(input.encode("utf-8")).decode("utf-8")
    except Exception as e:
        return f"Base64 {action} failed: {e}"


@register(
    "hash",
    "Compute cryptographic hash (MD5, SHA1, SHA256, SHA512) of a text string.",
    {
        "input": {"type": "string", "description": "Text to hash"},
        "algorithm": {"type": "string", "description": "Hash algorithm: md5, sha1, sha256, sha512"},
    },
)
async def hash(input: str, algorithm: str = "sha256"):
    """计算输入字符串的哈希值。"""
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


@register(
    "uuid_gen",
    "Generate UUIDs. Supports v4 (random) and v7 (time-ordered).",
    {
        "version": {"type": "string", "description": "UUID version: 'v4' (random) or 'v7' (time-ordered)"},
        "count": {"type": "integer", "description": "Number of UUIDs to generate (default 1)"},
    },
)
async def uuid_gen(version: str = "v4", count: int = 1):
    """生成 UUID。"""
    count = 1 if count < 1 else (100 if count > 100 else count)
    results = []
    for _ in range(count):
        if version == "v7":
            results.append(str(uuid.uuid7()))
        else:
            results.append(str(uuid.uuid4()))
    if count == 1:
        return results[0]
    return json.dumps(results, indent=2)
