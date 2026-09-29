"""
Section Reader Tool (edgar_read)

Read text content from specific sections of SEC filings. Extracts narrative
content like risk factors, MD&A, business descriptions, items, and financial
tables from 10-K, 10-Q, 8-K, proxy statements, 13D/G, 13F, and other forms.

Filing selection goes through the shared resolver
(``edgar.ai.mcp.tools.selection.resolve_report_filing``): ``accession_number``
takes precedence, then ``period`` (must exactly match an original filing's
``period_of_report``), then the latest original filing for ``identifier`` +
``form``. That last path now excludes amendments (``form`` + ``identifier``
alone used to return whatever ``get_filings()`` had first, amendment or not).
Every response carries a ``source`` provenance block.

Each extracted section is capped at one ``TEXT_PAGE_CHARS`` page; the full
section text is cached (``text_cache``, keyed by accession + section) so a
``cursor`` from a section's ``next_cursor`` can page through the rest without
re-extracting. A cursor call must name exactly the one section it continues.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from edgar.ai.mcp.tools.base import (
    ToolResponse,
    error,
    format_filing_summary,
    format_source,
    get_error_suggestions,
    success,
    tool,
    truncate_text,
)
from edgar.ai.mcp.tools.continuation import (
    CursorError,
    check_fingerprint,
    fingerprint,
    paginate_text,
    try_decode_cursor,
    try_encode_cursor,
)

logger = logging.getLogger(__name__)

_SECTION_TOOL = "edgar_read:section"

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
    name="edgar_read",
    description="""Use this to read the text content of specific sections from a filing. Extracts narrative content like risk factors, MD&A, business descriptions, financial tables, and event items.

Use edgar_filing first to identify a filing, then edgar_read to extract its content.

Available sections by form type:
- 10-K/10-Q: business, risk_factors, mda, financials, controls, legal
- 20-F: business, risk_factors, mda, financials, directors, shareholders, controls
- 8-K: items, press_release, earnings
- DEF 14A: compensation, pay_performance, governance
- SC 13D/13G: ownership, purpose
- 13F-HR: holdings, summary

Examples:
- Read risk factors: identifier="AAPL", form="10-K", sections=["risk_factors"]
- Read 8-K event: identifier="AAPL", form="8-K", sections=["items"]
- Read CEO pay: identifier="AAPL", form="DEF 14A", sections=["compensation"]
- Read from a chosen period: identifier="ARCC", form="10-Q", period="2026-06-30", sections=["mda"]
- Continue a truncated section: sections=["mda"], cursor="<next_cursor from a previous call>\"""",
    params={
        "accession_number": {
            "type": "string",
            "description": "Filing accession number (e.g., 0000320193-23-000077). Takes precedence over period."
        },
        "identifier": {
            "type": "string",
            "description": "Company identifier (alternative - gets most recent filing of form type)"
        },
        "form": {
            "type": "string",
            "description": "Form type (used with identifier to get most recent, or with period to select "
                           "the exact filing). Required whenever identifier is given."
        },
        "period": {
            "type": "string",
            "description": "Reporting period (YYYY-MM-DD) that must exactly match the chosen filing's "
                           "period_of_report. Requires identifier and form."
        },
        "sections": {
            "type": "array",
            "items": {
                "type": "string",
            },
            "description": "Sections to extract. Use 'summary' for metadata only, 'all' for everything. "
                           "Available sections depend on form type. With a cursor, must contain exactly "
                           "the one section being continued.",
            "default": ["summary"]
        },
        "cursor": {
            "type": "string",
            "description": "Continuation cursor from a previous response's section_pages.<section>.next_cursor, "
                           "to fetch the next page of that one section."
        }
    },
    required=[]
)
async def edgar_read(
    accession_number: Optional[str] = None,
    identifier: Optional[str] = None,
    form: Optional[str] = None,
    sections: Optional[list[str]] = None,
    period: Optional[str] = None,
    cursor: Optional[str] = None,
) -> Any:
    """
    Read SEC filing content.

    Can retrieve by accession number, or by identifier + form (latest
    original filing, or an exact period).
    """
    sections = sections or ["summary"]

    try:
        if cursor and (len(sections) != 1 or sections[0] in ("summary", "all")):
            return error(
                "With a cursor, sections must contain exactly one specific section name.",
                suggestions=["Pass sections=['mda'] (or the single section this cursor continues)"],
                error_code="INVALID_ARGUMENTS",
            )

        selected = _select_filing(accession_number, identifier, form, period)
        if isinstance(selected, ToolResponse):
            return selected
        filing = selected.filing
        selected_by = selected.selected_by

        result: dict[str, Any] = {
            "filing": format_filing_summary(filing),
            "form_type": filing.form,
            "source": format_source(filing, selected_by),
            "available_sections": _get_section_list(filing.form),
        }

        if cursor:
            page_result = _continue_section(filing, sections[0], cursor)
            if isinstance(page_result, ToolResponse):
                return page_result
            result["sections"], result["section_pages"] = page_result
            return success(result, next_steps=["Omit the cursor to read other sections"])

        # Extract requested sections
        if "summary" not in sections or len(sections) > 1:
            extracted, pages = await _extract_sections(filing, sections)
            result["sections"] = extracted
            if pages:
                result["section_pages"] = pages

        # Next steps
        next_steps = []
        if "summary" in sections and len(sections) == 1:
            next_steps.append("Add sections like 'business', 'risk_factors', 'mda' to read content")
        next_steps.append("Use edgar_company for full company analysis")

        return success(result, next_steps=next_steps)

    except Exception as e:
        logger.exception("Error in edgar_read")
        return error(str(e), suggestions=get_error_suggestions(e))


