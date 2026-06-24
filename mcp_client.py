import logging
from typing import Any, Dict, List, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from config import settings

logger = logging.getLogger(__name__)


class MCPClient:
    def __init__(self):
        self.session: Optional[ClientSession] = None
        self.available_tools: Dict[str, Any] = {}
        self.search_tools: List[str] = []
        self.execute_tools: List[str] = []

    async def start(self):
        if self.session:
            return

        logger.info(f"Starting CentralMind MCP: {settings.centralmind_command}")

        parts = settings.centralmind_command.split()
        command = parts[0]
        args = parts[1:] if len(parts) > 1 else []

        server_params = StdioServerParameters(command=command, args=args)

        stdio_ctx = stdio_client(server_params)
        read, write = await stdio_ctx.__aenter__()

        self.session = await ClientSession(read, write).__aenter__()
        await self.session.initialize()

        # Dynamically discover tools
        tools_result = await self.session.list_tools()
        self.available_tools = {t.name: t for t in tools_result.tools}

        self.search_tools = [name for name in self.available_tools if name.startswith("search_")]
        self.execute_tools = [name for name in self.available_tools if name.startswith("execute_")]

        logger.info(f"MCP connected. Search tools: {self.search_tools}")
        logger.info(f"MCP connected. Execute tools: {self.execute_tools}")

    async def call(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        if not self.session:
            await self.start()

        result = await self.session.call_tool(tool_name, arguments)

        if result.content:
            text = result.content[0].text if hasattr(result.content[0], "text") else str(result.content[0])
            try:
                import json
                return json.loads(text)
            except Exception:
                return text
        return result

    async def call_search(self, code: str) -> Any:
        if not self.search_tools:
            raise RuntimeError("No search_* tools found from CentralMind")
        tool_name = self.search_tools[0]
        return await self.call(tool_name, {"code": code})

    async def call_execute(self, code: str) -> Any:
        if not self.execute_tools:
            raise RuntimeError("No execute_* tools found from CentralMind")
        tool_name = self.execute_tools[0]
        return await self.call(tool_name, {"code": code})

    async def stop(self):
        if self.session:
            await self.session.__aexit__(None, None, None)
            self.session = None
            logger.info("MCP connection closed")


mcp = MCPClient()
