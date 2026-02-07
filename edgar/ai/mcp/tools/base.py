"""
Base utilities for MCP tool handlers.

Provides the tool registry, response helpers, and common utilities
for building intent-based MCP tools.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from functools import wraps
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# Global tool registry
TOOLS: dict[str, dict[str, Any]] = {}


# =============================================================================
# RESPONSE TYPES
# =============================================================================

@dataclass
class ToolResponse:
    """
    Structured tool response for consistent AI-friendly output.

    All tools return this type, which gets serialized to JSON.
    """
    success: bool
    data: Any = None
    error: Optional[str] = None
    suggestions: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary, excluding None values."""
        result = {"success": self.success}
        if self.data is not None:
            result["data"] = self.data
        if self.error:
            result["error"] = self.error
        if self.suggestions:
            result["suggestions"] = self.suggestions
        if self.next_steps:
            result["next_steps"] = self.next_steps
        return result

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2, default=str)


def success(
    data: Any,
    next_steps: Optional[list[str]] = None
) -> ToolResponse:
    """Create a successful response."""
    return ToolResponse(
        success=True,
        data=data,
        next_steps=next_steps or []
    )


def error(
    message: str,
    suggestions: Optional[list[str]] = None
) -> ToolResponse:
    """Create an error response with helpful suggestions."""
    return ToolResponse(
        success=False,
        error=message,
        suggestions=suggestions or []
    )


# =============================================================================
# TOOL REGISTRY
# =============================================================================

def tool(
    name: str,
    description: str,
    params: dict[str, Any],
    required: Optional[list[str]] = None
):
    """
    Decorator to register MCP tools declaratively.

    Example:
        @tool(
            name="edgar_company",
            description="Get company information",
            params={
                "identifier": {
                    "type": "string",
                    "description": "Company ticker, CIK, or name"
                }
            },
            required=["identifier"]
        )
        async def edgar_company(identifier: str) -> ToolResponse:
            ...
    """
    def decorator(func: Callable) -> Callable:
        TOOLS[name] = {
            "name": name,
            "description": description,
            "handler": func,
            "schema": {
                "type": "object",
                "properties": params,
                "required": required or []
            }
        }

        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def get_tool_definitions() -> list[dict]:
    """Get all tool definitions for MCP list_tools."""
    return [
        {
            "name": info["name"],
            "description": info["description"],
            "inputSchema": info["schema"]
        }
        for info in TOOLS.values()
    ]


async def call_tool_handler(name: str, arguments: dict[str, Any]) -> ToolResponse:
    """
    Route a tool call to its handler.

    Args:
        name: Tool name
        arguments: Tool arguments

    Returns:
        ToolResponse from the handler
    """
    if name not in TOOLS:
        return error(
            f"Unknown tool: {name}",
            suggestions=[f"Available tools: {', '.join(TOOLS.keys())}"]
        )

    handler = TOOLS[name]["handler"]

    try:
        result = await handler(**arguments)
        return result
    except TypeError as e:
        # Missing or invalid arguments
        return error(
            f"Invalid arguments: {e}",
            suggestions=["Check required parameters", "Verify parameter types"]
        )
    except Exception as e:
        logger.exception(f"Tool {name} failed")
        return error(f"Tool error: {e}")


# =============================================================================
# COMPANY RESOLUTION
# =============================================================================

def resolve_company(identifier: str):
    """
    Resolve flexible identifier to Company object.

    Handles:
    - Ticker symbols (AAPL, MSFT)
    - CIK numbers (320193, 0000320193)
    - Company names (Apple Inc)

    Args:
        identifier: Company identifier in any supported format

    Returns:
        Company object

    Raises:
        ValueError: If company cannot be found
    """
    from edgar import Company

    if not identifier or not identifier.strip():
        raise ValueError("Company identifier cannot be empty")

    # Clean the identifier
    cleaned = identifier.strip()

    try:
        return Company(cleaned)
    except Exception as original_error:
        # Try uppercase for tickers
        if cleaned.upper() != cleaned:
            try:
                return Company(cleaned.upper())
            except Exception as e:
                logger.debug(f"Uppercase lookup failed for '{cleaned}': {e}")

        # Try removing leading zeros for CIK
        if cleaned.isdigit():
            try:
                return Company(str(int(cleaned)))
            except Exception as e:
                logger.debug(f"CIK lookup failed for '{cleaned}': {e}")

        raise ValueError(
            f"Could not find company: '{identifier}'. "
            "Try a ticker (AAPL), CIK (320193), or exact company name."
        ) from original_error


# =============================================================================
# OUTPUT HELPERS
# =============================================================================

def truncate_text(text: str, max_chars: int = 8000) -> str:
    """
    Truncate text to stay within token limits.

    Args:
        text: Text to truncate
        max_chars: Maximum characters (roughly 4 chars per token)

    Returns:
        Truncated text with indicator if truncated
    """
    if len(text) <= max_chars:
        return text

    truncated = text[:max_chars]
    # Try to break at a newline
    last_newline = truncated.rfind('\n')
    if last_newline > max_chars * 0.8:
        truncated = truncated[:last_newline]

    return f"{truncated}\n\n... (truncated)"


def format_filing_summary(filing) -> dict:
    """Format a filing object as a summary dict."""
    return {
        "accession_number": filing.accession_number,
        "form": filing.form,
        "filed": str(filing.filing_date),
        "company": getattr(filing, 'company', None),
        "cik": str(filing.cik) if hasattr(filing, 'cik') else None,
    }


def format_company_profile(company) -> dict:
    """Format a company object as a profile dict."""
    profile = {
        "cik": str(company.cik),
        "name": company.name,
    }

    # Add optional fields if available
    if hasattr(company, 'tickers') and company.tickers:
        profile["tickers"] = company.tickers

    if hasattr(company, 'sic') and company.sic:
        profile["sic"] = company.sic

    if hasattr(company, 'sic_description') and company.sic_description:
        profile["industry"] = company.sic_description

    if hasattr(company, 'state_of_incorporation'):
        profile["state"] = company.state_of_incorporation

    if hasattr(company, 'fiscal_year_end'):
        profile["fiscal_year_end"] = company.fiscal_year_end

    return profile


# =============================================================================
# ERROR SUGGESTIONS
# =============================================================================

ERROR_SUGGESTIONS = {
    "CompanyNotFound": [
        "Try searching by CIK instead of ticker",
        "Use the full company name",
        "Check spelling of ticker symbol"
    ],
    "NoFinancialsAvailable": [
        "Company may not have filed recent 10-K/10-Q",
        "Try a different time period",
        "Some companies (funds, REITs) have different statement formats"
    ],
    "ValueError": [
        "Check that required parameters are provided",
        "Verify parameter formats",
    ],
    "HTTPError": [
        "SEC EDGAR may be temporarily unavailable",
        "Try again in a few moments"
    ],
}


def get_error_suggestions(error: Exception) -> list[str]:
    """Get helpful suggestions for an error type."""
    error_type = type(error).__name__
    return ERROR_SUGGESTIONS.get(error_type, [
        "Check parameter values",
        "Try a different approach"
    ])
