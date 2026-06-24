"""System prompt generation from user-provided agent descriptions.

Uses an LLM to generate a comprehensive system prompt based on a short
description of what the agent should do. Results are saved to
data/agents/{name}.prompt.md for user review and customization.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

GENERATION_PROMPT = """You are an expert prompt engineer. Based on the description below,
write a comprehensive system prompt for an AI agent.

The prompt should:
1. Define the agent's role and expertise clearly
2. List the types of tasks the agent can handle
3. Specify the agent's working style and constraints
4. Be written in the same language as the description
5. Be thorough but concise — aim for 200-500 words
6. NOT mention specific tools — the agent has access to all available tools

Description: {description}

Write ONLY the system prompt, no explanations or meta-commentary."""


def generate_prompt(description: str, model: str = "openai:gpt-4o") -> str:
    """Generate a system prompt from a description using LLM.

    Args:
        description: User's description of what the agent should do.
        model: LLM model to use for generation.

    Returns:
        Generated system prompt string.
    """
    import asyncio

    try:
        return asyncio.run(_generate_async(description, model))
    except RuntimeError:
        return _generate_fallback(description)


async def _generate_async(description: str, model: str) -> str:
    """Async LLM call to generate system prompt."""
    try:
        from langchain.chat_models import init_chat_model

        llm = init_chat_model(model)
        prompt = GENERATION_PROMPT.format(description=description)
        response = await llm.ainvoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
        return content.strip()
    except Exception as e:
        logger.warning(f"LLM prompt generation failed: {e}, using fallback")
        return _generate_fallback(description)


def _generate_fallback(description: str) -> str:
    """Fallback when LLM is unavailable — create a template prompt."""
    return f"""# {description}

You are an AI assistant with the following role:

{description}

You have access to various tools to help you complete tasks. Use them
thoughtfully to achieve the best results. Always explain your reasoning
and be thorough in your work.

When you are unsure, ask clarifying questions rather than making assumptions."""


def save_prompt(agent_name: str, prompt: str, data_dir: Path = None):
    """Save generated prompt to data/agents/{name}.prompt.md."""
    if data_dir is None:
        from app.config import config
        data_dir = config.data_dir
    agents_dir = data_dir / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = agents_dir / f"{agent_name}.prompt.md"
    prompt_path.write_text(prompt, encoding="utf-8")


def load_prompt(agent_name: str, data_dir: Path = None) -> str | None:
    """Load prompt from data/agents/{name}.prompt.md. Returns None if not found."""
    if data_dir is None:
        from app.config import config
        data_dir = config.data_dir
    prompt_path = data_dir / "agents" / f"{agent_name}.prompt.md"
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")
    return None
