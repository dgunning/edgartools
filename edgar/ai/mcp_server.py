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
        # New workflow-oriented tools
        Tool(
            name="edgar_company_research",
            description="Comprehensive company intelligence including profile, key financial metrics, recent filing activity, and ownership highlights",
            inputSchema={
                "type": "object",
                "properties": {
                    "identifier": {
                        "type": "string",
                        "description": "Company ticker, CIK, or name"
                    },
                    "include_financials": {
                        "type": "boolean",
                        "description": "Include latest financial metrics and statements",
                        "default": True
                    },
                    "include_filings": {
                        "type": "boolean",
                        "description": "Include recent filing activity summary",
                        "default": True
                    },
                    "include_ownership": {
                        "type": "boolean",
                        "description": "Include insider and institutional ownership highlights",
                        "default": False
                    },
                    "detail_level": {
                        "type": "string",
                        "enum": ["minimal", "standard", "detailed"],
                        "description": "Level of detail in response (affects token usage)",
                        "default": "standard"
                    }
                },
                "required": ["identifier"]
            }
        ),
        Tool(
            name="edgar_analyze_financials",
            description="Multi-period financial statement analysis including income statement, balance sheet, and cash flow statements across multiple quarters or years",
            inputSchema={
                "type": "object",
                "properties": {
                    "company": {
                        "type": "string",
                        "description": "Company ticker, CIK, or name"
                    },
                    "periods": {
                        "type": "integer",
                        "description": "Number of periods to analyze",
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
                        "description": "Financial statements to include",
                        "default": ["income"]
                    }
                },
                "required": ["company"]
            }
        ),
        # Existing tools (backward compatibility)
        Tool(
            name="edgar_get_company",
            description="Get comprehensive company information from SEC filings",
            inputSchema={
                "type": "object",
                "properties": {
                    "identifier": {
                        "type": "string",
                        "description": "Company ticker symbol, CIK, or name"
                    },
                    "include_financials": {
                        "type": "boolean",
                        "description": "Include latest financial statements",
                        "default": False
                    }
                },
                "required": ["identifier"]
            },
        ),
        Tool(
            name="edgar_current_filings",
            description="Get the most recent SEC filings",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Number of filings to return",
                        "default": 20
                    },
                    "form_type": {
                        "type": "string",
                        "description": "Filter by form type (e.g., '10-K', '10-Q')"
                    }
                }
            },
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any] | None) -> list[TextContent]:
    """Handle tool calls."""
    if arguments is None:
        arguments = {}

    try:
        # New workflow tools
        if name == "edgar_company_research":
            from edgar.ai.tools.company_research import handle_company_research
            return await handle_company_research(arguments)
        elif name == "edgar_analyze_financials":
            from edgar.ai.tools.financial_analysis import handle_analyze_financials
            return await handle_analyze_financials(arguments)
        # Existing tools (backward compatibility)
        elif name == "edgar_get_company":
            return await handle_get_company(arguments)
        elif name == "edgar_current_filings":
            return await handle_current_filings(arguments)
        else:
            raise ValueError(f"Unknown tool: {name}")

    except Exception as e:
        logger.error("Error in tool %s: %s", name, e)
        return [TextContent(
            type="text",
            text=f"Error: {str(e)}"
        )]


async def handle_get_company(args: dict[str, Any]) -> list[TextContent]:
    """Handle company information requests."""
    identifier = args.get("identifier", "")
    include_financials = args.get("include_financials", False)

    if not identifier:
        raise ValueError("identifier is required")

    try:
        # Import EdgarTools here to avoid import errors if not available
        from edgar import Company

        # Get company
        company = Company(identifier)

        # Build response text
        response_text = f"Company Information for {company.name}:\n\n"
        response_text += f"CIK: {company.cik}\n"

        # Add ticker if available
        if hasattr(company, 'ticker'):
            response_text += f"Ticker: {company.ticker}\n"
        elif hasattr(company, 'tickers') and company.tickers:
            response_text += f"Ticker: {company.tickers[0]}\n"
        elif hasattr(company, 'get_ticker'):
            try:
                ticker = company.get_ticker()
                response_text += f"Ticker: {ticker}\n"
            except:
                response_text += "Ticker: Not available\n"
        else:
            response_text += "Ticker: Not available\n"

        # Add description if available
        if hasattr(company, 'description'):
            response_text += f"Description: {company.description}\n"
        else:
            response_text += "Description: No description available\n"

        if include_financials:
            try:
                # Get recent filing for financial data
                filings = company.get_filings(form=["10-K", "10-Q"], limit=1)
                if filings:
                    latest_filing = filings[0]
                    response_text += "\nLatest Filing:\n"
                    response_text += f"- Form: {latest_filing.form}\n"
                    response_text += f"- Filing Date: {latest_filing.filing_date}\n"
                    if hasattr(latest_filing, 'period_of_report'):
                        response_text += f"- Period: {latest_filing.period_of_report}\n"
            except Exception as e:
                response_text += f"\nNote: Could not retrieve financial data: {str(e)}\n"

        return [TextContent(type="text", text=response_text)]

    except Exception as e:
        raise ValueError(f"Error retrieving company information: {str(e)}") from e


async def handle_current_filings(args: dict[str, Any]) -> list[TextContent]:
    """Handle current filings requests."""
    limit = args.get("limit", 20)
    form_type = args.get("form_type")

    try:
        from edgar import get_current_filings

        # Get current filings
        filings = get_current_filings(
            form=form_type or "",
            page_size=min(limit, 100)
        )

        # Convert to list
        filing_data = filings.data.to_pylist()

        # Build response
        response_text = f"Current SEC Filings (showing {len(filing_data)} filings)"
        if form_type:
            response_text += f" filtered by form type: {form_type}"
        response_text += "\n\n"

        for i, filing in enumerate(filing_data[:limit], 1):
            response_text += f"{i:2d}. {filing['form']:<6} - {filing['company'][:50]:<50} - {filing['filing_date']}\n"

        return [TextContent(type="text", text=response_text)]

    except Exception as e:
        raise ValueError(f"Error retrieving current filings: {str(e)}") from e


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
