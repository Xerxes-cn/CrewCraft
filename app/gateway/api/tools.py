"""工具目录 API 路由。

暴露可用工具列表，使 CLI 用户能够发现
可用于 Agent 配置的工具。
"""

from fastapi import APIRouter

from app.agent.tools import registry

router = APIRouter(prefix="/api/tools", tags=["tools"])


@router.get("")
async def list_tools():
    """列出所有可用工具及其描述和参数。"""
    tools = []
    for tool in registry.list_all():
        tools.append(tool.to_dict())
    return tools
