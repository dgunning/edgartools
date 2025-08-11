#!/usr/bin/env python3
"""
Run the EdgarTools MCP server.

This script starts the MCP server that can be used with Claude Desktop
and other MCP-compatible AI assistants.

Usage:
    python edgar/ai/run_mcp_server.py

Claude Desktop Configuration:
    Add this to your claude_desktop_config.json:
    
    {
      "mcpServers": {
        "edgartools": {
          "command": "python",
          "args": ["/path/to/edgartools/edgar/ai/run_mcp_server.py"]
        }
      }
    }
"""

import sys
import asyncio
import logging
from pathlib import Path

# Add the project root to Python path so imports work
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

def main():
    """Run the MCP server."""
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # Import the standalone server module
        import edgar.ai.edgartools_mcp_server as server_module
        
        print("Starting EdgarTools MCP server...", file=sys.stderr)
        print("Use Ctrl+C to stop", file=sys.stderr)
        
        # Run the async server
        asyncio.run(server_module.main())
        
    except ImportError as e:
        print(f"Error: {e}", file=sys.stderr)
        print("Please install EdgarTools with AI support:", file=sys.stderr)
        print("  pip install edgartools[ai]", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nServer stopped", file=sys.stderr)
        sys.exit(0)
    except Exception as e:
        print(f"Error running server: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()