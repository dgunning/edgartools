#!/usr/bin/env python3
"""
DEPRECATED: Legacy entry point for EdgarTools MCP server.

⚠️  This file is maintained for backward compatibility only.

New Usage (Recommended):
    python -m edgar.ai        # Python module entry point
    edgartools-mcp            # Console script (after pip install)

This script still works but you should migrate to the new entry points which:
- Don't require absolute file paths
- Work from any directory
- Are simpler to configure
- Support standard Python tooling

---

Legacy Usage:
    python edgar/ai/run_mcp_server.py

Legacy Claude Desktop Configuration:
    {
      "mcpServers": {
        "edgartools": {
          "command": "python",
          "args": ["/path/to/edgartools/edgar/ai/run_mcp_server.py"]
        }
      }
    }

Updated Configuration (Recommended):
    {
      "mcpServers": {
        "edgartools": {
          "command": "python",
          "args": ["-m", "edgar.ai"],
          "env": {
            "EDGAR_IDENTITY": "Your Name your@email.com"
          }
        }
      }
    }

See docs/MCP_QUICKSTART.md for complete setup guide.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add the project root to Python path so imports work
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("edgartools-mcp-legacy")


def main():
    """Run the MCP server using legacy entry point."""

    # Show deprecation warning
    logger.warning(
        "\n"
        "⚠️  DEPRECATION NOTICE ⚠️\n"
        "This entry point (run_mcp_server.py) is deprecated.\n"
        "\n"
        "Please update your MCP configuration to use:\n"
        '  "command": "python",\n'
        '  "args": ["-m", "edgar.ai"]\n'
        "\n"
        "Or use the console script after pip install:\n"
        "  edgartools-mcp\n"
        "\n"
        "See edgar/ai/docs/MCP_QUICKSTART.md for complete migration guide.\n"
        "Server will continue to work for now...\n"
    )

    try:
        # Use the new consolidated server module
        from edgar.ai import mcp_server

        # Run the server
        mcp_server.main()

    except ImportError as e:
        logger.error(f"Import error: {e}")
        logger.error("Make sure EdgarTools is installed: pip install edgartools[ai]")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
