#!/usr/bin/env python3
"""
EdgarTools MCP Server

MCP (Model Context Protocol) server providing AI agents access to SEC filing data.
This module provides the main entry point for the MCP server.

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
from mcp.types import TextContent

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("edgartools-mcp")


def setup_edgar_identity():
    """Configure SEC identity from environment variable.

    The SEC requires proper identification for API requests. This function
    checks for the EDGAR_IDENTITY environment variable and configures it.
    If not set, logs a warning but continues (API errors will guide user).
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

# Create the server
app = Server("edgartools")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="edgar_company_research",
            description="Get company overview and background. Returns profile, 3-year financial trends, and recent filing activity. Use this for initial company research or to get a snapshot of recent performance.",
            inputSchema={
                "type": "object",
                "properties": {
                    "identifier": {
                        "type": "string",
                        "description": "Company ticker (AAPL), CIK (0000320193), or name (Apple Inc)"
                    },
                    "include_financials": {
                        "type": "boolean",
                        "description": "Include 3-year income statement showing revenue and profit trends",
                        "default": True
                    },
                    "include_filings": {
                        "type": "boolean",
                        "description": "Include summary of last 5 SEC filings",
                        "default": True
                    },
                    "include_ownership": {
                        "type": "boolean",
                        "description": "Include insider and institutional ownership data (currently not implemented)",
                        "default": False
                    },
                    "detail_level": {
                        "type": "string",
                        "enum": ["minimal", "standard", "detailed"],
                        "description": "Response detail: 'minimal' (key metrics only), 'standard' (balanced), 'detailed' (comprehensive data)",
                        "default": "standard"
                    }
                },
                "required": ["identifier"]
            }
        ),
        Tool(
            name="edgar_analyze_financials",
            description="Detailed financial statement analysis across multiple periods. Use this for trend analysis, growth calculations, or comparing financial performance over time.",
            inputSchema={
                "type": "object",
                "properties": {
                    "company": {
                        "type": "string",
                        "description": "Company ticker (TSLA), CIK (0001318605), or name (Tesla Inc)"
                    },
                    "periods": {
                        "type": "integer",
                        "description": "Number of periods: 4-5 for trends, 8-10 for patterns (max 10)",
                        "default": 4
                    },
                    "annual": {
                        "type": "boolean",
                        "description": "Use annual periods (true) for long-term trends and year-over-year comparisons, or quarterly periods (false) for recent performance and current earnings. Quarterly provides more recent data but may show seasonal volatility.",
                        "default": True
                    },
                    "statement_types": {
                        "type": "array",
                        "items": {"type": "string", "enum": ["income", "balance", "cash_flow"]},
                        "description": "Statements to include: 'income' (revenue, profit, growth), 'balance' (assets, liabilities, equity), 'cash_flow' (operating, investing, financing cash flows)",
                        "default": ["income"]
                    }
                },
                "required": ["company"]
            }
        ),
        Tool(
            name="edgar_industry_overview",
            description="Get overview of an industry sector including company count, major players, and aggregate metrics. Use this to understand industry landscape before diving into specific companies.",
            inputSchema={
                "type": "object",
                "properties": {
                    "industry": {
                        "type": "string",
                        "enum": [
                            "pharmaceuticals", "biotechnology", "software",
                            "semiconductors", "banking", "investment",
                            "insurance", "real_estate", "oil_gas", "retail"
                        ],
                        "description": "Industry sector to analyze"
                    },
                    "include_top_companies": {
                        "type": "boolean",
                        "description": "Include list of major companies in the sector",
                        "default": True
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of top companies to show (by filing activity)",
                        "default": 10
                    }
                },
                "required": ["industry"]
            }
        ),
        Tool(
            name="edgar_compare_industry_companies",
            description="Compare financial performance of companies within an industry sector. Automatically selects top companies or accepts custom company list for side-by-side financial comparison.",
            inputSchema={
                "type": "object",
                "properties": {
                    "industry": {
                        "type": "string",
                        "enum": [
                            "pharmaceuticals", "biotechnology", "software",
                            "semiconductors", "banking", "investment",
                            "insurance", "real_estate", "oil_gas", "retail"
                        ],
                        "description": "Industry sector to analyze"
                    },
                    "companies": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional: Specific tickers to compare (e.g., ['AAPL', 'MSFT', 'GOOGL']). If omitted, uses top companies by market presence.",
                        "default": None
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of companies to compare if not specified (default 5, max 10)",
                        "default": 5
                    },
                    "periods": {
                        "type": "integer",
                        "description": "Number of periods for comparison (default 3)",
                        "default": 3
                    },
                    "annual": {
                        "type": "boolean",
                        "description": "Annual (true) or quarterly (false) comparison",
                        "default": True
                    }
                },
                "required": ["industry"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any] | None) -> list[TextContent]:
    """Handle tool calls."""
    if arguments is None:
        arguments = {}

    try:
        if name == "edgar_company_research":
            from edgar.ai.mcp.tools.company_research import handle_company_research
            return await handle_company_research(arguments)
        elif name == "edgar_analyze_financials":
            from edgar.ai.mcp.tools.financial_analysis import handle_analyze_financials
            return await handle_analyze_financials(arguments)
        elif name == "edgar_industry_overview":
            from edgar.ai.mcp.tools.industry_analysis import handle_industry_overview
            return await handle_industry_overview(arguments)
        elif name == "edgar_compare_industry_companies":
            from edgar.ai.mcp.tools.industry_analysis import handle_compare_industry_companies
            return await handle_compare_industry_companies(arguments)
        else:
            raise ValueError(f"Unknown tool: {name}")

    except Exception as e:
        logger.error("Error in tool %s: %s", name, e)
        return [TextContent(
            type="text",
            text=f"Error: {str(e)}"
        )]


