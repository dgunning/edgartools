"""
edgar_fund `action="bdc_nonaccrual"`: non-accrual evidence from one chosen
filing, with an `evidence_level` and null (never 0) counts when the filing
does not identify individual investments (P1-M4).
"""

from __future__ import annotations

import json
from typing import Any, Optional

from edgar.ai.mcp.tools.base import ToolResponse, _cell_number, success
from edgar.ai.mcp.tools.bdc.identity import BdcResolution, bdc_identity_fields, resolve_bdc_and_filing
from edgar.ai.mcp.tools.bdc.paging import (
    NONACCRUAL_CURSOR_TOOL,
    build_next_cursor,
    decode_page_cursor,
    no_xbrl_response,
    peek_bdc_cursor,
    resolve_cursor_offset,
    selection_args,
)

_NONACCRUAL_INTERPRETATION_LIMITS = (
    "Non-accrual is an accounting status (interest income no longer recognized), "
    "not a legal default determination. Absence from this list does not establish "
    "that a loan is performing. Aggregate evidence is not attributed to individual "
    "borrowers."
)


def _nonaccrual_evidence_level(result) -> str:
    """Map a NonAccrualResult to the response's `evidence_level`.

    Mapping (per Task 5 brief):
    - "investment": per-investment detail was resolved. `has_investment_detail`
      is the authoritative check (equivalent to `extraction_method == 'footnote'`,
      the only layer that resolves individual investments).
    - "aggregate": no investment detail, but a custom or standard XBRL concept
      gave a portfolio-level rate/value (`extraction_method` is
      'custom_concept' or 'aggregate_concept').
    - "none": no non-accrual signal was extracted at all
      (`extraction_method == 'none'`).
    """
    if result.has_investment_detail:
        return "investment"
    if result.extraction_method in ("custom_concept", "aggregate_concept"):
        return "aggregate"
    return "none"


def _nonaccrual_investment_record(inv) -> dict[str, Any]:
    """Serialize one NonAccrualInvestment. Missing numeric fields stay `None`, never `0`."""
    return {
        "identifier": inv.identifier or None,
        "company_name": inv.company_name or None,
        "investment_type": inv.investment_type or None,
        "fair_value": _cell_number(inv.fair_value),
        "cost": _cell_number(inv.cost),
        "footnote_text": inv.footnote_text or None,
    }


def _load_nonaccrual_result(filing):
    """Cached `extract_nonaccrual(filing)`.

    Cache key per the Task 5 brief: `("bdc_nonaccrual", accession, edgar.__version__)`
    -- deliberately not shared with `_load_extraction`'s `bdc_portfolio` cache,
    since this wraps a different extraction function with no `include_untyped`
    parameter. A `None` result (no XBRL at all) is never cached -- the caller
    turns that into a NO_XBRL error every time, which costs nothing to redo.
    """
    from edgar import __version__ as edgar_version
    from edgar.ai.mcp.tools.continuation import results_cache
    from edgar.bdc.nonaccrual import extract_nonaccrual

    cache_key = ("bdc_nonaccrual", filing.accession_number, edgar_version)
    result = results_cache.get(cache_key)
    if result is not None:
        return result

    result = extract_nonaccrual(filing)
    if result is not None:
        results_cache.put(cache_key, result)
    return result


def _nonaccrual_page_block(page_meta: dict, next_cursor: Optional[str], has_detail: bool) -> dict[str, Any]:
    """The `page` block. Without investment-level evidence the number of
    non-accrual investments is unknown, so its totals are `null`, not 0 (P1-M4)."""
    total = page_meta["total"] if has_detail else None
    return {
        "offset": page_meta["offset"],
        "returned": page_meta["returned"],
        "total_matching": total,
        "total_extracted": total,
        "remaining": page_meta["remaining"],
        "next_cursor": next_cursor,
    }


