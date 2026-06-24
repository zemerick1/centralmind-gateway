"""MCP Client for CentralMind Gateway - proper client to centralmind."""

import asyncio
import logging
import os
import subprocess
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from config import settings

logger = logging.getLogger(__name__)


class MCPClient:
    def __init__(self):
        self._available_tools: Dict[str, Any] = {}

    @asynccontextmanager
    async def _get_session(self):
        """Create a fresh connection to centralmind for each operation."""
        parts = settings.centralmind_command.split()
        command = parts[0]
        args = parts[1:] if len(parts) > 1 else []

        centralmind_dir = os.path.abspath("../central-mind")

        process = subprocess.Popen(
            [command] + args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=centralmind_dir,
            env=os.environ.copy(),
            text=False,
        )

        server_params = StdioServerParameters(command=command, args=args)

        try:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    yield session
        finally:
            try:
                process.terminate()
            except Exception:
                pass

    async def discover_tools(self) -> Dict[str, Any]:
        """Discover available tools from centralmind."""
        async with self._get_session() as session:
            tools_result = await session.list_tools()
            self._available_tools = {t.name: t for t in tools_result.tools}
            logger.info(f"Discovered MCP tools: {list(self._available_tools.keys())}")
            return self._available_tools

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call a specific tool on centralmind."""
        async with self._get_session() as session:
            result = await session.call_tool(tool_name, arguments)

            if result.content:
                text = result.content[0].text if hasattr(result.content[0], "text") else str(result.content[0])
                try:
                    import json
                    return json.loads(text)
                except Exception:
                    return {"raw_output": text}
            return result

    async def get_search_tools(self) -> List[str]:
        return [name for name in self._available_tools if name.startswith("search_")]

    async def get_execute_tools(self) -> List[str]:
        return [name for name in self._available_tools if name.startswith("execute_")]


mcp = MCPClient()