@app.list_resources()
async def list_resources() -> list[Resource]:
    """List available resources."""
    return [
        Resource(
            uri="edgartools://docs/quickstart",
            name="EdgarTools Quickstart Guide",
            description="Quick start guide for using EdgarTools",
            mimeType="text/markdown"
        )
    ]


@app.read_resource()
async def read_resource(uri: str) -> str:
    """Read a resource."""
    if uri == "edgartools://docs/quickstart":
        return """# EdgarTools Quickstart

## Basic Usage

```python
from edgar import Company, get_current_filings

# Get company information
company = Company("AAPL")
print(f"{company.name} - CIK: {company.cik}")

# Get filings
filings = company.get_filings(form="10-K", limit=5)
for filing in filings:
    print(f"{filing.form} - {filing.filing_date}")

# Get current filings across all companies
current = get_current_filings(limit=20)
for filing in current.data.to_pylist():
    print(f"{filing['company']} - {filing['form']}")
```

## Available Tools

- **edgar_get_company**: Get detailed company information
- **edgar_current_filings**: Get the latest SEC filings

## Example Queries

- "Get information about Apple Inc including recent financials"
- "Show me the 20 most recent SEC filings"
- "Find current 8-K filings"
"""
    else:
        raise ValueError(f"Unknown resource: {uri}")


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
                        server_version=__version__,  # Sync with package version
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
    """Test that MCP server is properly configured and ready to run.

    Returns:
        bool: True if all checks pass, False otherwise
    """
    import sys

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
        print("  Install with: pip install edgartools[ai]")
        all_passed = False

    # Test 3: Identity configuration check
    identity = os.environ.get('EDGAR_IDENTITY')
    if identity:
        print(f"✓ EDGAR_IDENTITY configured: {identity}")
    else:
        print("⚠ EDGAR_IDENTITY not set (recommended)")
        print("  Set with: export EDGAR_IDENTITY=\"Your Name your@email.com\"")
        print("  Or configure in MCP client's env settings")

    # Test 4: Quick functionality test
    try:
        from edgar import get_current_filings
        print("✓ Core EdgarTools functionality available")
    except Exception as e:
        print(f"✗ EdgarTools functionality check failed: {e}")
        all_passed = False

    # Summary
    print()
    if all_passed:
        print("✓ All checks passed - MCP server is ready to run")
        print("\nTo start the server:")
        print("  python -m edgar.ai")
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
