"""
Company Research Tool Handler

Provides comprehensive company intelligence including profile,
financials, recent activity, and ownership information.
"""

import logging
from typing import Any

from mcp.types import TextContent

from edgar import Company
from edgar.ai.mcp.tools.utils import (
    build_company_profile,
    check_output_size,
    format_error_with_suggestions,
)

logger = logging.getLogger(__name__)


async def handle_company_research(args: dict[str, Any]) -> list[TextContent]:
    """
    Handle company research tool requests.

    Provides comprehensive company intelligence in one call, combining:
    - Company profile (name, CIK, ticker, industry)
    - Latest financial information (optional)
    - Recent filing activity (optional)
    - Ownership highlights (optional)

    Args:
        args: Tool arguments containing:
            - identifier (required): Company ticker, CIK, or name
            - include_financials (default True): Include latest financials
            - include_filings (default True): Include recent filing summary
            - include_ownership (default False): Include ownership highlights
            - detail_level (default "standard"): minimal/standard/detailed

    Returns:
        List containing TextContent with company research results
    """
    identifier = args.get("identifier")
    detail_level = args.get("detail_level", "standard")
    include_financials = args.get("include_financials", True)
    include_filings = args.get("include_filings", True)
    include_ownership = args.get("include_ownership", False)

    if not identifier:
        return [TextContent(
            type="text",
            text="Error: identifier parameter is required"
        )]

    try:
        # Get company
        company = Company(identifier)

        # Build response parts
        response_parts = []

        # 1. Company profile
        profile = build_company_profile(company, detail_level)
        response_parts.append(profile)

        # 2. Latest financials (if requested)
        if include_financials:
            try:
                financials = extract_latest_financials(company, detail_level)
                if financials:
                    response_parts.append("\n\nLatest Financials:")
                    response_parts.append(financials)
            except Exception as e:
                logger.warning(f"Could not retrieve financials: {e}")
                response_parts.append(f"\n\nFinancials: Not available ({str(e)})")

        # 3. Recent filings (if requested)
        if include_filings:
            try:
                filings = recent_filing_summary(company, detail_level)
                if filings:
                    response_parts.append("\n\nRecent Filings:")
                    response_parts.append(filings)
            except Exception as e:
                logger.warning(f"Could not retrieve filings: {e}")
                response_parts.append(f"\n\nRecent Filings: Not available ({str(e)})")

        # 4. Ownership highlights (if requested)
        if include_ownership:
            try:
                ownership = ownership_highlights(company)
                if ownership:
                    response_parts.append("\n\nOwnership Highlights:")
                    response_parts.append(ownership)
            except Exception as e:
                logger.warning(f"Could not retrieve ownership: {e}")
                response_parts.append(f"\n\nOwnership: Not available ({str(e)})")

        # Combine response
        response_text = "\n".join(response_parts)

        # Check output size and truncate if needed
        response_text = check_output_size(response_text)

        return [TextContent(type="text", text=response_text)]

    except Exception as e:
        logger.error(f"Error in company research: {e}", exc_info=True)
        return [TextContent(
            type="text",
            text=format_error_with_suggestions(e)
        )]


def extract_latest_financials(company: Any, detail_level: str = "standard") -> str:
    """
    Extract latest financial information for a company.

    Args:
        company: Company object
        detail_level: Level of detail to include

    Returns:
        Formatted financial summary
    """
    try:
        # Get income statement with 3 periods for trend analysis (annual) with concise format for LLM
        stmt = company.income_statement(periods=3, annual=True, concise_format=True)

        if detail_level == "minimal":
            # Just key metrics
            parts = ["Latest Annual Period"]
            # TODO: Extract specific metrics once we understand the API better
            return stmt.to_llm_string()
        else:
            # Standard or detailed
            return stmt.to_llm_string()

    except Exception as e:
        logger.warning(f"Could not extract financials: {e}")
        return ""


def recent_filing_summary(company: Any, detail_level: str = "standard") -> str:
    """
    Get summary of recent filing activity.

    Args:
        company: Company object
        detail_level: Level of detail to include

    Returns:
        Formatted filing summary
    """
    try:
        # Get recent filings (last 5)
        filings = company.get_filings(limit=5)

        if not filings:
            return "No recent filings found"

        parts = []
        for filing in filings:
            if detail_level == "minimal":
                parts.append(f"- {filing.form} ({filing.filing_date})")
            else:
                parts.append(f"- {filing.form} - {filing.filing_date}")
                if hasattr(filing, 'description') and filing.description:
                    parts.append(f"  {filing.description}")

        return "\n".join(parts)

    except Exception as e:
        logger.warning(f"Could not retrieve filings: {e}")
        return ""


def ownership_highlights(company: Any) -> str:
    """
    Get ownership highlights (insider/institutional activity).

    Args:
        company: Company object

    Returns:
        Formatted ownership summary
    """
    # TODO: Implement once we understand ownership data access
    # This might require analyzing Form 4 (insider) and 13F (institutional) filings
    logger.info("Ownership highlights not yet implemented")
    return "Ownership data: Feature not yet implemented"
