"""
MCP Server implementation for EdgarTools.

This module provides the core MCP server that exposes EdgarTools functionality
to AI agents through the Model Context Protocol.
"""

import logging
from typing import Any, Dict

# Handle optional MCP import
try:
    from mcp import Resource, Tool
    from mcp.server import Server
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    # Stub classes for when MCP is not installed
    class Server:
        def __init__(self, name: str):
            raise ImportError("MCP not installed. Install with: pip install edgartools[ai]")
    class Tool:
        pass
    class Resource:
        pass

from edgar.ai.mcp.tools import CompanyTool, CurrentFilingsTool, FilingsTool, FinancialsTool, ScreeningTool, SearchTool

logger = logging.getLogger(__name__)


class MCPServer:
    """Base MCP Server class."""

    def __init__(self, name: str = "edgartools"):
        if not MCP_AVAILABLE:
            raise ImportError(
                "MCP support requires additional dependencies. "
                "Install with: pip install edgartools[ai]"
            )

        self.server = Server(name)
        self.tools = {}
        self.resources = {}

    def add_tool(self, tool: 'Tool'):
        """Add a tool to the server."""
        self.tools[tool.name] = tool
        self.server.add_tool(tool)

    def add_resource(self, resource: 'Resource'):
        """Add a resource to the server."""
        self.resources[resource.uri] = resource
        self.server.add_resource(resource)

    def run(self):
        """Run the MCP server."""
        self.server.run()