def _select_filing(
    accession_number: Optional[str],
    identifier: Optional[str],
    form: Optional[str],
    period: Optional[str],
):
    """Resolve exactly one filing. Returns a `FilingSelection`, or a `ToolResponse`
    the caller should return as-is.

    `accession_number` wins over everything (per `resolve_report_filing`'s
    precedence); it needs neither `identifier` nor `form`. Without it, both
    `identifier` and `form` are required — the latest-original and
    exact-period paths both need a form to select within, and `form` was
    already required alongside `identifier` before this task; `period` does
    not relax that.
    """
    if not accession_number and not identifier:
        return error(
            "Could not find filing",
            suggestions=[
                "Provide accession_number for a specific filing",
                "Or provide identifier + form for most recent",
            ],
            error_code="INVALID_ARGUMENTS",
        )
    if not accession_number and not form:
        return error(
            "form is required when identifier is used",
            suggestions=["Provide form (e.g. '10-K' or '10-Q') together with identifier"],
            error_code="INVALID_ARGUMENTS",
        )

    # Imported locally (not at module import time) so tests can monkeypatch
    # edgar.ai.mcp.tools.selection.resolve_report_filing and have it take
    # effect here -- same convention fund.py uses for filing selection.
    from edgar.ai.mcp.tools.selection import FilingSelectionError, resolve_report_filing

    try:
        return resolve_report_filing(
            identifier=identifier, form=form or "10-K", accession_number=accession_number, period=period
        )
    except FilingSelectionError as exc:
        return exc.to_response()


def _get_section_text_cached(obj, filing, section: str) -> Optional[str]:
    """Full (untruncated) section text, cached by (accession, section).

    `_extract_section` is the potentially expensive step (it can parse the
    filing's structured object's fields); a page past the first would
    otherwise re-run it just to re-slice text it already computed.

    Imports `text_cache` locally (not at module import time) so tests can
    monkeypatch `continuation.text_cache` and have it take effect here --
    same convention `fund.py` uses for its own caches.
    """
    from edgar.ai.mcp.tools.continuation import text_cache

    cache_key = ("edgar_read", filing.accession_number, section)
    cached = text_cache.get(cache_key)
    if cached is not None:
        return cached

    content = _extract_section(obj, filing.form, section)
    text = str(content) if content else None
    if text is not None:
        text_cache.put(cache_key, text, size_bytes=len(text.encode("utf-8")))
    return text


