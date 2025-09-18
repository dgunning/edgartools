"""
Model Context Protocol (MCP) implementation for EdgarTools.

This module provides MCP server functionality to expose EdgarTools
capabilities to AI agents and assistants.
"""

try:
    from edgar.ai.mcp.server import EdgarToolsServer, MCPServer
    from edgar.ai.mcp.tools import CompanyTool, FilingsTool, FinancialsTool, SearchTool
except ImportError:
    # Fallback if complex server doesn't work
    MCPServer = None
    EdgarToolsServer = None
    CompanyTool = None
    FilingsTool = None
    FinancialsTool = None
    SearchTool = None

# Export a function to get the simple server to avoid circular imports
def get_simple_server():
    """Get the simple MCP server instance."""
    from edgar.ai.mcp.simple_server import app
    return app

# For backward compatibility
SimpleServer = None

__all__ = [
    "MCPServer",
    "EdgarToolsServer", 
    "CompanyTool",
    "FilingsTool", 
    "FinancialsTool",
    "SearchTool",
    "get_simple_server"
]