def _build_bdc_nonaccrual_response(
    *,
    resolution: BdcResolution,
    filing,
    result,
    page_items: list,
    page_meta: dict,
    next_cursor: Optional[str],
) -> dict[str, Any]:
    from edgar.ai.mcp.tools.base import format_source

    evidence_level = _nonaccrual_evidence_level(result)
    has_detail = evidence_level == "investment"

    response: dict[str, Any] = {
        "analysis": "bdc_nonaccrual",
        **bdc_identity_fields(resolution, filing),
        "source": format_source(filing, resolution.selection.selected_by),
        "period": result.period,
        "evidence_level": evidence_level,
        "extraction_method": result.extraction_method,
        # Unknown, not zero, unless individual investments were resolved (P1-M4).
        "num_nonaccrual": result.num_nonaccrual if has_detail else None,
        "nonaccrual_fair_value": _cell_number(result.nonaccrual_fair_value),
        "total_portfolio_fair_value": _cell_number(result.total_portfolio_fair_value),
        "nonaccrual_rate": result.nonaccrual_rate,
        "rate_convention": "decimal_fraction",
        "custom_concept_rate": result.custom_concept_rate,
        "aggregate_concept_value": _cell_number(result.aggregate_concept_value),
        "warnings": list(result.warnings),
        "unique_footnote_texts": list(result.unique_footnote_texts),
        "investments": [_nonaccrual_investment_record(inv) for inv in page_items],
        "page": _nonaccrual_page_block(page_meta, next_cursor, has_detail),
        "interpretation_limits": _NONACCRUAL_INTERPRETATION_LIMITS,
    }

    if evidence_level == "aggregate":
        response["note"] = (
            "This filing discloses only a portfolio-level non-accrual value; "
            "individual investments are not identified."
        )
    elif page_meta["remaining"] > 0:
        response["note"] = (
            f"{page_meta['remaining']} more non-accrual investment(s) remain. "
            "Pass the returned cursor to action='bdc_nonaccrual' to continue."
        )

    return response


def _bdc_nonaccrual_next_steps(next_cursor: Optional[str]) -> list[str]:
    steps = [
        "Use action='bdc_portfolio' to see the full Schedule of Investments",
        "Use edgar_notes to read the non-accrual footnote disclosure in context",
    ]
    steps.append(
        "Pass the returned cursor to continue paging through non-accrual investments"
        if next_cursor else
        "Use edgar_company with this CIK for full company analysis"
    )
    return steps


def _bdc_nonaccrual_page(resolution: BdcResolution, result, cursor_payload: Optional[dict], limit: int) -> Any:
    """Page the extracted non-accrual investments and build the response."""
    from edgar.ai.mcp.tools.continuation import fingerprint, paginate

    filing = resolution.selection.filing
    full_list = list(result.investments)
    fp = fingerprint(json.dumps(_nonaccrual_investment_record(inv), sort_keys=True) for inv in full_list)

    offset, err = resolve_cursor_offset(cursor_payload, fp)
    if err is not None:
        return err

    page_items, page_meta = paginate(full_list, offset=offset, limit=limit)

    next_cursor = None
    if page_meta["remaining"] > 0:
        next_cursor, err = build_next_cursor(
            NONACCRUAL_CURSOR_TOOL, filing.accession_number, offset + page_meta["returned"], fp, None
        )
        if err is not None:
            return err

    response = _build_bdc_nonaccrual_response(
        resolution=resolution,
        filing=filing,
        result=result,
        page_items=page_items,
        page_meta=page_meta,
        next_cursor=next_cursor,
    )
    return success(response, next_steps=_bdc_nonaccrual_next_steps(next_cursor))


async def bdc_nonaccrual(
    identifier: Optional[str],
    accession_number: Optional[str],
    form: str,
    period: Optional[str],
    cursor: Optional[str],
    limit: int,
) -> Any:
    """Get BDC non-accrual evidence from a chosen filing.

    Resolves exactly one filing via the shared selection resolver (same as
    `bdc_portfolio`, including cursor-only continuation by the cursor's own
    accession), then extracts non-accrual investments/values via
    `extract_nonaccrual` (cached; see `_load_nonaccrual_result`) and pages the
    per-investment detail when it exists. Errors NO_XBRL when the filing has
    no XBRL at all -- the only case `extract_nonaccrual` returns `None`.
    """
    peeked, err = peek_bdc_cursor(
        cursor, allowed_tools=(NONACCRUAL_CURSOR_TOOL,), accession_number=accession_number
    )
    if err is not None:
        return err

    accession_number, period = selection_args(peeked, accession_number, period)
    resolution = resolve_bdc_and_filing(identifier, accession_number, form, period)
    if isinstance(resolution, ToolResponse):
        return resolution
    accession = resolution.selection.filing.accession_number

    cursor_payload, err = decode_page_cursor(
        cursor, tool=NONACCRUAL_CURSOR_TOOL, accession=accession, query=None
    )
    if err is not None:
        return err

    result = _load_nonaccrual_result(resolution.selection.filing)
    if result is None:
        return no_xbrl_response(accession)

    return _bdc_nonaccrual_page(resolution, result, cursor_payload, limit)
