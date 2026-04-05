"""
Filing Reader Tool

Read SEC filing content - full filing or specific sections.
Handles 10-K, 10-Q, 8-K, proxy statements, 13D/G, 13F, and other form types.
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
SECTION_MAP_10K = {
    "business": "business",
    "risk_factors": "risk_factors",
    "mda": "mda",
    "financials": "financials",
    "controls": "controls_procedures_9a",
    "legal": "legal_proceedings",
}

# For 10-Q: maps MCP section names to the Part/Item keys accepted by TenQ.__getitem__
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

# Form types that have dedicated extractors (keyed by base form, without /A suffix)
FORM_EXTRACTORS = {"10-K", "10-Q", "8-K", "DEF 14A", "SC 13D", "SC 13G", "SC 13D/A", "SC 13G/A", "13F-HR"}


@tool(
    name="edgar_filing",
    description="""Read SEC filing content. Get full filing metadata or specific sections.

For 10-K/10-Q: business, risk_factors, mda, financials, controls, legal
For 20-F: business, risk_factors, mda, financials, directors, shareholders, financial_info, controls (foreign private issuers)
For 6-K: financials, full_text (foreign private issuer current reports)
For 8-K: items (event list + content), press_release, earnings
For DEF 14A (proxy): compensation, pay_performance, governance
For SC 13D/13G: ownership (shares, percent), purpose
For 13F-HR: holdings, summary

