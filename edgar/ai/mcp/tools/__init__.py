"""
EdgarTools MCP Tools

Intent-based tools for SEC filing analysis:
- edgar_company: Company intelligence (profile, financials, filings, ownership)
- edgar_search: Search companies and filings
- edgar_filing: Read filing content and sections
- edgar_compare: Compare companies or analyze industries
- edgar_ownership: Insider transactions, institutional holders, fund portfolios
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

# Keep legacy utilities for backwards compatibility
from edgar.ai.mcp.tools.utils import (
    check_output_size,
    format_error_with_suggestions,
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
    # Legacy
    "check_output_size",
    "format_error_with_suggestions",
]
