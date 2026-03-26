"""
EdgarTools MCP Tools

Intent-based tools for SEC filing analysis:
- edgar_company: Company intelligence (profile, financials, filings, ownership)
- edgar_filing: Examine any filing by accession number or URL (structured context)
- edgar_read: Read specific sections from filings (risk factors, MD&A, etc.)
- edgar_search: Search companies and filings by metadata
- edgar_text_search: Full-text search across filing content (EFTS)
- edgar_compare: Compare companies or analyze industries
- edgar_ownership: Insider transactions, institutional holders, fund portfolios
- edgar_monitor: Latest SEC filings feed
- edgar_trends: Financial time series with growth rates
- edgar_screen: Discover companies by industry/exchange/state
- edgar_fund: Fund, ETF, BDC, money market data
- edgar_proxy: Executive compensation and governance
- edgar_notes: Notes and disclosures behind financial statement numbers
"""

from edgar.ai.mcp.tools.base import (
    TOOLS,
    ToolResponse,
    success,
    error,
    tool,
    resolve_company,
    get_tool_definitions,
    call_tool_handler,
)

__all__ = [
    # Registry
    "TOOLS",
    "get_tool_definitions",
    "call_tool_handler",
    # Response helpers
    "ToolResponse",
    "success",
    "error",
    # Decorator
    "tool",
    # Utilities
    "resolve_company",
]
