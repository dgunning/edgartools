"""
Search & Discovery Tool

Flexible search across SEC data: companies, filings, or both.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from edgar.ai.mcp.tools.base import (
    tool,
    success,
    error,
    resolve_company,
    format_filing_summary,
    get_error_suggestions,
)

logger = logging.getLogger(__name__)


@tool(
    name="edgar_search",
    description="""Search SEC data: companies, filings, or both.

Examples:
- Find companies: query="software", search_type="companies"
- Recent 10-Ks: form="10-K", search_type="filings", limit=20
- Company filings: identifier="AAPL", form="8-K", search_type="filings"
- Everything: query="artificial intelligence", search_type="all\"""",
    params={
        "query": {
            "type": "string",
            "description": "Search term for company name or description"
        },
        "search_type": {
            "type": "string",
            "enum": ["companies", "filings", "all"],
            "description": "What to search: companies, filings, or all",
            "default": "all"
        },
        "identifier": {
            "type": "string",
            "description": "Limit filing search to specific company (ticker/CIK)"
        },
        "form": {
            "type": "string",
            "description": "Filter filings by form type (10-K, 10-Q, 8-K, DEF 14A, 13F-HR, etc.)"
        },
        "limit": {
            "type": "integer",
            "description": "Maximum results per category (default 20)",
            "default": 20
        }
    },
    required=[]
)
async def edgar_search(
    query: Optional[str] = None,
    search_type: str = "all",
    identifier: Optional[str] = None,
    form: Optional[str] = None,
    limit: int = 20
) -> Any:
    """
    Search SEC data flexibly.

    Can search for companies, filings, or both depending on parameters.
    """
    result = {}
    next_steps = []

    try:
        # Search companies
        if search_type in ["companies", "all"] and query:
            companies = await _search_companies(query, limit)
            result["companies"] = companies
            if companies:
                next_steps.append("Use edgar_company with an identifier for detailed info")

        # Search filings
        if search_type in ["filings", "all"]:
            filings = await _search_filings(
                identifier=identifier,
                form=form,
                limit=limit
            )
            result["filings"] = filings
            if filings:
                next_steps.append("Use edgar_filing with accession_number to read content")

        # If nothing specified, give helpful guidance
        if not result:
            return error(
                "No search criteria provided",
                suggestions=[
                    "Add 'query' to search for companies",
                    "Add 'form' to search for specific filing types",
                    "Add 'identifier' to get filings for a specific company"
                ]
            )

        return success(result, next_steps=next_steps)

    except Exception as e:
        logger.exception("Error in edgar_search")
        return error(str(e), suggestions=get_error_suggestions(e))


async def _search_companies(query: str, limit: int) -> list[dict]:
    """Search for companies by name or keyword."""
    try:
        from edgar import find_company

        # find_company returns CompanySearchResults with top_n parameter
        matches = find_company(query, top_n=limit)

        if matches is None or len(matches) == 0:
            return []

        # CompanySearchResults has a results DataFrame with cik, ticker, company, score
        companies = []
        for _, row in matches.results.iterrows():
            company_dict = {
                "cik": str(row.cik),
                "name": row.company,
            }
            if row.ticker:
                company_dict["ticker"] = row.ticker
            if hasattr(row, 'score'):
                company_dict["match_score"] = int(row.score)
            companies.append(company_dict)

        return companies

    except Exception as e:
        logger.warning(f"Company search failed: {e}")
        return [{"error": str(e)}]


async def _search_filings(
    identifier: Optional[str] = None,
    form: Optional[str] = None,
    limit: int = 20
) -> list[dict]:
    """Search for filings, optionally filtered by company and/or form."""
    try:
        if identifier:
            # Search specific company's filings
            company = resolve_company(identifier)
            if form:
                filings = company.get_filings(form=form)
            else:
                filings = company.get_filings()
        else:
            # Search all recent filings
            from edgar import get_filings
            if form:
                filings = get_filings(form=form)
            else:
                filings = get_filings()

        # Convert to list to enable slicing (some filing types don't support direct slicing)
        filings_list = list(filings)[:limit]
        return [format_filing_summary(f) for f in filings_list]

    except Exception as e:
        logger.warning(f"Filing search failed: {e}")
        return [{"error": str(e)}]
