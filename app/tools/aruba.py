"""
Aruba Central tools for CentralMind Gateway.
Connects to your separate central-mind MCP server via stdio.
"""

import asyncio
import json
import logging
import subprocess
import sys
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.config import settings

logger = logging.getLogger(__name__)


class CentralMindClient:
    """Manages a persistent connection to the CentralMind MCP server."""

    def __init__(self):
        self.session: Optional[ClientSession] = None
        self._process = None
        self._stdio_ctx = None
        self._session_ctx = None

    async def start(self):
        """Start the CentralMind MCP server subprocess and connect."""
        if self.session:
            return

        logger.info(f"Starting CentralMind MCP server: {settings.centralmind_command}")

        # Parse command into executable + args
        parts = settings.centralmind_command.split()
        command = parts[0]
        args = parts[1:] if len(parts) > 1 else []

        server_params = StdioServerParameters(
            command=command,
            args=args,
            env=None,  # Inherits current environment (so .env from central-mind works if set)
            cwd=settings.centralmind_path,  # Run from central-mind's directory so it finds its .env
        )

        self._stdio_ctx = stdio_client(server_params)
        read, write = await self._stdio_ctx.__aenter__()

        self._session_ctx = ClientSession(read, write)
        self.session = await self._session_ctx.__aenter__()

        # Initialize the MCP session
        await self.session.initialize()

        # List available tools (for debugging / logging)
        tools = await self.session.list_tools()
        tool_names = [t.name for t in tools.tools]
        logger.info(f"Connected to CentralMind. Available tools: {tool_names}")

    async def stop(self):
        """Cleanly shut down the MCP connection."""
        if self._session_ctx:
            await self._session_ctx.__aexit__(None, None, None)
        if self._stdio_ctx:
            await self._stdio_ctx.__aexit__(None, None, None)
        self.session = None
        logger.info("CentralMind MCP connection closed")

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool on the CentralMind MCP server."""
        if not self.session:
            await self.start()

        try:
            result = await asyncio.wait_for(
                self.session.call_tool(tool_name, arguments),
                timeout=settings.mcp_timeout
            )
            # MCP returns content blocks; we want the text
            if result.content:
                text = result.content[0].text if hasattr(result.content[0], 'text') else str(result.content[0])
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    return text
            return result
        except asyncio.TimeoutError:
            logger.error(f"MCP tool {tool_name} timed out after {settings.mcp_timeout}s")
            raise
        except Exception as e:
            logger.error(f"MCP tool {tool_name} failed: {e}")
            raise

    # Convenience high-level methods (optional but very useful)
    async def search_central(self, code: str) -> Any:
        """Search Aruba Central OpenAPI spec using JS code."""
        return await self.call_tool("search_central", {"code": code})

    async def execute_central(self, code: str) -> Any:
        """Execute Aruba Central API call using JS code (respects readonly mode)."""
        return await self.call_tool("execute_central", {"code": code})


# Global singleton
centralmind_client = CentralMindClient()


@asynccontextmanager
async def get_centralmind_client():
    """FastAPI dependency or context manager."""
    if not centralmind_client.session:
        await centralmind_client.start()
    try:
        yield centralmind_client
    except Exception:
        # Don't close on every request — keep persistent
        raise
