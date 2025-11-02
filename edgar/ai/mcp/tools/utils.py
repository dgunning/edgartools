"""
Utility functions for MCP tool handlers.

Provides helper functions for output management, error handling,
and data formatting for MCP responses.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def check_output_size(data: str, max_tokens: int = 2000) -> str:
    """
    Prevent context overflow with intelligent summarization.

    Estimates token count and truncates/summarizes if needed to stay
    within context window limits.

    Args:
        data: The text data to check
        max_tokens: Maximum allowed tokens (default: 2000)

    Returns:
        Original data if under limit, truncated data otherwise
    """
    # Rough estimation: 1 token ≈ 4 characters
    estimated_tokens = len(data) / 4

    if estimated_tokens > max_tokens:
        # Simple truncation with ellipsis
        # TODO: Implement smarter summarization in future
        char_limit = int(max_tokens * 4 * 0.9)  # 90% of limit to be safe
        truncated = data[:char_limit]
        logger.warning(f"Output truncated: {int(estimated_tokens)} tokens -> {max_tokens} tokens")
        return f"{truncated}\n\n... (output truncated to stay within token limit)"

    return data


def format_error_with_suggestions(error: Exception) -> str:
    """
    Provide helpful error messages with alternatives.

    Creates AI-friendly error messages that include specific suggestions
    for common error types.

    Args:
        error: The exception that occurred

    Returns:
        Formatted error message with suggestions
    """
    error_type = type(error).__name__
    error_message = str(error)

    # Define helpful suggestions for common errors
    suggestions_map = {
        "CompanyNotFound": [
            "Try searching by CIK instead of ticker",
            "Use the full company name",
            "Check spelling of ticker symbol"
        ],
        "NoFinancialsAvailable": [
            "Company may not have filed recent 10-K/10-Q",
            "Try include_financials=False for basic info",
            "Check filing history with edgar_market_monitor tool"
        ],
        "FileNotFoundError": [
            "The requested filing may not be available",
            "Try a different form type or date range",
            "Verify the company has filed this type of document"
        ],
        "HTTPError": [
            "SEC EDGAR website may be temporarily unavailable",
            "Check your internet connection",
            "Try again in a few moments"
        ],
        "ValueError": [
            "Check that all required parameters are provided",
            "Verify parameter formats (e.g., valid ticker symbols)",
            "Review the tool's parameter documentation"
        ]
    }

    suggestions = suggestions_map.get(error_type, [
        "Try rephrasing your request",
        "Check parameter values",
        "Consult the tool documentation"
    ])

    # Format the error response
    response_parts = [
        f"Error: {error_message}",
        f"Error Type: {error_type}",
        "",
        "Suggestions:"
    ]

    for i, suggestion in enumerate(suggestions, 1):
        response_parts.append(f"{i}. {suggestion}")

    return "\n".join(response_parts)


def build_company_profile(company: Any, detail_level: str = "standard") -> str:
    """
    Build a company profile summary.

    Args:
        company: Company object
        detail_level: Level of detail (minimal/standard/detailed)

    Returns:
        Formatted company profile text
    """
    parts = [f"Company: {company.name}"]

    # Add CIK
    parts.append(f"CIK: {company.cik}")

    # Add ticker if available
    if hasattr(company, 'tickers') and company.tickers:
        parts.append(f"Ticker: {company.tickers[0]}")

    # Add industry/sector if available and detail level permits
    if detail_level in ["standard", "detailed"]:
        if hasattr(company, 'sic_description'):
            parts.append(f"Industry: {company.sic_description}")

    # Add description for detailed level
    if detail_level == "detailed":
        if hasattr(company, 'description') and company.description:
            parts.append(f"\nDescription: {company.description}")

    return "\n".join(parts)
