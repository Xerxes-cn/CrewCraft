"""Skill 加载器 — 加载公共和私有 Skill。"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def load_skills(agent_name: str = None, data_dir: Path = None) -> list[dict]:
    """加载 Skill 文件。

    1. 公共 Skill：app/agent/skills/*.md
    2. 私有 Skill：data/agents/{name}/skills/*.md

    私有 Skill 优先级更高（允许覆盖同名）。
    返回 [{"name": "xxx", "content": "..."}, ...]
    """
    skills = {}

    # 公共 Skill
    public_dir = Path(__file__).parent
    if public_dir.is_dir():
        for path in sorted(public_dir.glob("*.md")):
            name = path.stem
            skills[name] = {"name": name, "content": path.read_text(encoding="utf-8")}

    # 私有 Skill
    if agent_name and data_dir:
        private_dir = data_dir / "agents" / agent_name / "skills"
        if private_dir.is_dir():
            for path in sorted(private_dir.glob("*.md")):
                name = path.stem
                skills[name] = {"name": name, "content": path.read_text(encoding="utf-8")}

    return list(skills.values())


def inject_skills_to_prompt(base_prompt: str, agent_name: str = None, data_dir: Path = None) -> str:
    """将已加载的 Skill 注入到 system_prompt 中。"""
    skills = load_skills(agent_name, data_dir)
    if not skills:
        return base_prompt

    skill_text = "\n\n".join(
        f"## Skill: {s['name']}\n{s['content']}" for s in skills
    )
    return f"{base_prompt}\n\n---\n\n# Available Skills\n\n{skill_text}"
