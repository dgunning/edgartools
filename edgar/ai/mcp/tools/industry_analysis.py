"""
Industry Analysis Tool Handlers

Provides industry sector analysis and competitive benchmarking capabilities.
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

# Industry function mapping
INDUSTRY_FUNCTIONS = {
    "pharmaceuticals": "get_pharmaceutical_companies",
    "biotechnology": "get_biotechnology_companies",
    "software": "get_software_companies",
    "semiconductors": "get_semiconductor_companies",
    "banking": "get_banking_companies",
    "investment": "get_investment_companies",
    "insurance": "get_insurance_companies",
    "real_estate": "get_real_estate_companies",
    "oil_gas": "get_oil_gas_companies",
    "retail": "get_retail_companies",
}


async def handle_industry_overview(args: dict[str, Any]) -> list[TextContent]:
    """
    Handle industry overview tool requests.

    Provides overview of an industry sector including:
    - Total company count
    - SIC code(s)
    - Major public companies
    - Industry description

    Args:
        args: Tool arguments containing:
            - industry (required): Industry sector name
            - include_top_companies (default True): Include major companies
            - limit (default 10): Number of top companies to show

    Returns:
        List containing TextContent with industry overview
    """
    industry = args.get("industry")
    include_top = args.get("include_top_companies", True)
    limit = args.get("limit", 10)

    if not industry:
        return [TextContent(
            type="text",
            text="Error: industry parameter is required"
        )]

    if industry not in INDUSTRY_FUNCTIONS:
        return [TextContent(
            type="text",
            text=f"Error: Unknown industry '{industry}'. Must be one of: {', '.join(INDUSTRY_FUNCTIONS.keys())}"
        )]

    try:
        # Import and call the appropriate industry function
        from edgar.ai import helpers
        function_name = INDUSTRY_FUNCTIONS[industry]
        get_companies = getattr(helpers, function_name)
        companies = get_companies()

        # Build response
        response_parts = [
            f"# {industry.replace('_', ' ').title()} Industry Overview",
            "",
            f"**Total Companies**: {len(companies):,}",
        ]

        # Get unique SIC codes
        sic_codes = sorted(companies['sic'].unique().tolist())
        if len(sic_codes) == 1:
            response_parts.append(f"**SIC Code**: {sic_codes[0]}")
        else:
            response_parts.append(f"**SIC Codes**: {', '.join(map(str, sic_codes))}")

        # Get primary description (from first company)
        if len(companies) > 0 and 'sic_description' in companies.columns:
            primary_desc = companies['sic_description'].iloc[0]
            response_parts.append(f"**Description**: {primary_desc}")

        response_parts.append("")

        # Add major companies if requested
        if include_top and len(companies) > 0:
            # Filter to companies with tickers (publicly traded)
            public = companies[companies['ticker'].notna()].copy()

            if len(public) > 0:
                response_parts.append("## Major Public Companies")
                response_parts.append("")

                # Show top N companies
                top_companies = public.head(limit)

                for _, row in top_companies.iterrows():
                    ticker = row['ticker'] if row['ticker'] else 'N/A'
                    exchange = row['exchange'] if row['exchange'] else 'N/A'
                    response_parts.append(
                        f"- **{ticker}** - {row['name']} ({exchange})"
                    )
            else:
                response_parts.append("*No public companies found in this sector*")

        # Combine response
        response_text = "\n".join(response_parts)

        # Check output size
        response_text = check_output_size(response_text)

        return [TextContent(type="text", text=response_text)]

    except Exception as e:
        logger.error(f"Error in industry overview: {e}", exc_info=True)
        return [TextContent(
            type="text",
            text=format_error_with_suggestions(e)
        )]


async def handle_compare_industry_companies(args: dict[str, Any]) -> list[TextContent]:
    """
    Handle industry company comparison tool requests.

    Compares financial performance of companies within an industry sector.

    Args:
        args: Tool arguments containing:
            - industry (required): Industry sector name
            - companies (optional): Specific tickers to compare
            - limit (default 5): Number of companies if not specified
            - periods (default 3): Number of periods for comparison
            - annual (default True): Annual (true) or quarterly (false)

    Returns:
        List containing TextContent with comparative analysis
    """
    industry = args.get("industry")
    company_tickers = args.get("companies")
    limit = args.get("limit", 5)
    periods = args.get("periods", 3)
    annual = args.get("annual", True)

    if not industry:
        return [TextContent(
            type="text",
            text="Error: industry parameter is required"
        )]

    if industry not in INDUSTRY_FUNCTIONS:
        return [TextContent(
            type="text",
            text=f"Error: Unknown industry '{industry}'. Must be one of: {', '.join(INDUSTRY_FUNCTIONS.keys())}"
        )]

    try:
        # Import and call the appropriate industry function
        from edgar.ai import helpers
        function_name = INDUSTRY_FUNCTIONS[industry]
        get_companies = getattr(helpers, function_name)
        companies = get_companies()

        # Select companies
        if company_tickers:
            # Filter to specified tickers
            selected = companies[companies['ticker'].isin(company_tickers)].copy()
            if len(selected) == 0:
                return [TextContent(
                    type="text",
                    text=f"Error: None of the specified tickers found in {industry} industry"
                )]
        else:
            # Use top N companies with tickers
            public = companies[companies['ticker'].notna()].copy()
            if len(public) == 0:
                return [TextContent(
                    type="text",
                    text=f"Error: No public companies found in {industry} industry"
                )]
            selected = public.head(limit)

        # Compare financials
        response_parts = [
            f"# {industry.replace('_', ' ').title()} Industry Comparison",
            f"",
            f"Comparing {len(selected)} companies over {periods} {'annual' if annual else 'quarterly'} periods",
            "",
        ]

        for _, row in selected.iterrows():
            ticker = row['ticker']
            try:
                company = Company(ticker)
                stmt = company.income_statement(
                    periods=periods,
                    annual=annual,
                    concise_format=True
                )

                response_parts.append(f"## {ticker} - {row['name']}")
                response_parts.append("")
                response_parts.append(stmt.to_llm_string())
                response_parts.append("")

            except Exception as e:
                logger.warning(f"Could not get financials for {ticker}: {e}")
                response_parts.append(f"## {ticker} - {row['name']}")
                response_parts.append(f"*Financial data not available: {str(e)}*")
                response_parts.append("")

        # Combine response
        response_text = "\n".join(response_parts)

        # Check output size (larger limit for comparative data)
        response_text = check_output_size(response_text, max_tokens=5000)

        return [TextContent(type="text", text=response_text)]

    except Exception as e:
        logger.error(f"Error in industry comparison: {e}", exc_info=True)
        return [TextContent(
            type="text",
            text=format_error_with_suggestions(e)
        )]
