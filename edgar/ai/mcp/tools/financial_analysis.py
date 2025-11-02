"""
Financial Analysis Tool Handler

Provides multi-period financial statement analysis.
"""

import logging
from typing import Any

from mcp.types import TextContent

from edgar import Company
from edgar.ai.mcp.tools.utils import (
    check_output_size,
    format_error_with_suggestions,
)

logger = logging.getLogger(__name__)


async def handle_analyze_financials(args: dict[str, Any]) -> list[TextContent]:
    """
    Handle financial analysis tool requests.

    Provides multi-period financial statement analysis using Company
    convenience methods (income_statement, balance_sheet, cash_flow).

    Args:
        args: Tool arguments containing:
            - company (required): Company ticker, CIK, or name
            - periods (default 4): Number of periods to analyze
            - annual (default True): Annual (true) or quarterly (false)
            - statement_types (default ["income"]): Statements to include

    Returns:
        List containing TextContent with financial analysis results
    """
    company_id = args.get("company")
    periods = args.get("periods", 4)
    annual = args.get("annual", True)
    statement_types = args.get("statement_types", ["income"])

    if not company_id:
        return [TextContent(
            type="text",
            text="Error: company parameter is required"
        )]

    try:
        # Get company
        company = Company(company_id)

        # Extract requested statements
        response_parts = []
        response_parts.append(f"Financial Analysis: {company.name}")
        response_parts.append(f"Periods: {periods} {'Annual' if annual else 'Quarterly'}")
        response_parts.append("")

        # Process each requested statement type
        if "income" in statement_types:
            try:
                stmt = company.income_statement(periods=periods, annual=annual, concise_format=True)
                response_parts.append("=== Income Statement ===")
                response_parts.append(stmt.to_llm_string())
                response_parts.append("")
            except Exception as e:
                logger.warning(f"Could not retrieve income statement: {e}")
                response_parts.append(f"Income Statement: Not available ({str(e)})")
                response_parts.append("")

        if "balance" in statement_types:
            try:
                stmt = company.balance_sheet(periods=periods, annual=annual, concise_format=True)
                response_parts.append("=== Balance Sheet ===")
                response_parts.append(stmt.to_llm_string())
                response_parts.append("")
            except Exception as e:
                logger.warning(f"Could not retrieve balance sheet: {e}")
                response_parts.append(f"Balance Sheet: Not available ({str(e)})")
                response_parts.append("")

        if "cash_flow" in statement_types:
            try:
                stmt = company.cash_flow(periods=periods, annual=annual, concise_format=True)
                response_parts.append("=== Cash Flow Statement ===")
                response_parts.append(stmt.to_llm_string())
                response_parts.append("")
            except Exception as e:
                logger.warning(f"Could not retrieve cash flow: {e}")
                response_parts.append(f"Cash Flow: Not available ({str(e)})")
                response_parts.append("")

        # Combine response
        response_text = "\n".join(response_parts)

        # Check output size and truncate if needed
        response_text = check_output_size(response_text, max_tokens=3000)  # Larger limit for financials

        return [TextContent(type="text", text=response_text)]

    except Exception as e:
        logger.error(f"Error in financial analysis: {e}", exc_info=True)
        return [TextContent(
            type="text",
            text=format_error_with_suggestions(e)
        )]
