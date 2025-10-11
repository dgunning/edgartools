#!/usr/bin/env python3
"""
EdgarTools MCP Server Entry Point

Enables running the server via: python -m edgar.ai.mcp
"""

if __name__ == "__main__":
    from edgar.ai import mcp_server
    mcp_server.main()
