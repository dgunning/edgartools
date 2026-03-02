"""
Text Search Tool

Full-text search across SEC filings using EDGAR EFTS.
Thin MCP wrapper around edgar.search.efts.search_filings().
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
    name="edgar_text_search",
    description="""Full-text search across all SEC filings. Searches the actual text
content of filings — find filings that mention specific topics, products, risks, etc.

This searches EDGAR's EFTS (Electronic Full-Text Search) index, which covers
all filing text content, not just metadata.

Examples:
- Topic search: query="artificial intelligence"
- Scoped to form: query="cybersecurity incident", forms=["8-K"]
- Date range: query="supply chain disruption", start_date="2024-01-01", end_date="2024-12-31"
- Company + topic: query="tariff impact", forms=["10-K"], identifier="AAPL\"""",
    params={
        "query": {
            "type": "string",
            "description": "Full-text search query (searches filing content)"
        },
        "forms": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Filter by form types (e.g., ['10-K', '8-K']). Default: all forms."
        },
        "identifier": {
            "type": "string",
            "description": "Optional company ticker or CIK to scope results"
        },
        "start_date": {
            "type": "string",
            "description": "Start date for filing date range (YYYY-MM-DD)"
        },
        "end_date": {
            "type": "string",
            "description": "End date for filing date range (YYYY-MM-DD)"
        },
        "limit": {
            "type": "integer",
            "description": "Max results to return (default 20, max 50)",
            "default": 20
        }
    },
    required=["query"]
)
async def edgar_text_search(
    query: str,
    forms: Optional[list[str]] = None,
    identifier: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 20,
) -> Any:
    """Full-text search across SEC filings via EFTS."""
    try:
        if not query or not query.strip():
            return error(
                "Search query cannot be empty",
                suggestions=[
                    "Provide a search term like 'artificial intelligence'",
                    "Use forms parameter to filter by filing type",
                ]
            )

        from edgar.search.efts import search_filings

        # Resolve identifier to ticker or CIK for the library function
        ticker = None
        cik = None
        if identifier:
            cleaned = identifier.strip()
            if cleaned.isdigit():
                cik = cleaned
            else:
                ticker = cleaned

        search_result = search_filings(
            query,
            forms=forms,
            ticker=ticker,
            cik=cik,
            start_date=start_date,
            end_date=end_date,
            limit=min(limit, 50),
        )

        # Serialize to MCP response
        results = []
        for r in search_result:
            filing_result = {
                "accession_number": r.accession_number,
                "form": r.form,
                "filed": r.filed,
            }
            if r.company:
                filing_result["company"] = r.company
            if r.cik:
                filing_result["cik"] = r.cik
            if r.period:
                filing_result["period"] = r.period
            results.append(filing_result)

        result = {
            "query": query,
            "total_matches": search_result.total,
            "count": len(results),
            "results": results,
        }

        if forms:
            result["forms_filter"] = forms
        if start_date or end_date:
            result["date_range"] = {"start": start_date, "end": end_date}

        if search_result.total > len(results):
            result["note"] = f"Showing {len(results)} of {search_result.total} matches. Increase limit for more."

        next_steps = [
            "Use edgar_filing with an accession_number to read the full filing content",
            "Use edgar_company with a CIK to get company details",
        ]

        return success(result, next_steps=next_steps)

    except ValueError as e:
        return error(str(e), suggestions=get_error_suggestions(e))
    except Exception as e:
        logger.exception("Error in edgar_text_search")
        return error(
            f"Search error: {e}",
            suggestions=[
                "SEC EFTS may be temporarily unavailable",
                "Try a simpler query",
                "Check date format (YYYY-MM-DD)",
            ]
        )
