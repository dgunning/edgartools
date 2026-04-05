"""
Monitor Tool

Real-time SEC filings feed. No other MCP server offers this capability.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from edgar.ai.mcp.tools.base import (
    tool,
    success,
    error,
    format_filing_summary,
    get_error_suggestions,
)

logger = logging.getLogger(__name__)


@tool(
    name="edgar_monitor",
    description="""Get the latest SEC filings in real-time (updated every few minutes).

Returns today's filings from the SEC's live feed. Use this to monitor new filings,
track 8-K events, or see insider trades as they happen.

Examples:
- Latest filings: (no parameters)
- Today's 8-Ks: form="8-K"
- Insider trades: form="4"
- Latest 10-Ks: form="10-K"
- More results: limit=50""",
    params={
        "form": {
            "type": "string",
            "description": "Filter by form type (e.g., '8-K', '4', '10-K', '10-Q', '13F-HR')"
        },
        "limit": {
            "type": "integer",
            "description": "Max filings to return (default 20, max 100)",
            "default": 20
        }
    },
    required=[]
)
async def edgar_monitor(
    form: Optional[str] = None,
    limit: int = 20,
) -> Any:
    """Get the latest SEC filings from the live feed."""
    try:
        from edgar import get_current_filings

        limit = min(max(limit, 1), 100)

        # Fetch current filings
        current = get_current_filings(form=form or '', page_size=limit)

        filings_list = []
        for filing in current:
            summary = format_filing_summary(filing)
            # Add accepted time if available
            if hasattr(filing, 'accepted_datetime') and filing.accepted_datetime:
                summary["accepted"] = str(filing.accepted_datetime)
            filings_list.append(summary)

            if len(filings_list) >= limit:
                break

        result = {
            "filings": filings_list,
            "count": len(filings_list),
        }

        if form:
            result["form_filter"] = form

        next_steps = [
            "Use edgar_filing with an accession_number to read a specific filing's content",
            "Use edgar_company to get full company analysis",
        ]

        return success(result, next_steps=next_steps)

    except Exception as e:
        logger.exception("Error in edgar_monitor")
        return error(str(e), suggestions=get_error_suggestions(e))