Examples:
- Latest 10-K: identifier="AAPL", form="10-K", sections=["business", "risk_factors"]
- Foreign issuer 20-F: identifier="BNTX", form="20-F", sections=["business", "mda"]
- 8-K events: identifier="AAPL", form="8-K", sections=["items"]
- CEO pay: identifier="AAPL", form="DEF 14A", sections=["compensation"]
- Activist stake: identifier="AAPL", form="SC 13D", sections=["ownership"]""",
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
            },
            "description": "Sections to extract. Use 'summary' for metadata only, 'all' for everything. "
                           "Available sections depend on form type.",
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
        result["available_sections"] = _get_section_list(filing.form)

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
    base = form_type.replace("/A", "").strip()
    if base == "10-K":
        return list(SECTION_MAP_10K.keys())
    elif base == "10-Q":
        return list(SECTION_MAP_10Q.keys())
    elif base == "20-F":
        return list(SECTION_MAP_20F.keys())
    elif base == "6-K":
        return list(SECTION_MAP_6K.keys())
    elif base == "8-K":
        return ["items", "press_release", "earnings"]
    elif base == "DEF 14A":
        return ["compensation", "pay_performance", "governance"]
    elif base in ("SC 13D", "SC 13G"):
        return ["ownership", "purpose"]
    elif base == "13F-HR":
        return ["holdings", "summary"]
    else:
        return ["full_text"]


def _extract_section(obj, form_type: str, section: str) -> Optional[str]:
    """Extract a specific section from a filing object.

    Routes to form-specific extractors for structured forms, with
    fallback to __getitem__ for 10-K/10-Q narrative sections.
    """
    base = form_type.replace("/A", "").strip()

    # Special handling for financials (10-K/10-Q)
    if section == "financials":
        return _extract_financials(obj)

    # Route to form-specific extractors
    if base == "8-K":
        return _extract_8k_section(obj, section)
    elif base == "DEF 14A":
        return _extract_proxy_section(obj, section)
    elif base in ("SC 13D", "SC 13G"):
        return _extract_schedule13_section(obj, section)
    elif base == "13F-HR":
        return _extract_13f_section(obj, section)

    # For 10-K/10-Q narrative sections, look up the canonical key
    if base == "10-K":
        section_key = SECTION_MAP_10K.get(section)
    elif base == "10-Q":
        section_key = SECTION_MAP_10Q.get(section)
    elif base == "20-F":
        section_key = SECTION_MAP_20F.get(section)
    elif base == "6-K":
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
    try:
        content = obj[section]
        if content:
            return str(content)
    except (KeyError, TypeError, AttributeError):
        pass

    return None


def _extract_financials(obj) -> Optional[str]:
    """Extract XBRL financial statements from a filing object."""
    try:
        fin = obj.financials
        if fin is not None:
            parts = []
            for name, method in [("Income Statement", "income_statement"),
                                 ("Balance Sheet", "balance_sheet"),
                                 ("Cash Flow Statement", "cashflow_statement")]:
                try:
                    stmt = getattr(fin, method)()
                    if stmt is not None:
                        parts.append(f"=== {name} ===\n{stmt}")
                except Exception:
                    pass
            if parts:
                return "\n\n".join(parts)
            return str(fin)
    except Exception:
        pass
    return None


def _extract_8k_section(obj, section: str) -> Optional[str]:
    """Extract sections from an 8-K (CurrentReport) object."""
    if section == "items":
        try:
            items = obj.items
            if not items:
                return "No items detected in this 8-K."
            parts = [f"Items: {', '.join(items)}"]
            for item_name in items:
                try:
                    content = obj[item_name]
                    if content:
                        parts.append(f"\n--- {item_name} ---\n{content}")
                except (KeyError, TypeError):
                    pass
            return "\n".join(parts)
        except Exception as e:
            logger.debug(f"Could not extract 8-K items: {e}")
            return None

    elif section == "press_release":
        try:
            if hasattr(obj, 'press_releases') and obj.press_releases:
                return str(obj.press_releases)
            if hasattr(obj, 'has_press_release') and not obj.has_press_release:
                return "No press release attached to this 8-K."
        except Exception as e:
            logger.debug(f"Could not extract press release: {e}")
        return None

    elif section == "earnings":
        try:
            if hasattr(obj, 'has_earnings') and not obj.has_earnings:
                return "This 8-K does not contain earnings data."
            parts = []
            if hasattr(obj, 'earnings') and obj.earnings:
                parts.append(f"Earnings data available")
            for name, method in [("Income Statement", "income_statement"),
                                 ("Balance Sheet", "balance_sheet"),
                                 ("Cash Flow", "cash_flow_statement")]:
                try:
                    stmt = getattr(obj, method)()
                    if stmt is not None:
                        parts.append(f"\n=== {name} ===\n{stmt}")
                except Exception:
                    pass
            return "\n".join(parts) if parts else None
        except Exception as e:
            logger.debug(f"Could not extract earnings: {e}")
        return None

    return None


def _extract_proxy_section(obj, section: str) -> Optional[str]:
    """Extract sections from a DEF 14A (ProxyStatement) object."""
    if section == "compensation":
        try:
            parts = []
            if hasattr(obj, 'peo_name') and obj.peo_name:
                parts.append(f"CEO/PEO: {obj.peo_name}")
            if hasattr(obj, 'peo_total_comp') and obj.peo_total_comp is not None:
                parts.append(f"PEO Total Compensation: ${obj.peo_total_comp:,.0f}")
            if hasattr(obj, 'neo_avg_total_comp') and obj.neo_avg_total_comp is not None:
                parts.append(f"NEO Average Total Compensation: ${obj.neo_avg_total_comp:,.0f}")
            if hasattr(obj, 'executive_compensation'):
                comp = obj.executive_compensation
                if comp is not None and not comp.empty:
                    parts.append(f"\n=== Executive Compensation Table ===\n{comp.to_string()}")
            return "\n".join(parts) if parts else None
        except Exception as e:
            logger.debug(f"Could not extract compensation: {e}")
        return None

    elif section == "pay_performance":
        try:
            parts = []
            if hasattr(obj, 'total_shareholder_return') and obj.total_shareholder_return is not None:
                parts.append(f"Total Shareholder Return: {obj.total_shareholder_return}")
            if hasattr(obj, 'company_selected_measure') and obj.company_selected_measure:
                parts.append(f"Company-Selected Measure: {obj.company_selected_measure}")
                if hasattr(obj, 'company_selected_measure_value') and obj.company_selected_measure_value is not None:
                    parts.append(f"  Value: {obj.company_selected_measure_value}")
            if hasattr(obj, 'pay_vs_performance'):
                pvp = obj.pay_vs_performance
                if pvp is not None and not pvp.empty:
                    parts.append(f"\n=== Pay vs Performance Table ===\n{pvp.to_string()}")
            return "\n".join(parts) if parts else None
        except Exception as e:
            logger.debug(f"Could not extract pay vs performance: {e}")
        return None

    elif section == "governance":
        try:
            parts = []
            if hasattr(obj, 'performance_measures'):
                measures = obj.performance_measures
                if measures:
                    parts.append(f"Performance Measures: {', '.join(measures)}")
            if hasattr(obj, 'insider_trading_policy_adopted'):
                policy = obj.insider_trading_policy_adopted
                if policy is not None:
                    parts.append(f"Insider Trading Policy Adopted: {policy}")
            return "\n".join(parts) if parts else None
        except Exception as e:
            logger.debug(f"Could not extract governance: {e}")
        return None

    return None


def _extract_schedule13_section(obj, section: str) -> Optional[str]:
    """Extract sections from a Schedule 13D/13G object."""
    if section == "ownership":
        try:
            parts = []
            if hasattr(obj, 'is_amendment'):
                parts.append(f"Amendment: {obj.is_amendment}")
            if hasattr(obj, 'total_shares') and obj.total_shares is not None:
                parts.append(f"Total Shares: {obj.total_shares:,}")
            if hasattr(obj, 'total_percent') and obj.total_percent is not None:
                parts.append(f"Ownership Percentage: {obj.total_percent:.1f}%")
            if hasattr(obj, 'is_passive_investor'):
                parts.append(f"Passive Investor: {obj.is_passive_investor}")
            return "\n".join(parts) if parts else None
        except Exception as e:
            logger.debug(f"Could not extract 13D/G ownership: {e}")
        return None

    elif section == "purpose":
        # Try to get the purpose of transaction text
        try:
            # Schedule 13D Item 4 is "Purpose of Transaction"
            if hasattr(obj, 'purpose_of_transaction'):
                return str(obj.purpose_of_transaction)
            # Fallback: try generic string representation
            return str(obj)
        except Exception as e:
            logger.debug(f"Could not extract 13D/G purpose: {e}")
        return None

    return None


def _extract_13f_section(obj, section: str) -> Optional[str]:
    """Extract sections from a 13F-HR (ThirteenF) object."""
    if section == "holdings":
        try:
            if hasattr(obj, 'holdings') and obj.holdings:
                parts = []
                for h in obj.holdings[:30]:  # Limit to top 30
                    name = getattr(h, 'name', None) or getattr(h, 'issuer', 'Unknown')
                    shares = getattr(h, 'shares', None)
                    value = getattr(h, 'value', None)
                    line = f"  {name}"
                    if shares:
                        line += f" | {shares:,} shares"
                    if value:
                        line += f" | ${value:,}"
                    parts.append(line)
                total = len(obj.holdings)
                header = f"Top holdings ({min(30, total)} of {total}):"
                return header + "\n" + "\n".join(parts)
        except Exception as e:
            logger.debug(f"Could not extract 13F holdings: {e}")
        return None

    elif section == "summary":
        try:
            parts = []
            if hasattr(obj, 'management_company_name') and obj.management_company_name:
                parts.append(f"Management Company: {obj.management_company_name}")
            if hasattr(obj, 'report_period') and obj.report_period:
                parts.append(f"Report Period: {obj.report_period}")
            if hasattr(obj, 'total_holdings') and obj.total_holdings is not None:
                parts.append(f"Total Holdings: {obj.total_holdings}")
            if hasattr(obj, 'total_value') and obj.total_value is not None:
                parts.append(f"Total Value: ${obj.total_value:,}")
            return "\n".join(parts) if parts else None
        except Exception as e:
            logger.debug(f"Could not extract 13F summary: {e}")
        return None

    return None
