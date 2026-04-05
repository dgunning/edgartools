#!/usr/bin/env python3
"""
EdgarTools MCP Server

MCP (Model Context Protocol) server providing AI agents access to SEC filing data.

Design principles:
1. Intent-based tools (match user goals, not API structure)
2. Flexible identifiers (ticker, CIK, name all work)
3. Structured JSON responses (AI-friendly)
4. Smart defaults, explicit overrides
5. Helpful error messages with suggestions

Tools:
- edgar_company: Get company info, financials, filings, ownership in one call
- edgar_search: Search companies and/or filings
- edgar_filing: Read SEC filing content and sections (10-K, 10-Q, 8-K, DEF 14A, 13D/G, 13F)
- edgar_compare: Compare multiple companies or analyze industry
- edgar_ownership: Insider transactions, fund portfolios
- edgar_monitor: Real-time SEC filings feed
- edgar_trends: Financial time series with growth rates
- edgar_screen: Company discovery by industry, exchange, state
- edgar_text_search: Full-text search across SEC filing content

Usage:
    python -m edgar.ai.mcp        # Via module
    edgartools-mcp                # Via console script
"""

import asyncio
import logging
import os
from typing import Any

from mcp import Resource, Tool
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import GetPromptResult, Prompt, TextContent

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("edgartools-mcp")


def setup_edgar_identity():
    """
    Configure SEC identity from environment variable.

    The SEC requires proper identification for API requests. This function
    checks for the EDGAR_IDENTITY environment variable and configures it.
    """
    try:
        from edgar import set_identity

        identity = os.environ.get('EDGAR_IDENTITY')
        if not identity:
            logger.warning(
                "EDGAR_IDENTITY environment variable not set. "
                "The SEC requires proper identification for API requests.\n"
                "Add to your MCP client configuration:\n"
                '  "env": {"EDGAR_IDENTITY": "Your Name your.email@example.com"}\n'
                "Or set in your shell: export EDGAR_IDENTITY=\"Your Name your.email@example.com\""
            )
            return

        set_identity(identity)
        logger.info(f"SEC identity configured: {identity}")

    except Exception as e:
        logger.error(f"Error setting up EDGAR identity: {e}")


def _import_tools():
    """
    Import all tool modules to register them.

    Each tool module uses the @tool decorator which registers
    the tool in the TOOLS registry when imported.
    """
    # Import tool modules - this triggers registration via @tool decorators
    from edgar.ai.mcp.tools import company  # noqa: F401
    from edgar.ai.mcp.tools import search  # noqa: F401
    from edgar.ai.mcp.tools import filing  # noqa: F401
    from edgar.ai.mcp.tools import compare  # noqa: F401
    from edgar.ai.mcp.tools import ownership  # noqa: F401
    from edgar.ai.mcp.tools import monitor  # noqa: F401
    from edgar.ai.mcp.tools import trends  # noqa: F401
    from edgar.ai.mcp.tools import screen  # noqa: F401
    from edgar.ai.mcp.tools import text_search  # noqa: F401


