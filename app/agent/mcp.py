"""MCP (Model Context Protocol) 客户端。

Agent 启动时自动连接 MCP Server，将其 tools 注册到工具列表。
"""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class MCPClient:
    """MCP 客户端 — 管理多个 MCP Server 连接。"""

    def __init__(self):
        self._sessions: dict[str, Any] = {}
        self._tools: dict[str, Any] = {}

    @property
    def tools(self) -> dict[str, Any]:
        return self._tools

    async def connect(self, server_config: dict) -> bool:
        """连接一个 MCP Server。"""
        name = server_config.get("name", "unknown")
        command = server_config.get("command", "")
        args = server_config.get("args", [])

        if not command:
            logger.warning(f"MCP Server {name}: 缺少 command")
            return False

        logger.info(f"连接 MCP Server: {name} ({command} {' '.join(args)})")
        try:
            # 使用 mcp 包的标准客户端
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client

            params = StdioServerParameters(command=command, args=args)
            transport = await stdio_client(params)
            session = await ClientSession(transport[0], transport[1]).__aenter__()

            # 发现 tools
            tools_result = await session.list_tools()
            for tool in tools_result.tools:
                full_name = f"mcp_{name}_{tool.name}"
                self._tools[full_name] = {
                    "name": full_name,
                    "description": tool.description or f"MCP tool: {tool.name}",
                    "session": session,
                    "original_name": tool.name,
                    "schema": tool.inputSchema,
                }
                logger.info(f"  MCP tool: {full_name}")

            self._sessions[name] = session
            logger.info(f"MCP {name}: {len(tools_result.tools)} tools 已加载")
            return True
        except ImportError:
            logger.warning(f"MCP {name}: mcp 包未安装。pip install mcp")
            return False
        except Exception as e:
            logger.warning(f"MCP {name}: 连接失败 - {e}")
            return False

    async def disconnect_all(self):
        """断开所有 MCP 连接。"""
        for name, session in self._sessions.items():
            try:
                await session.__aexit__(None, None, None)
            except Exception:
                pass
        self._sessions.clear()
        self._tools.clear()
        logger.info("所有 MCP 连接已断开")

    def load_config(self, agent_name: str, data_dir: Path = None) -> list[dict]:
        """加载 Agent 的 MCP 配置。"""
        if data_dir is None:
            from app.config import config
            data_dir = config.data_dir
        path = data_dir / "agents" / agent_name / "mcp.json"
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text())
            return data.get("servers", [])
        except Exception as e:
            logger.warning(f"加载 MCP 配置失败: {e}")
            return []

    async def connect_all(self, agent_name: str, data_dir: Path = None):
        """连接 Agent 的所有 MCP Server。"""
        servers = self.load_config(agent_name, data_dir)
        for server in servers:
            await self.connect(server)


# 全局实例
mcp_client = MCPClient()
