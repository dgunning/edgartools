"""
Screen Tool

Company discovery by industry (SIC), exchange, and state.
All filtering uses local reference data — zero SEC API calls.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from edgar.ai.mcp.tools.base import (
    tool,
    success,
    error,
    get_error_suggestions,
)

logger = logging.getLogger(__name__)


@tool(
    name="edgar_screen",
    description="""Discover companies by industry, exchange, or state. Returns matching
companies from SEC reference data — instant, no API calls.

Combine filters to narrow results (e.g., software companies on NYSE in Delaware).

Examples:
- By industry keyword: industry="software"
- By SIC code: sic=2834 (pharmaceutical)
- By exchange: exchange="NYSE"
- By state: state="DE" (Delaware)
- Combined: industry="semiconductor", exchange="Nasdaq", limit=20""",
    params={
        "industry": {
            "type": "string",
            "description": "Industry keyword to search SIC descriptions (e.g., 'software', 'pharmaceutical', 'banking')"
        },
        "sic": {
            "type": "integer",
            "description": "Exact SIC code (e.g., 2834 for pharma, 7372 for software)"
        },
        "exchange": {
            "type": "string",
            "enum": ["NYSE", "Nasdaq", "OTC", "CBOE"],
            "description": "Stock exchange filter"
        },
        "state": {
            "type": "string",
            "description": "US state code for state of incorporation (e.g., 'DE', 'CA', 'NY')"
        },
        "limit": {
            "type": "integer",
            "description": "Max companies to return (default 25, max 100)",
            "default": 25
        }
    },
    required=[]
)
async def edgar_screen(
    industry: Optional[str] = None,
    sic: Optional[int] = None,
    exchange: Optional[str] = None,
    state: Optional[str] = None,
    limit: int = 25,
) -> Any:
    """Discover companies by industry, exchange, or state."""
    try:
        if not any([industry, sic, exchange, state]):
            return error(
                "At least one filter required",
                suggestions=[
                    "Use industry='software' to find software companies",
                    "Use exchange='NYSE' to list NYSE-listed companies",
                    "Use state='DE' to find Delaware-incorporated companies",
                    "Use sic=2834 for pharmaceutical companies",
                ]
            )

        limit = min(max(limit, 1), 100)

        from edgar.reference import (
            get_companies_by_industry,
            get_companies_by_exchanges,
            get_companies_by_state,
        )

        df = None

        # Apply industry/SIC filter
        if industry or sic:
            df = get_companies_by_industry(
                sic=sic,
                sic_description_contains=industry,
            )

        # Apply exchange filter
        if exchange:
            if df is not None:
                df = df[df['exchange'] == exchange]
            else:
                df = get_companies_by_exchanges(exchange)

        # Apply state filter
        if state:
            if df is not None:
                if 'state_of_incorporation' in df.columns:
                    df = df[df['state_of_incorporation'] == state.upper()]
            else:
                df = get_companies_by_state(state.upper())

        if df is None or df.empty:
            return error(
                "No companies match the specified filters",
                suggestions=[
                    "Try a broader industry keyword",
                    "Check state code (use 2-letter abbreviation like 'DE', 'CA')",
                    "Try a different exchange",
                ]
            )

        # Build response
        total = len(df)
        df = df.head(limit)

        companies = []
        for _, row in df.iterrows():
            company = {
                "cik": str(row.get('cik', '')),
                "name": row.get('name') or row.get('company', ''),
            }
            ticker = row.get('ticker')
            if ticker and str(ticker) != 'nan' and str(ticker) != 'None':
                company["ticker"] = str(ticker)
            ex = row.get('exchange')
            if ex and str(ex) != 'nan' and str(ex) != 'None':
                company["exchange"] = str(ex)
            sic_desc = row.get('sic_description')
            if sic_desc and str(sic_desc) != 'nan':
                company["industry"] = str(sic_desc)

            companies.append(company)

        result = {
            "companies": companies,
            "count": len(companies),
            "total_matches": total,
        }

        # Describe active filters
        filters = {}
        if industry:
            filters["industry"] = industry
        if sic:
            filters["sic"] = sic
        if exchange:
            filters["exchange"] = exchange
        if state:
            filters["state"] = state
        result["filters"] = filters

        if total > limit:
            result["note"] = f"Showing {limit} of {total} matches. Increase limit for more."

        next_steps = [
            "Use edgar_company with a ticker or CIK for detailed company analysis",
            "Use edgar_compare with multiple tickers to compare companies",
            "Use edgar_trends to analyze financial trends for a company",
        ]

        return success(result, next_steps=next_steps)

    except Exception as e:
        logger.exception("Error in edgar_screen")
        return error(str(e), suggestions=get_error_suggestions(e))
