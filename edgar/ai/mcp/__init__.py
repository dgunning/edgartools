"""
Model Context Protocol (MCP) server for EdgarTools.

This module provides MCP server functionality to expose EdgarTools
capabilities to AI agents and assistants like Claude Desktop.

Usage:
    # Start the server
    python -m edgar.ai

    # Or via console script
    edgartools-mcp

    # Test the server configuration
    python -m edgar.ai --test

For configuration and setup instructions, see:
    edgar/ai/mcp/docs/MCP_QUICKSTART.md
"""

from edgar.ai.mcp.server import main, test_server

__all__ = [
    "main",
    "test_server",
]