# Create the server
app = Server("edgartools")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools from the registry."""
    from edgar.ai.mcp.tools.base import TOOLS

    # Ensure tools are imported
    _import_tools()

    tools = []
    for info in TOOLS.values():
        kwargs = {
            "name": info["name"],
            "description": info["description"],
            "inputSchema": info["schema"],
        }
        if "output_schema" in info:
            kwargs["outputSchema"] = info["output_schema"]
        tools.append(Tool(**kwargs))
    return tools


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any] | None) -> list[TextContent]:
    """Handle tool calls by routing to registered handlers."""
    from edgar.ai.mcp.tools.base import TOOLS, call_tool_handler

    # Ensure tools are imported
    _import_tools()

    if arguments is None:
        arguments = {}

    try:
        # Route to handler
        result = await call_tool_handler(name, arguments)

        # Convert response to TextContent
        return [TextContent(
            type="text",
            text=result.to_json()
        )]

    except Exception as e:
        logger.error("Error in tool %s: %s", name, e, exc_info=True)
        return [TextContent(
            type="text",
            text=f'{{"success": false, "error": "{str(e)}"}}'
        )]


@app.list_resources()
async def list_resources() -> list[Resource]:
    """List available resources."""
    return [
        Resource(
            uri="edgartools://docs/quickstart",
            name="EdgarTools Quickstart Guide",
            description="Quick start guide for using EdgarTools MCP",
            mimeType="text/markdown"
        ),
        Resource(
            uri="edgartools://docs/tools",
            name="Tool Reference",
            description="Detailed reference for all available tools",
            mimeType="text/markdown"
        )
    ]


@app.read_resource()
async def read_resource(uri: str) -> str:
    """Read a resource."""
    if uri == "edgartools://docs/quickstart":
        return _get_quickstart_doc()
    elif uri == "edgartools://docs/tools":
        return _get_tools_doc()
    else:
        raise ValueError(f"Unknown resource: {uri}")


@app.list_prompts()
async def handle_list_prompts() -> list[Prompt]:
    """List available analysis prompts."""
    from edgar.ai.mcp.tools.prompts import list_prompts
    return list_prompts()


@app.get_prompt()
async def handle_get_prompt(name: str, arguments: dict[str, str] | None = None) -> GetPromptResult:
    """Get a specific analysis prompt with arguments."""
    from edgar.ai.mcp.tools.prompts import get_prompt
    return get_prompt(name, arguments)


def _get_quickstart_doc() -> str:
    """Get quickstart documentation."""
    return """# EdgarTools MCP Quickstart

## Available Tools

### edgar_company
Get comprehensive company information in one call.

```json
{"identifier": "AAPL"}
{"identifier": "AAPL", "include": ["profile", "financials"]}
{"identifier": "MSFT", "periods": 8, "annual": false}
```

### edgar_search
Search for companies or filings.

```json
{"query": "artificial intelligence", "search_type": "companies"}
{"form": "10-K", "identifier": "AAPL", "search_type": "filings"}
```

### edgar_filing
Read SEC filing content.

```json
{"identifier": "AAPL", "form": "10-K", "sections": ["business", "risk_factors"]}
{"accession_number": "0000320193-23-000077", "sections": ["mda"]}
```

### edgar_compare
Compare multiple companies.

```json
{"identifiers": ["AAPL", "MSFT", "GOOGL"]}
{"industry": "software", "limit": 5}
```

### edgar_ownership
Get ownership information.

```json
{"identifier": "AAPL", "analysis_type": "insiders"}
{"identifier": "1067983", "analysis_type": "fund_portfolio"}
{"identifier": "1067983", "analysis_type": "portfolio_diff"}
```

### edgar_monitor
Get latest SEC filings in real-time.

```json
{}
{"form": "8-K"}
{"form": "4", "limit": 50}
```

### edgar_trends
Get financial time series with growth rates.

```json
{"identifier": "AAPL"}
{"identifier": "MSFT", "concepts": ["revenue", "net_income", "eps"], "periods": 10}
```

### edgar_screen
Discover companies by industry, exchange, or state.

```json
{"industry": "software"}
{"exchange": "NYSE", "industry": "pharmaceutical"}
{"state": "DE", "limit": 50}
```

### edgar_text_search
Full-text search across SEC filing content.

```json
{"query": "artificial intelligence"}
{"query": "cybersecurity incident", "forms": ["8-K"]}
{"query": "tariff impact", "identifier": "AAPL", "start_date": "2024-01-01"}
```

## Prompts

Pre-built analysis workflows:
- **due_diligence**: Full company analysis (profile, financials, risks, insiders)
- **earnings_analysis**: Earnings deep dive (8-K, trends, peer comparison)
- **industry_overview**: Sector survey (screen, compare, trends)
- **insider_monitor**: Insider trading activity analysis

