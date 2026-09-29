"""
edgar_fund `action="bdc_portfolio"`: holdings from one chosen filing's
Schedule of Investments, paged and borrower-filtered, with the raw SOI text
fallback when the XBRL has no per-investment structured data.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, Optional

from edgar.ai.mcp.tools.base import ToolResponse, _cell_missing, _cell_number, error, success
from edgar.ai.mcp.tools.bdc.identity import BdcResolution, bdc_identity_fields, resolve_bdc_and_filing
from edgar.ai.mcp.tools.bdc.paging import (
    PORTFOLIO_CURSOR_TOOL,
    SOI_TEXT_CURSOR_TOOL,
    PeekedCursor,
    build_next_cursor,
    decode_page_cursor,
    no_xbrl_response,
    peek_bdc_cursor,
    resolve_cursor_offset,
    selection_args,
)


def _parse_include_untyped(value: Any):
    """Strictly parse `include_untyped`. Returns `(bool_or_None, error_or_None)`.

    `None` means "not given" (so a cursor can supply it). A bool passes
    through; the strings "true"/"false" (any case) are accepted from loose
    clients; anything else is INVALID_ARGUMENTS rather than `bool()`, which
    turned the string "false" into True (P1-L10).
    """
    if value is None or isinstance(value, bool):
        return value, None
    if isinstance(value, str) and value.strip().lower() in ("true", "false"):
        return value.strip().lower() == "true", None
    return None, error(
        f"include_untyped must be true or false, got {value!r}.",
        suggestions=["Pass include_untyped=true or include_untyped=false"],
        error_code="INVALID_ARGUMENTS",
    )


def _portfolio_query(borrower: Optional[str], include_untyped: Optional[bool], peeked: Optional[PeekedCursor]) -> dict:
    """The cursor query for this call. An omitted borrower/include_untyped
    defaults to the cursor's value (rule 7b); a supplied one is kept as
    given, so a different value fails the cursor's query check with
    CURSOR_MISMATCH."""
    cursor_query = peeked.query if peeked is not None and isinstance(peeked.query, dict) else {}
    normalized = borrower.strip().lower() if borrower and borrower.strip() else None
    if normalized is None:
        normalized = cursor_query.get("borrower")
    if include_untyped is None:
        include_untyped = bool(cursor_query.get("include_untyped", False))
    return {"borrower": normalized, "include_untyped": include_untyped}


def _investment_record(inv) -> dict[str, Any]:
    """Serialize one PortfolioInvestment. Every key is always present;
    missing numeric fields are `_cell_number`-coerced to `None`, never `0`.
    """
    return {
        "identifier": inv.identifier or None,
        "company_name": inv.company_name or None,
        "investment_type": inv.investment_type or None,
        "type": inv.investment_type or None,  # legacy duplicate of investment_type, kept
        "fair_value": _cell_number(inv.fair_value),
        "cost": _cell_number(inv.cost),
        "principal_amount": _cell_number(inv.principal_amount),
        "shares": _cell_number(inv.shares, as_int=True),
        "interest_rate": _cell_number(inv.interest_rate),
        "pik_rate": _cell_number(inv.pik_rate),
        "spread": _cell_number(inv.spread),
        "percent_of_net_assets": _cell_number(inv.percent_of_net_assets),
    }


# Cached in place of `None` when a filing has no structured holdings, so the
# "nothing to extract" outcome is remembered too (`results_cache.get` returns
# `None` for a miss, so `None` itself cannot be the cached value).
_NO_STRUCTURED_HOLDINGS = object()


def _load_extraction(filing, include_untyped: bool):
    """Cached extraction, threading the parsed XBRL through on a cache miss.

    `filing.xbrl()` is not memoized -- it re-parses the filing's full
    submission on every call -- so this parses it at most once per call and
    hands the same object back so the no-structured-data fallback (if
    needed) never parses the same filing a second time. A `None` outcome
    (no structured holdings) is cached as well, so repeat calls on such a
    filing do not re-parse it just to learn that again (P1-H1).

    Returns `(investments_or_None, xbrl_or_None)`. `xbrl` is `None` on a
    cache hit: nothing needed parsing this call.
    """
    from edgar import __version__ as edgar_version
    from edgar.ai.mcp.tools.continuation import results_cache
    from edgar.bdc.investments import portfolio_investments_from_filing

    cache_key = ("bdc_portfolio", filing.accession_number, bool(include_untyped), edgar_version)
    cached = results_cache.get(cache_key)
    if cached is _NO_STRUCTURED_HOLDINGS:
        return None, None
    if cached is not None:
        return cached, None

    xbrl = filing.xbrl()
    investments = portfolio_investments_from_filing(filing, include_untyped=include_untyped, xbrl=xbrl)
    results_cache.put(cache_key, investments if investments is not None else _NO_STRUCTURED_HOLDINGS)
    return investments, xbrl


def _filter_and_paginate(full_list: list, normalized_borrower: Optional[str], offset: int, limit: int):
    """Apply the borrower filter (if any), then slice a page. Returns `(matching, page_items, page_meta)`."""
    from edgar.ai.mcp.tools.continuation import paginate

    if normalized_borrower:
        matching = [
            inv for inv in full_list
            if normalized_borrower in (inv.company_name or "").lower()
            or normalized_borrower in (inv.identifier or "").lower()
        ]
    else:
        matching = full_list

    page_items, page_meta = paginate(matching, offset=offset, limit=limit)
    return matching, page_items, page_meta


def _build_extraction_block(investments, include_untyped: bool) -> dict[str, Any]:
    dq = investments.data_quality
    return {
        "method": investments.extraction_method,
        "include_untyped": bool(include_untyped),
        "period": investments.period,
        "field_coverage": {
            "fair_value": round(dq.fair_value_coverage, 3),
            "cost": round(dq.cost_coverage, 3),
            "principal": round(dq.principal_coverage, 3),
            "interest_rate": round(dq.interest_rate_coverage, 3),
            "pik_rate": round(dq.pik_rate_coverage, 3),
            "spread": round(dq.spread_coverage, 3),
        },
        "rate_convention": "decimal_fraction",
        "limitation": (
            "Holdings are those the parser extracted from XBRL; holdings present "
            "in the filing may be missing. A null field means not extracted or "
            "not disclosed, never zero."
        ),
    }


def _sum_known(values) -> Optional[float]:
    """Sum of the non-missing `values`, or `None` when none is known.

    Rule 7b ("unknown is null"): a total over values that are all missing is
    unknown, not zero (P1-M4).
    """
    known = [v for v in values if not _cell_missing(v)]
    return float(sum(known, Decimal(0))) if known else None


def _filtered_totals(matching: list) -> dict[str, Any]:
    return {
        "count": len(matching),
        "fair_value": _sum_known(inv.fair_value for inv in matching),
        "cost": _sum_known(inv.cost for inv in matching),
    }


def _build_bdc_portfolio_response(
    *,
    resolution: BdcResolution,
    filing,
    investments,
    full_list: list,
    page_items: list,
    page_meta: dict,
    matching: list,
    next_cursor: Optional[str],
    normalized_borrower: Optional[str],
    include_untyped: bool,
) -> dict[str, Any]:
    from edgar.ai.mcp.tools.base import format_source

    result: dict[str, Any] = {
        "analysis": "bdc_portfolio",
        **bdc_identity_fields(resolution, filing),
        "source": format_source(filing, resolution.selection.selected_by),
        "total_investments": len(full_list),
        "total_fair_value": _sum_known(inv.fair_value for inv in full_list),
        "total_cost": _sum_known(inv.cost for inv in full_list),
        "investments": [_investment_record(inv) for inv in page_items],
        "page": {
            "offset": page_meta["offset"],
            "returned": page_meta["returned"],
            "total_matching": len(matching),
            "total_extracted": len(full_list),
            "remaining": page_meta["remaining"],
            "next_cursor": next_cursor,
        },
        "extraction": _build_extraction_block(investments, include_untyped),
    }

    if normalized_borrower:
        result["filtered_totals"] = _filtered_totals(matching)

    if page_meta["remaining"] > 0:
        result["note"] = (
            f"{page_meta['remaining']} more matching investment(s) remain. "
            "Pass the returned cursor to action='bdc_portfolio' to continue."
        )

    return result


def _bdc_portfolio_next_steps(next_cursor: Optional[str]) -> list[str]:
    steps = [
        "Use action='bdc_search' to find other BDCs",
        "Use edgar_company with this CIK for full company analysis",
    ]
    steps.append(
        "Pass the returned cursor to continue paging through investments"
        if next_cursor else
        "Use edgar_read to read the BDC's filing sections"
    )
    return steps


def _bdc_portfolio_with_holdings(
    *,
    resolution: BdcResolution,
    filing,
    investments,
    cursor_payload: Optional[dict],
    query: dict,
    limit: int,
) -> Any:
    """Build the paged response once the filing has structured holdings."""
    from edgar.ai.mcp.tools.continuation import fingerprint

    full_list = list(investments)
    fp = fingerprint(json.dumps(_investment_record(inv), sort_keys=True) for inv in full_list)

    offset, err = resolve_cursor_offset(cursor_payload, fp)
    if err is not None:
        return err

    matching, page_items, page_meta = _filter_and_paginate(full_list, query["borrower"], offset, limit)

    next_cursor = None
    if page_meta["remaining"] > 0:
        next_cursor, err = build_next_cursor(
            PORTFOLIO_CURSOR_TOOL, filing.accession_number, offset + page_meta["returned"], fp, query
        )
        if err is not None:
            return err

    result = _build_bdc_portfolio_response(
        resolution=resolution,
        filing=filing,
        investments=investments,
        full_list=full_list,
        page_items=page_items,
        page_meta=page_meta,
        matching=matching,
        next_cursor=next_cursor,
        normalized_borrower=query["borrower"],
        include_untyped=query["include_untyped"],
    )
    return success(result, next_steps=_bdc_portfolio_next_steps(next_cursor))


async def bdc_portfolio(
    identifier: Optional[str],
    accession_number: Optional[str],
    form: str,
    period: Optional[str],
    borrower: Optional[str],
    cursor: Optional[str],
    limit: int,
    include_untyped: Any,
) -> Any:
    """Get BDC portfolio investments from a chosen filing's Schedule of Investments.

    Resolves exactly one filing via the shared selection resolver — by
    accession number, period, or the BDC's latest 10-K/10-Q, or, when
    continuing, by the cursor's own accession — then extracts holdings via
    `portfolio_investments_from_filing` (cached: extraction costs roughly
    11s for a large BDC like ARCC) and pages/filters the result. Falls back
    to the raw Schedule of Investments text when the filing's XBRL has no
    per-investment structured data, and errors with NO_XBRL when the filing
    has no XBRL at all. A text-fallback cursor goes straight back to the
    text fallback (P1-H1).
    """
    include_untyped, err = _parse_include_untyped(include_untyped)
    if err is not None:
        return err
    peeked, err = peek_bdc_cursor(
        cursor, allowed_tools=(PORTFOLIO_CURSOR_TOOL, SOI_TEXT_CURSOR_TOOL), accession_number=accession_number
    )
    if err is not None:
        return err

    accession_number, period = selection_args(peeked, accession_number, period)
    resolution = resolve_bdc_and_filing(identifier, accession_number, form, period)
    if isinstance(resolution, ToolResponse):
        return resolution
    filing = resolution.selection.filing

    if peeked is not None and peeked.tool == SOI_TEXT_CURSOR_TOOL:
        return _bdc_portfolio_no_structured_data(filing=filing, resolution=resolution, cursor=cursor)

    query = _portfolio_query(borrower, include_untyped, peeked)
    cursor_payload, err = decode_page_cursor(
        cursor, tool=PORTFOLIO_CURSOR_TOOL, accession=filing.accession_number, query=query
    )
    if err is not None:
        return err

    investments, xbrl = _load_extraction(filing, query["include_untyped"])
    if investments is None or len(investments) == 0:
        return _bdc_portfolio_no_structured_data(filing=filing, resolution=resolution, cursor=cursor, xbrl=xbrl)

    return _bdc_portfolio_with_holdings(
        resolution=resolution,
        filing=filing,
        investments=investments,
        cursor_payload=cursor_payload,
        query=query,
        limit=limit,
    )


NO_SOI_STATEMENT_REASON = (
    "This filing's XBRL has no Schedule of Investments statement and no "
    "dimensional investment facts were found."
)
NO_STRUCTURED_FIELDS_REASON = (
    "Structured per-investment fields could not be extracted from this "
    "filing's XBRL; showing the raw Schedule of Investments text instead."
)


def _soi_text_and_reason(filing, xbrl=None):
    """The filing's raw Schedule of Investments text plus why structured
    extraction didn't work. Returns `((text, reason), None)` or
    `(None, NO_XBRL error)`.

    Checks `text_cache` BEFORE touching the XBRL, so a later SOI page never
    re-parses the filing (P1-H1). `xbrl`, if given, is the caller's
    already-parsed XBRL; otherwise it is parsed here only on a cache miss.
    An empty outcome (no SOI statement at all) is cached like any other.
    """
    from edgar.ai.mcp.tools.continuation import text_cache

    cache_key = ("bdc_soi_text", filing.accession_number)
    cached = text_cache.get(cache_key)
    if cached is not None:
        return cached, None

    if xbrl is None:
        xbrl = filing.xbrl()
    if xbrl is None:
        return None, no_xbrl_response(filing.accession_number)

    soi = xbrl.statements.schedule_of_investments()
    text = str(soi) if soi is not None else ""
    reason = NO_SOI_STATEMENT_REASON if soi is None else NO_STRUCTURED_FIELDS_REASON
    text_cache.put(cache_key, (text, reason), size_bytes=len(text.encode("utf-8")))
    return (text, reason), None


def _paginate_soi_text(text: str, cursor: Optional[str], accession: str):
    """Page the SOI fallback text. Returns `(page_text, text_page, error_response)`.

    `text_page` carries only the response's own keys (`offset`,
    `returned_chars`, `total_chars`, `remaining_chars`, `next_cursor`); the
    paginator's internal `next_offset` stays inside the cursor (P1-L6).
    """
    from edgar.ai.mcp.tools.continuation import fingerprint, paginate_text

    fp = fingerprint([text])
    cursor_payload, err = decode_page_cursor(cursor, tool=SOI_TEXT_CURSOR_TOOL, accession=accession, query=None)
    if err is not None:
        return None, None, err
    offset, err = resolve_cursor_offset(cursor_payload, fp)
    if err is not None:
        return None, None, err

    page_text, meta = paginate_text(text, offset=offset)

    next_cursor = None
    if meta["next_offset"] is not None:
        next_cursor, err = build_next_cursor(SOI_TEXT_CURSOR_TOOL, accession, meta["next_offset"], fp, None)
        if err is not None:
            return None, None, err

    text_page = {
        "offset": meta["offset"],
        "returned_chars": meta["returned_chars"],
        "total_chars": meta["total_chars"],
        "remaining_chars": meta["remaining_chars"],
        "next_cursor": next_cursor,
    }
    return page_text, text_page, None


def _bdc_portfolio_no_structured_data(
    *,
    filing,
    resolution: BdcResolution,
    cursor: Optional[str],
    xbrl=None,
) -> Any:
    """Fallback when the filing's XBRL has no per-investment structured data.

    Returns the raw Schedule of Investments text, paged, or a NO_XBRL error
    when the filing carries no XBRL at all. `xbrl`, if given, is the
    already-parsed XBRL from the caller's own extraction attempt, reused
    here instead of parsing the filing's full submission a second time.
    """
    from edgar.ai.mcp.tools.base import format_source

    text_and_reason, err = _soi_text_and_reason(filing, xbrl)
    if err is not None:
        return err
    text, reason = text_and_reason

    page_text, text_page, err = _paginate_soi_text(text, cursor, filing.accession_number)
    if err is not None:
        return err

    result: dict[str, Any] = {
        "analysis": "bdc_portfolio",
        **bdc_identity_fields(resolution, filing),
        "source": format_source(filing, resolution.selection.selected_by),
        # Holdings exist in the text but none were extracted: the count is
        # unknown, not zero (P1-M4).
        "total_investments": None,
        "total_fair_value": None,
        "total_cost": None,
        "investments": [],
        "schedule_of_investments": page_text,
        "structured_data_unavailable": {"reason": reason},
        "text_page": text_page,
    }

    if text_page["remaining_chars"] > 0:
        result["note"] = (
            f"{text_page['remaining_chars']} more character(s) of the Schedule of "
            "Investments text remain. Pass the returned cursor to continue."
        )

    next_steps = [
        "Use edgar_notes to look up disclosures for this filing",
        "Use edgar_read to read the full filing text",
    ]

    return success(result, next_steps=next_steps)
