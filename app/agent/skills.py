"""Skill 加载器。

从 data/agents/{name}/skills/ 目录加载 Agent 专属 Skill 文件。
Skill 是 markdown 文件，包含 Agent 的行为指令和工具使用指南。
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def load_skills(agent_name: str, data_dir: Path = None) -> list[dict]:
    """加载 Agent 的私有 Skill 文件。

    扫描 data/agents/{name}/skills/*.md
    返回 [{"name": "xxx", "content": "..."}, ...]
    """
    if data_dir is None:
        from app.config import config
        data_dir = config.data_dir

    skills_dir = data_dir / "agents" / agent_name / "skills"
    if not skills_dir.is_dir():
        return []

    skills = []
    for path in sorted(skills_dir.glob("*.md")):
        try:
            skills.append({
                "name": path.stem,
                "content": path.read_text(encoding="utf-8"),
            })
        except Exception as e:
            logger.warning(f"加载 skill 失败 {path}: {e}")

    return skills


def inject_skills_to_prompt(base_prompt: str, agent_name: str = None,
                            data_dir: Path = None) -> str:
    """将 Agent 的 Skill 注入到 system_prompt 中。"""
    if not agent_name:
        return base_prompt

    skills = load_skills(agent_name, data_dir)
    if not skills:
        return base_prompt

    skill_text = "\n\n".join(
        f"## Skill: {s['name']}\n{s['content']}" for s in skills
    )
    return f"{base_prompt}\n\n---\n\n# Available Skills\n\n{skill_text}"
