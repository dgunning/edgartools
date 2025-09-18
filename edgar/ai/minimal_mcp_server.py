#!/usr/bin/env python3
"""Minimal working MCP server for EdgarTools"""

# Test imports first

try:
    from mcp.server import Server
except ImportError:
    exit(1)

try:
    from mcp.types import TextContent, Tool
except ImportError:
    exit(1)


app = Server("edgartools")

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="edgar_test",
            description="Test tool",
            inputSchema={
                "type": "object",
                "properties": {
                    "message": {"type": "string"}
                }
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict | None) -> list[TextContent]:
    return [TextContent(type="text", text=f"Hello from {name}")]

if __name__ == "__main__":
    pass
