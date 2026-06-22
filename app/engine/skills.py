"""Skill loader — reads .md files with YAML frontmatter from the skills/ directory."""

from __future__ import annotations

import re
from pathlib import Path

SKILLS_DIR = Path("skills")


def _parse_frontmatter(content: str) -> tuple[dict, str]:
    """Extract YAML-like frontmatter and body from markdown content."""
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)", content, re.DOTALL)
    if not m:
        return {}, content
    raw = m.group(1)
    body = m.group(2).strip()
    data: dict = {}
    current_key: str | None = None
    list_buf: list[str] = []
    for line in raw.split("\n"):
        # list item
        lm = re.match(r"^\s+-\s+(.+)", line)
        if lm and current_key:
            list_buf.append(lm.group(1).strip())
            continue
        # flush list
        if list_buf and current_key:
            data[current_key] = list_buf
            list_buf = []
            current_key = None
        # key: value
        km = re.match(r"^(\w[\w_]*)\s*:\s*(.*)", line)
        if km:
            current_key = km.group(1)
            val = km.group(2).strip().strip('"').strip("'")
            data[current_key] = val
    if list_buf and current_key:
        data[current_key] = list_buf
    return data, body


def load_skills() -> list[dict]:
    """Load all .md skill files from the skills/ directory."""
    if not SKILLS_DIR.is_dir():
        return []
    skills: list[dict] = []
    for f in sorted(SKILLS_DIR.glob("*.md")):
        content = f.read_text(encoding="utf-8")
        meta, body = _parse_frontmatter(content)
        if meta.get("name"):
            skills.append({
                "name": meta["name"],
                "label": meta.get("label", meta["name"]),
                "description": meta.get("description", meta.get("label", "")),
                "tools": meta.get("tools", []) if isinstance(meta.get("tools"), list) else [],
                "prompt": body,
            })
    return skills


def reload_skills() -> list[dict]:
    """Force reload skills (useful for dev/hot-reload)."""
    return load_skills()
