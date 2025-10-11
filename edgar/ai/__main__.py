#!/usr/bin/env python3
"""
EdgarTools MCP Server Entry Point

Enables running the server via: python -m edgar.ai
"""

if __name__ == "__main__":
    import sys
    from edgar.ai import mcp_server

    # Check for --test flag before starting server
    if "--test" in sys.argv or "-t" in sys.argv:
        sys.exit(0 if mcp_server.test_server() else 1)
    else:
        mcp_server.main()
