"""
Filing Reader Tool

Read SEC filing content - full filing or specific sections.
Handles 10-K, 10-Q, 8-K, proxy statements, and other form types.
"""

from __future__ import annotations

import logging
from typing import Any, Optional
from edgar import find
from edgar.ai.mcp.tools.base import (
    tool,
    success,
    error,
    resolve_company,
    format_filing_summary,
    get_error_suggestions,
    truncate_text,
)

logger = logging.getLogger(__name__)

# Section mapping for different form types
SECTION_MAP_10K = {
    "business": "item1",
    "risk_factors": "item1a",
    "mda": "item7",
    "financials": "item8",
    "controls": "item9a",
    "legal": "item3",
}

SECTION_MAP_10Q = {
    "financials": "part1item1",
    "mda": "part1item2",
    "risk_factors": "part2item1a",
    "legal": "part2item1",
}


@tool(
    name="edgar_filing",
    description="""Read SEC filing content. Get full filing metadata or specific sections.

For 10-K/10-Q: extracts business description, risk factors, MD&A, financials.
For 8-K: extracts event items.
For proxy (DEF 14A): extracts compensation, governance info.

Examples:
- Get filing: accession_number="0000320193-23-000077"
- Latest 10-K sections: identifier="AAPL", form="10-K", sections=["business", "risk_factors"]
- Full content: accession_number="...", sections=["all"]""",
    params={
        "accession_number": {
            "type": "string",
            "description": "Filing accession number (e.g., 0000320193-23-000077)"
        },
        "identifier": {
            "type": "string",
            "description": "Company identifier (alternative - gets most recent filing of form type)"
        },
        "form": {
            "type": "string",
            "description": "Form type (used with identifier to get most recent)"
        },
        "sections": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": ["summary", "business", "risk_factors", "mda", "financials", "all"]
            },
            "description": "Sections to extract. 'summary' (default) gives metadata only. 'all' extracts everything.",
            "default": ["summary"]
        }
    },
    required=[]
)
async def edgar_filing(
    accession_number: Optional[str] = None,
    identifier: Optional[str] = None,
    form: Optional[str] = None,
    sections: Optional[list[str]] = None
) -> Any:
    """
    Read SEC filing content.

    Can retrieve by accession number or find the most recent filing
    of a given type for a company.
    """
    sections = sections or ["summary"]

    try:
        # Get the filing
        filing = await _get_filing(accession_number, identifier, form)
        if filing is None:
            return error(
                "Could not find filing",
                suggestions=[
                    "Provide accession_number for a specific filing",
                    "Or provide identifier + form for most recent"
                ]
            )

        # Build response with metadata
        result = {
            "filing": format_filing_summary(filing),
            "form_type": filing.form,
        }

        # Determine available sections based on form type
        if filing.form in ["10-K", "10-K/A"]:
            result["available_sections"] = list(SECTION_MAP_10K.keys())
        elif filing.form in ["10-Q", "10-Q/A"]:
            result["available_sections"] = list(SECTION_MAP_10Q.keys())
        else:
            result["available_sections"] = ["full_text"]

        # Extract requested sections
        if "summary" not in sections or len(sections) > 1:
            extracted = await _extract_sections(filing, sections)
            result["sections"] = extracted

        # Next steps
        next_steps = []
        if "summary" in sections and len(sections) == 1:
            next_steps.append("Add sections like 'business', 'risk_factors', 'mda' to read content")
        next_steps.append("Use edgar_company for full company analysis")

        return success(result, next_steps=next_steps)

    except Exception as e:
        logger.exception("Error in edgar_filing")
        return error(str(e), suggestions=get_error_suggestions(e))


async def _get_filing(
    accession_number: Optional[str],
    identifier: Optional[str],
    form: Optional[str]
):
    """Get filing by accession number or company+form."""
    from edgar import Filing

    if accession_number:
        # Direct lookup by accession number
        try:
            # Handle both formats: with and without dashes
            clean_accession = accession_number.replace("-", "")
            # Try the Filing constructor
            return find(search_id=accession_number)
        except Exception:
            # Try fetching from company filings if direct lookup fails
            pass

    if identifier and form:
        # Get most recent filing of this type for company
        company = resolve_company(identifier)
        filings = company.get_filings(form=form)
        if filings and len(filings) > 0:
            return filings[0]

    return None


async def _extract_sections(filing, sections: list[str]) -> dict[str, Any]:
    """Extract requested sections from filing."""
    extracted = {}

    try:
        # Get the typed object (TenK, TenQ, EightK, etc.)
        obj = filing.obj()

        if "all" in sections:
            # Extract all available sections
            sections_to_extract = _get_section_list(filing.form)
        else:
            sections_to_extract = [s for s in sections if s != "summary"]

        for section in sections_to_extract:
            content = _extract_section(obj, filing.form, section)
            if content:
                extracted[section] = truncate_text(str(content), max_chars=6000)
            else:
                extracted[section] = None

    except Exception as e:
        logger.warning(f"Could not extract sections: {e}")
        extracted["error"] = str(e)

        # Try to get raw text as fallback
        try:
            if hasattr(filing, 'text'):
                extracted["raw_text_preview"] = truncate_text(filing.text(), max_chars=4000)
        except:
            pass

    return extracted


def _get_section_list(form_type: str) -> list[str]:
    """Get list of extractable sections for a form type."""
    if form_type in ["10-K", "10-K/A"]:
        return list(SECTION_MAP_10K.keys())
    elif form_type in ["10-Q", "10-Q/A"]:
        return list(SECTION_MAP_10Q.keys())
    else:
        return ["full_text"]


def _extract_section(obj, form_type: str, section: str) -> Optional[str]:
    """Extract a specific section from a filing object."""

    # Try direct attribute access first
    section_attrs = [
        section,
        section.replace("_", ""),
        f"item_{section}",
    ]

    for attr in section_attrs:
        if hasattr(obj, attr):
            value = getattr(obj, attr)
            if value is not None:
                return str(value)

    # Try mapped section names
    if form_type in ["10-K", "10-K/A"]:
        mapped = SECTION_MAP_10K.get(section)
        if mapped and hasattr(obj, mapped):
            return str(getattr(obj, mapped))

    elif form_type in ["10-Q", "10-Q/A"]:
        mapped = SECTION_MAP_10Q.get(section)
        if mapped and hasattr(obj, mapped):
            return str(getattr(obj, mapped))

    # Try common patterns
    common_attrs = {
        "business": ["business", "business_description", "item1"],
        "risk_factors": ["risk_factors", "risks", "item1a"],
        "mda": ["mda", "management_discussion", "item7"],
        "financials": ["financial_statements", "financials", "item8"],
    }

    for attr in common_attrs.get(section, []):
        if hasattr(obj, attr):
            value = getattr(obj, attr)
            if value is not None:
                return str(value)

    return None
