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

# Section mapping for different form types.
# For 10-K: maps MCP section names to the friendly-name keys accepted by TenK.__getitem__
# (which supports 'business', 'risk_factors', 'mda', 'Item 1', 'Item 7', etc.)
SECTION_MAP_10K = {
    "business": "business",
    "risk_factors": "risk_factors",
    "mda": "mda",
    "financials": "financials",
    "controls": "controls_procedures_9a",
    "legal": "legal_proceedings",
}

# For 10-Q: maps MCP section names to the Part/Item keys accepted by TenQ.__getitem__
# ('Part I, Item 2', 'Part II, Item 1A', etc. are the canonical formats TenQ supports)
SECTION_MAP_10Q = {
    "financials": "Part I, Item 1",
    "mda": "Part I, Item 2",
    "risk_factors": "Part II, Item 1A",
    "legal": "Part II, Item 1",
    "controls": "Part I, Item 4",
    "market_risk": "Part I, Item 3",
}

# For 20-F: maps MCP section names to keys accepted by TwentyF.__getitem__
SECTION_MAP_20F = {
    "business": "Item 4",           # Information on the Company
    "risk_factors": "Item 3",       # Key Information (includes risk factors)
    "mda": "Item 5",                # Operating and Financial Review (MD&A equivalent)
    "financials": "financials",     # XBRL data via CompanyReport.financials
    "directors": "Item 6",          # Directors, Senior Management and Employees
    "shareholders": "Item 7",       # Major Shareholders and Related Party Transactions
    "financial_info": "Item 8",     # Financial Information section
    "controls": "Item 15",          # Controls and Procedures
}

# For 6-K: Current reports for foreign private issuers (unstructured)
SECTION_MAP_6K = {
    "financials": "financials",     # Financial statements via XBRL if available
    "full_text": "full_text",       # Full document text
}


@tool(
    name="edgar_filing",
    description="""Read SEC filing content. Get full filing metadata or specific sections.

For 10-K/10-Q: extracts business description, risk factors, MD&A, financials.
For 20-F: extracts business, risk factors, operating review (MD&A), financials for foreign private issuers.
For 6-K/8-K: extracts event items and financials.
For proxy (DEF 14A): extracts compensation, governance info.

Examples:
- Get filing: accession_number="0000320193-23-000077"
- Latest 10-K sections: identifier="AAPL", form="10-K", sections=["business", "risk_factors"]
- Foreign issuer 20-F: identifier="BNTX", form="20-F", sections=["business", "mda"]
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
                "enum": ["summary", "business", "risk_factors", "mda", "financials", "directors", "shareholders", "financial_info", "all"]
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
        elif filing.form in ["20-F", "20-F/A"]:
            result["available_sections"] = list(SECTION_MAP_20F.keys())
        elif filing.form in ["6-K", "6-K/A"]:
            result["available_sections"] = list(SECTION_MAP_6K.keys())
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
            return find(search_id=accession_number)
        except Exception as e:
            logger.debug(f"Direct accession lookup failed for '{accession_number}': {e}")

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
        except Exception as e:
            logger.debug(f"Could not get raw text fallback: {e}")

    return extracted


def _get_section_list(form_type: str) -> list[str]:
    """Get list of extractable sections for a form type."""
    if form_type in ["10-K", "10-K/A"]:
        return list(SECTION_MAP_10K.keys())
    elif form_type in ["10-Q", "10-Q/A"]:
        return list(SECTION_MAP_10Q.keys())
    elif form_type in ["20-F", "20-F/A"]:
        return list(SECTION_MAP_20F.keys())
    elif form_type in ["6-K", "6-K/A"]:
        return list(SECTION_MAP_6K.keys())
    else:
        return ["full_text"]


def _extract_section(obj, form_type: str, section: str) -> Optional[str]:
    """Extract a specific section from a filing object.

    Uses __getitem__ (item/key access) rather than attribute access because
    TenQ and TenK expose content via __getitem__ with Part/Item keys or friendly
    names, not as object attributes.  Attribute access on these objects raises
    AttributeError for narrative sections and therefore always returns None.

    Special case: 'financials' returns the structured XBRL representation via
    the obj.financials cached property, which is a Financials object.
    """
    # Special handling for financials: use the Financials object's structured repr
    if section == "financials":
        try:
            fin = obj.financials
            if fin is not None:
                # Return a human-readable summary of the financial statements
                parts = []
                try:
                    income = fin.income_statement()
                    if income is not None:
                        parts.append(f"=== Income Statement ===\n{income}")
                except Exception:
                    pass
                try:
                    balance = fin.balance_sheet()
                    if balance is not None:
                        parts.append(f"=== Balance Sheet ===\n{balance}")
                except Exception:
                    pass
                try:
                    cashflow = fin.cashflow_statement()
                    if cashflow is not None:
                        parts.append(f"=== Cash Flow Statement ===\n{cashflow}")
                except Exception:
                    pass
                if parts:
                    return "\n\n".join(parts)
                # Fall back to str() representation if no structured data
                return str(fin)
        except Exception:
            pass
        return None

    # For narrative sections, look up the canonical key for this form type
    if form_type in ["10-K", "10-K/A"]:
        section_key = SECTION_MAP_10K.get(section)
    elif form_type in ["10-Q", "10-Q/A"]:
        section_key = SECTION_MAP_10Q.get(section)
    elif form_type in ["20-F", "20-F/A"]:
        section_key = SECTION_MAP_20F.get(section)
    elif form_type in ["6-K", "6-K/A"]:
        section_key = SECTION_MAP_6K.get(section)
    else:
        section_key = None

    if section_key:
        try:
            content = obj[section_key]
            if content:
                return str(content)
        except (KeyError, TypeError, AttributeError):
            pass

    # Last-resort fallback: try the section name directly as a __getitem__ key
    # This handles edge cases and future form types
    try:
        content = obj[section]
        if content:
            return str(content)
    except (KeyError, TypeError, AttributeError):
        pass

    return None