def _build_page_block(meta: dict, fp: str, accession: str, section: str):
    """`{offset, total_chars, remaining_chars, next_cursor}`, or a `ToolResponse` error.

    Built from documented keys only -- `paginate_text`'s own metadata dict
    also carries an internal `next_offset`, which does not belong in a
    response.
    """
    next_cursor = None
    if meta["next_offset"] is not None:
        next_cursor, err = try_encode_cursor(
            tool=_SECTION_TOOL, accession=accession, offset=meta["next_offset"], fp=fp, document=section
        )
        if err is not None:
            return err
    return {
        "offset": meta["offset"],
        "total_chars": meta["total_chars"],
        "remaining_chars": meta["remaining_chars"],
        "next_cursor": next_cursor,
    }


async def _extract_sections(filing, sections: list[str]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Extract requested sections from filing. Returns `(extracted, section_pages)`."""
    extracted: dict[str, Any] = {}
    pages: dict[str, Any] = {}
    accession = filing.accession_number

    try:
        # Get the typed object (TenK, TenQ, EightK, etc.)
        obj = filing.obj()

        if obj is None:
            extracted["error"] = f"Could not parse {filing.form} filing into a structured object"
            return extracted, pages

        if "all" in sections:
            # Extract all available sections
            sections_to_extract = _get_section_list(filing.form)
        else:
            sections_to_extract = [s for s in sections if s != "summary"]

        for section in sections_to_extract:
            text = _get_section_text_cached(obj, filing, section)
            if text is None:
                extracted[section] = None
                continue

            fp = fingerprint([text])
            page_text, meta = paginate_text(text, offset=0)
            page_block = _build_page_block(meta, fp, accession, section)
            if isinstance(page_block, ToolResponse):
                # Cursor construction failed (e.g. an oversized query) --
                # still return the page text, just without a way to continue.
                logger.warning("Could not build section cursor for %s: %s", section, page_block)
                extracted[section] = page_text
                continue

            extracted[section] = page_text
            pages[section] = page_block

    except Exception as e:
        logger.warning(f"Could not extract sections: {e}")
        extracted["error"] = str(e)

        # Try to get raw text as fallback
        try:
            if hasattr(filing, 'text'):
                extracted["raw_text_preview"] = truncate_text(filing.text(), max_chars=4000)
                extracted["fallback_used"] = True
                extracted["fallback_reason"] = str(e)
        except Exception as inner:
            logger.debug(f"Could not get raw text fallback: {inner}")

    return extracted, pages


def _continue_section(filing, section: str, cursor: str):
    """Continue one section's cursor. Returns `(extracted, section_pages)` for just
    that section, or a `ToolResponse` error."""
    accession = filing.accession_number

    try:
        obj = filing.obj()
    except Exception as e:
        return error(f"Could not parse {filing.form} filing: {e}", error_code="INTERNAL_ERROR")

    text = _get_section_text_cached(obj, filing, section)
    if text is None:
        return error(
            f"Section '{section}' has no extractable content for this filing.",
            suggestions=["Call edgar_read without a cursor first to fetch this section"],
            error_code="INVALID_ARGUMENTS",
        )

    fp = fingerprint([text])
    payload, err = try_decode_cursor(cursor, tool=_SECTION_TOOL, accession=accession, document=section)
    if err is not None:
        return err
    try:
        check_fingerprint(payload, fp)
    except CursorError as exc:
        return exc.to_response()

    offset = payload["off"]
    page_text, meta = paginate_text(text, offset=offset)
    page_block = _build_page_block(meta, fp, accession, section)
    if isinstance(page_block, ToolResponse):
        return page_block

    return {section: page_text}, {section: page_block}


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
                                 ("Cash Flow Statement", "cash_flow_statement")]:
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
                parts.append("Earnings data available")
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
