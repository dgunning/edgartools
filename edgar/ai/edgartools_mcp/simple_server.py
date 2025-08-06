#!/usr/bin/env python3
"""
Simple MCP server for EdgarTools.

This demonstrates the core functionality without the complex tool registration.
"""

import asyncio
from typing import Any, Sequence
import logging

from mcp.server import Server
from mcp import Resource, Tool
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolRequest,
    CallToolResult, 
    ListResourcesResult,
    ListToolsResult,
    ReadResourceResult,
    TextContent,
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("edgartools-mcp")

# Create the server
app = Server("edgartools")

@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
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
        if name == "edgar_get_company":
            return await handle_get_company(arguments)
        elif name == "edgar_current_filings":
            return await handle_current_filings(arguments)
        else:
            raise ValueError(f"Unknown tool: {name}")
            
    except Exception as e:
        logger.error(f"Error in tool {name}: {e}")
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
        
        # Build response
        response = {
            "name": company.name,
            "cik": company.cik,
            "description": getattr(company, 'description', 'No description available')
        }
        
        # Add ticker if available
        if hasattr(company, 'ticker'):
            response["ticker"] = company.ticker
        elif hasattr(company, 'tickers') and company.tickers:
            response["ticker"] = company.tickers[0]
        else:
            response["ticker"] = "Not available"
            
        if include_financials:
            try:
                # Get recent filing for financial data
                filings = company.get_filings(form=["10-K", "10-Q"], limit=1)
                if filings:
                    latest_filing = filings[0]
                    response["latest_filing"] = {
                        "form": latest_filing.form,
                        "filing_date": str(latest_filing.filing_date),
                        "period": getattr(latest_filing, 'period_of_report', 'N/A')
                    }
            except Exception as e:
                response["financials_error"] = str(e)
        
        text_response = f"""Company Information for {response['name']}:

CIK: {response['cik']}
Ticker: {response['ticker']}
Description: {response['description']}
"""
        
        if 'latest_filing' in response:
            filing = response['latest_filing']
            text_response += f"""
Latest Filing:
- Form: {filing['form']}
- Filing Date: {filing['filing_date']}
- Period: {filing['period']}
"""
        
        if 'financials_error' in response:
            text_response += f"\nNote: Could not retrieve financial data: {response['financials_error']}"
        
        return [TextContent(type="text", text=text_response)]
        
    except Exception as e:
        raise ValueError(f"Error retrieving company information: {str(e)}")

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
        text_response = f"Current SEC Filings (showing {len(filing_data)} filings)"
        if form_type:
            text_response += f" filtered by form type: {form_type}"
        text_response += "\n\n"
        
        for i, filing in enumerate(filing_data[:limit], 1):
            text_response += f"{i:2d}. {filing['form']:<6} - {filing['company'][:50]:<50} - {filing['filing_date']}\n"
        
        return [TextContent(type="text", text=text_response)]
        
    except Exception as e:
        raise ValueError(f"Error retrieving current filings: {str(e)}")

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

async def main():
    """Run the MCP server."""
    # Use stdio transport
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream, 
            write_stream, 
            InitializationOptions(
                server_name="edgartools",
                server_version="1.0.0",
                capabilities=app.get_capabilities(
                    notification_options=None,
                    experimental_capabilities={}
                )
            )
        )

if __name__ == "__main__":
    asyncio.run(main())