## Tips

1. **Flexible identifiers**: Use ticker (AAPL), CIK (320193), or company name
2. **Control output**: Use 'include' parameter to get only what you need
3. **Follow next_steps**: Each response suggests logical next actions
"""


def _get_tools_doc() -> str:
    """Get detailed tools documentation."""
    from edgar.ai.mcp.tools.base import TOOLS
    _import_tools()

    doc_parts = ["# EdgarTools MCP Tools Reference\n"]

    for name, info in TOOLS.items():
        doc_parts.append(f"## {name}\n")
        doc_parts.append(f"{info['description']}\n")
        doc_parts.append("\n**Parameters:**\n")

        for param, details in info['schema'].get('properties', {}).items():
            required = param in info['schema'].get('required', [])
            req_str = " (required)" if required else ""
            desc = details.get('description', 'No description')
            doc_parts.append(f"- `{param}`{req_str}: {desc}\n")

        doc_parts.append("\n")

    return "".join(doc_parts)


def main():
    """Main entry point for MCP server."""
    try:
        # Get package version for server version
        from edgar.__about__ import __version__

        # Configure EDGAR identity from environment
        setup_edgar_identity()

        async def run_server():
            """Run the async MCP server."""
            logger.info(f"Starting EdgarTools MCP Server v{__version__}")

            # Use stdio transport
            async with stdio_server() as (read_stream, write_stream):
                await app.run(
                    read_stream,
                    write_stream,
                    InitializationOptions(
                        server_name="edgartools",
                        server_version=__version__,
                        capabilities=app.get_capabilities(
                            notification_options=NotificationOptions(),
                            experimental_capabilities={}
                        )
                    )
                )

        asyncio.run(run_server())

    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        raise


def test_server():
    """
    Test that MCP server is properly configured and ready to run.

    Returns:
        bool: True if all checks pass, False otherwise
    """
    print("Testing EdgarTools MCP Server Configuration...\n")

    all_passed = True

    # Test 1: EdgarTools import check
    try:
        from edgar import Company
        from edgar.__about__ import __version__
        print(f"✓ EdgarTools v{__version__} imports successfully")
    except ImportError as e:
        print(f"✗ EdgarTools import error: {e}")
        print("  Install with: pip install edgartools")
        all_passed = False

    # Test 2: MCP framework check
    try:
        from mcp.server import Server
        print("✓ MCP framework available")
    except ImportError as e:
        print(f"✗ MCP framework not installed: {e}")
        print('  Install with: pip install "edgartools[ai]"')
        all_passed = False

    # Test 3: Tool registration check
    try:
        from edgar.ai.mcp.tools.base import TOOLS
        _import_tools()
        tool_count = len(TOOLS)
        print(f"✓ {tool_count} tools registered: {', '.join(TOOLS.keys())}")
    except Exception as e:
        print(f"✗ Tool registration failed: {e}")
        all_passed = False

    # Test 4: Identity configuration check
    identity = os.environ.get('EDGAR_IDENTITY')
    if identity:
        print(f"✓ EDGAR_IDENTITY configured: {identity}")
    else:
        print("⚠ EDGAR_IDENTITY not set (recommended)")
        print("  Set with: export EDGAR_IDENTITY=\"Your Name your@email.com\"")
        print("  Or configure in MCP client's env settings")

    # Summary
    print()
    if all_passed:
        print("✓ All checks passed - MCP server is ready to run")
        print("\nTo start the server:")
        print("  python -m edgar.ai.mcp")
        print("  or")
        print("  edgartools-mcp")
        return True
    else:
        print("✗ Some checks failed - please fix the issues above")
        return False


if __name__ == "__main__":
    import sys

    # Check for --test flag
    if "--test" in sys.argv or "-t" in sys.argv:
        sys.exit(0 if test_server() else 1)
    else:
        main()