class EdgarToolsServer(MCPServer):
    """
    MCP Server implementation specifically for EdgarTools.

    This server exposes all EdgarTools functionality as MCP tools
    that can be called by AI agents.
    """

    def __init__(self, name: str = "edgartools"):
        super().__init__(name)
        self._register_tools()
        self._register_resources()

    def _register_tools(self):
        """Register all EdgarTools functionality as MCP tools."""

        # Company analysis tools
        self.add_tool(Tool(
            name="edgar_get_company",
            description="Get comprehensive company information from SEC filings",
            input_schema={
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
                    },
                    "include_filings": {
                        "type": "boolean",
                        "description": "Include recent filings list",
                        "default": False
                    }
                },
                "required": ["identifier"]
            },
            handler=CompanyTool.get_company
        ))

        # Filing retrieval and analysis
        self.add_tool(Tool(
            name="edgar_get_filings",
            description="Retrieve SEC filings for a company with filtering options",
            input_schema={
                "type": "object",
                "properties": {
                    "company": {
                        "type": "string",
                        "description": "Company identifier (ticker, CIK, or name)"
                    },
                    "form_type": {
                        "type": ["string", "array"],
                        "items": {"type": "string"},
                        "description": "Form type(s) to filter by (e.g., '10-K', '10-Q', '8-K')"
                    },
                    "date_from": {
                        "type": "string",
                        "format": "date",
                        "description": "Start date for filing search (YYYY-MM-DD)"
                    },
                    "date_to": {
                        "type": "string",
                        "format": "date",
                        "description": "End date for filing search (YYYY-MM-DD)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of filings to return",
                        "default": 10
                    }
                },
                "required": ["company"]
            },
            handler=FilingsTool.get_filings
        ))

        # Financial statement analysis
        self.add_tool(Tool(
            name="edgar_analyze_financials",
            description="Analyze financial statements and calculate key metrics",
            input_schema={
                "type": "object",
                "properties": {
                    "company": {
                        "type": "string",
                        "description": "Company identifier"
                    },
                    "statement_type": {
                        "type": "string",
                        "enum": ["income", "balance", "cash_flow", "all"],
                        "description": "Type of financial statement to analyze",
                        "default": "all"
                    },
                    "periods": {
                        "type": "integer",
                        "description": "Number of periods to analyze",
                        "default": 4
                    },
                    "include_ratios": {
                        "type": "boolean",
                        "description": "Calculate financial ratios",
                        "default": True
                    },
                    "include_trends": {
                        "type": "boolean",
                        "description": "Include trend analysis",
                        "default": True
                    }
                },
                "required": ["company"]
            },
            handler=FinancialsTool.analyze_financials
        ))

        # Search functionality
        self.add_tool(Tool(
            name="edgar_search",
            description="Search for companies or filings using various criteria",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (natural language supported)"
                    },
                    "search_type": {
                        "type": "string",
                        "enum": ["companies", "filings", "all"],
                        "description": "Type of search to perform",
                        "default": "all"
                    },
                    "filters": {
                        "type": "object",
                        "properties": {
                            "industry": {"type": "string"},
                            "sector": {"type": "string"},
                            "market_cap_min": {"type": "number"},
                            "market_cap_max": {"type": "number"},
                            "form_types": {
                                "type": "array",
                                "items": {"type": "string"}
                            }
                        }
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results to return",
                        "default": 20
                    }
                },
                "required": ["query"]
            },
            handler=SearchTool.search
        ))

        # Current filings monitoring
        self.add_tool(Tool(
            name="edgar_current_filings",
            description="Get the most recent SEC filings across all companies",
            input_schema={
                "type": "object",
                "properties": {
                    "form_type": {
                        "type": "string",
                        "description": "Filter by specific form type"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of filings to return",
                        "default": 20
                    },
                    "include_summary": {
                        "type": "boolean",
                        "description": "Include AI-generated summary of each filing",
                        "default": False
                    }
                }
            },
            handler=CurrentFilingsTool.get_current_filings
        ))

        # Stock screening
        self.add_tool(Tool(
            name="edgar_screen_stocks",
            description="Screen stocks based on fundamental criteria",
            input_schema={
                "type": "object",
                "properties": {
                    "criteria": {
                        "type": "object",
                        "description": "Screening criteria",
                        "properties": {
                            "min_revenue": {"type": "number"},
                            "max_pe_ratio": {"type": "number"},
                            "min_roe": {"type": "number"},
                            "min_revenue_growth": {"type": "number"},
                            "sector": {"type": "string"},
                            "profitable_only": {"type": "boolean"}
                        }
                    },
                    "sort_by": {
                        "type": "string",
                        "description": "Metric to sort results by",
                        "default": "market_cap"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results",
                        "default": 50
                    }
                },
                "required": ["criteria"]
            },
            handler=ScreeningTool.screen_stocks
        ))

    def _register_resources(self):
        """Register MCP resources for documentation and examples."""

        # API documentation resource
        self.add_resource(Resource(
            uri="edgartools://docs/api",
            name="EdgarTools API Documentation",
            description="Complete API documentation for EdgarTools",
            mimeType="text/markdown",
            handler=self._get_api_docs
        ))

        # Example queries resource
        self.add_resource(Resource(
            uri="edgartools://examples/queries",
            name="Example Queries",
            description="Common query patterns and examples",
            mimeType="application/json",
            handler=self._get_example_queries
        ))

    def _get_api_docs(self) -> str:
        """Return API documentation."""
        return """
# EdgarTools MCP API Documentation

## Overview
EdgarTools provides comprehensive access to SEC filing data through the Model Context Protocol.

## Available Tools

### edgar_get_company
Retrieve detailed company information including business description, financials, and filings.

### edgar_get_filings  
Search and retrieve SEC filings with powerful filtering options.

### edgar_analyze_financials
Perform financial analysis including ratios, trends, and peer comparisons.

### edgar_search
Natural language search across companies and filings.

### edgar_current_filings
Monitor the latest SEC filings in real-time.

### edgar_screen_stocks
Screen stocks based on fundamental criteria.

## Example Usage

```python
# Get Apple's latest 10-K
result = edgar_get_filings(
    company="AAPL",
    form_type="10-K",
    limit=1
)

# Analyze Microsoft's financials
analysis = edgar_analyze_financials(
    company="MSFT",
    periods=8,
    include_ratios=True
)
```
"""

    def _get_example_queries(self) -> Dict[str, Any]:
        """Return example queries for common use cases."""
        return {
            "examples": [
                {
                    "description": "Get basic company information",
                    "tool": "edgar_get_company",
                    "params": {
                        "identifier": "AAPL",
                        "include_financials": True
                    }
                },
                {
                    "description": "Find recent 8-K filings for Tesla",
                    "tool": "edgar_get_filings",
                    "params": {
                        "company": "TSLA",
                        "form_type": "8-K",
                        "limit": 5
                    }
                },
                {
                    "description": "Screen for profitable tech companies",
                    "tool": "edgar_screen_stocks",
                    "params": {
                        "criteria": {
                            "sector": "Technology",
                            "profitable_only": True,
                            "min_revenue_growth": 0.1
                        },
                        "sort_by": "revenue_growth",
                        "limit": 20
                    }
                }
            ]
        }


def run_edgar_mcp_server():
    """Convenience function to run the EdgarTools MCP server."""
    server = EdgarToolsServer()
    logger.info("Starting EdgarTools MCP server...")
    server.run()


if __name__ == "__main__":
    run_edgar_mcp_server()
