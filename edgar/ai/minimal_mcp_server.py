#!/usr/bin/env python3
"""Minimal working MCP server for EdgarTools"""

# Test imports first
print("Testing imports...")

try:
    from mcp.server import Server
    print("✓ Server import OK")
except ImportError as e:
    print(f"✗ Server import failed: {e}")
    exit(1)

try: 
    from mcp.types import Tool, Resource, TextContent
    print("✓ Types import OK")
except ImportError as e:
    print(f"✗ Types import failed: {e}")
    exit(1)

print("Creating minimal server...")

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
    print(f"Minimal MCP server ready: {app.name}")
    print("This server would normally start stdio transport here")