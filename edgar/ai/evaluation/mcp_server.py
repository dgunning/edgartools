"""
Standalone MCP stdio server for EdgarTools evaluation.

This script runs as a subprocess, serving the 5 EdgarTools MCP tools
via the MCP stdio protocol. Used by the agent evaluation framework
when running through the Claude Code SDK.

Usage:
    python -m edgar.ai.evaluation.mcp_server
"""

import asyncio
import json
import sys

from mcp.server import Server, NotificationOptions
from mcp.server.stdio import stdio_server
from mcp.server.models import InitializationOptions
from mcp.types import Tool, TextContent

# Import and register all tool modules
from edgar.ai.mcp.tools import company, search, filing, compare, ownership  # noqa: F401
from edgar.ai.mcp.tools.base import TOOLS, call_tool_handler


app = Server("edgar-tools")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List all available EdgarTools MCP tools."""
    tools = []
    for name, info in TOOLS.items():
        tools.append(Tool(
            name=name,
            description=info["description"],
            inputSchema=info["schema"],
        ))
    return tools


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Execute a tool and return results."""
    response = await call_tool_handler(name, arguments)
    return [TextContent(type="text", text=response.to_json())]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        init_options = InitializationOptions(
            server_name="edgar-tools",
            server_version="1.0.0",
            capabilities=app.get_capabilities(
                notification_options=NotificationOptions(),
                experimental_capabilities=None,
            ),
        )
        await app.run(read_stream, write_stream, init_options)


if __name__ == "__main__":
    asyncio.run(main())
