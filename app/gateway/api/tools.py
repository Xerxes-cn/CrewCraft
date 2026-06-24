"""Tool catalog API route.

Exposes the list of available tools so CLI users can
discover what tools are available for agent configuration.
"""

from fastapi import APIRouter

from app.agent.tools import registry

router = APIRouter(prefix="/api/tools", tags=["tools"])


@router.get("")
async def list_tools():
    """List all available tools with their descriptions and parameters."""
    tools = []
    for tool in registry.list_all():
        tools.append(tool.to_dict())
    return tools
