"""
Filing Tool (edgar_filing)

The primary tool for examining any SEC filing. Takes an accession number or
SEC URL and returns structured context: what the filing is, key data, and
available actions. Uses to_context() from the filing's typed data object
when available (TenK, Form4, ThirteenF, etc.).
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

from edgar.ai.mcp.tools.base import (
    tool,
    success,
    error,
    get_error_suggestions,
)

logger = logging.getLogger(__name__)

# Regex for dashed accession number: 0000320193-23-000077
_ACCESSION_DASHED = re.compile(r'(\d{10}-\d{2}-\d{6})')
# Regex for undashed accession number in paths: 000032019323000077
_ACCESSION_UNDASHED = re.compile(r'(?<!\d)(\d{18})(?!\d)')


def _extract_accession(text: str) -> Optional[str]:
    """Extract an accession number from a string, URL, or raw accession number."""
    if not text:
        return None
    text = text.strip()

    # Try dashed format first
    m = _ACCESSION_DASHED.search(text)
    if m:
        return m.group(1)

    # Try undashed format (18 consecutive digits)
    m = _ACCESSION_UNDASHED.search(text)
    if m:
        d = m.group(1)
        return f"{d[:10]}-{d[10:12]}-{d[12:]}"

    return None


@tool(
    name="edgar_filing",
    description="""Use this when you have a specific SEC filing to examine. Takes an accession number or any SEC URL and returns structured context: what the filing is, key data points, and available next steps.

If the filing has a typed data object (10-K, 10-Q, 8-K, Form 4, 13F, DEF 14A, etc.), returns that object's extracted data — financials, sections, ownership, transactions, etc.

Accepts accession numbers ("0000320193-23-000077"), SEC URLs, or any text containing an accession number.

Examples:
- Filing by accession: input="0000320193-23-000077"
- Filing from URL: input="https://www.sec.gov/Archives/edgar/data/320193/000032019323000077/..."
- Minimal overview: input="0000320193-23-000077", detail="minimal\"""",
    params={
        "input": {
            "type": "string",
            "description": "Accession number or URL containing an accession number"
        },
        "detail": {
            "type": "string",
            "enum": ["minimal", "standard", "full"],
            "description": "Detail level for context output (default: standard)",
            "default": "standard"
        }
    },
    required=["input"]
)
async def edgar_filing(
    input: str,
    detail: str = "standard",
) -> Any:
    """Get AI context for a filing by accession number or URL."""
    try:
        # Extract accession number
        accession = _extract_accession(input)
        if not accession:
            return error(
                f"Could not find an accession number in: {input[:100]}",
                suggestions=[
                    "Provide a dashed accession number like '0000320193-23-000077'",
                    "Or a SEC URL containing an accession number",
                ]
            )

        # Look up the filing
        from edgar import find
        filing = find(search_id=accession)
        if filing is None:
            return error(
                f"Filing not found: {accession}",
                suggestions=[
                    "Check the accession number is correct",
                    "Use edgar_search to find filings by company or form type",
                ]
            )

        # Try to get the typed data object
        obj = None
        obj_type = None
        try:
            obj = filing.obj()
            if obj is not None:
                obj_type = type(obj).__name__
        except Exception:
            pass

        # Build context using to_context()
        if obj is not None and hasattr(obj, 'to_context'):
            context_text = obj.to_context(detail=detail)
            source = "data_object"
        else:
            context_text = filing.to_context(detail=detail)
            source = "filing"

        result = {
            "accession_number": accession,
            "form": filing.form,
            "company": getattr(filing, 'company', None),
            "filed": str(filing.filing_date),
            "source": source,
            "context": context_text,
        }

        if obj_type:
            result["data_object_type"] = obj_type

        next_steps = []
        if source == "filing":
            next_steps.append("Use edgar_read to extract specific sections from this filing")
        if obj_type:
            next_steps.append(f"Filing parsed as {obj_type} — see AVAILABLE ACTIONS in context")
            next_steps.append("Use edgar_read to extract section text (risk_factors, mda, business, etc.)")
        next_steps.append("Use edgar_company for full company profile")

        return success(result, next_steps=next_steps)

    except Exception as e:
        logger.exception("Error in edgar_context")
        return error(str(e), suggestions=get_error_suggestions(e))
