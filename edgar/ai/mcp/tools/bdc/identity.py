"""
BDC identity for edgar_fund: which BDC, and which filing.

- `bdc_search`: the `action="bdc_search"` name/ticker listing.
- `resolve_bdc`: identifier (ticker, CIK or name) -> BDC, with the name-search
  auto-select rule (P1-M2) and NOT_A_BDC for real non-BDC companies (P1-L10).
- `is_active` for a match from a stale report year (P1-M5) and the shared
  identity block (`bdc_identity_fields`).
- `resolve_bdc_and_filing`: the BDC plus the one chosen filing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Optional

from edgar.ai.mcp.tools.base import error, get_error_suggestions, resolve_company, success

logger = logging.getLogger(__name__)


async def bdc_search(query: str, limit: int) -> Any:
    """Search for BDCs by name or ticker."""
    try:
        from edgar.bdc.search import find_bdc

        results = find_bdc(query, top_n=limit)

        if results.empty:
            return error(
                f"No BDCs found matching '{query}'",
                suggestions=[
                    "Try a broader search term",
                    "BDC tickers include ARCC, MAIN, PSEC, FSK",
                    "Use action='search' for regular investment funds",
                ]
            )

        records = []
        for _, row in results.results.iterrows():
            record = {
                "cik": int(row['cik']),
                "name": row['name'],
                "ticker": row['ticker'] if row['ticker'] else None,
                "state": row['state'] if row['state'] else None,
                "is_active": bool(row['is_active']),
                "score": int(row['score']),
            }
            records.append(record)

        result = {
            "analysis": "bdc_search",
            "query": query,
            "total_results": len(records),
            "results": records,
        }

        next_steps = [
            "Use action='bdc_portfolio' with a ticker or CIK to see investments",
            "Use edgar_company with a CIK to get full company analysis",
        ]

        return success(result, next_steps=next_steps)

    except Exception as e:
        return error(str(e), suggestions=get_error_suggestions(e))


# =============================================================================
# BDC resolution: identifier -> BDC (ticker, CIK, or name search)
# =============================================================================

# Report years searched/looked up behind the latest SEC BDC Report; the same
# value as `lookup_bdc`'s default, so a name search and a CIK lookup agree on
# which BDCs exist (P1-M2c: ARCC is absent from the 2026 report).
_BDC_LOOKBACK_YEARS = 2

# A fuzzy name hit is auto-selected only when it is at least this good and
# the runner-up is below `_SEARCH_RUNNER_UP_MAX`; anything less clear-cut is
# AMBIGUOUS_BDC (P1-M2b). A single weak hit is never silently used.
_SEARCH_AUTO_SELECT_SCORE = 95
_SEARCH_RUNNER_UP_MAX = 90
_SEARCH_TOP_N = 10
_MAX_AMBIGUOUS_CANDIDATES = 5


@dataclass(frozen=True)
class BdcLookup:
    """Result of resolving an identifier to a BDC.

    At most one of `bdc`/`ambiguous`/`not_a_bdc_cik` is set. All three
    `None` means "not found". `not_a_bdc_cik` means the identifier is a real
    company, just not a BDC in any checked report year. `resolved_by` is set
    to `"search"` when a fuzzy name search (rather than a direct ticker/CIK
    hit) produced `bdc`.
    """
    bdc: Optional[Any] = None
    ambiguous: Optional[list[dict]] = None
    resolved_by: Optional[str] = None
    not_a_bdc_cik: Optional[int] = None


def resolve_bdc(identifier: str) -> BdcLookup:
    """Resolve a ticker, CIK, or name to a BDC.

    A purely numeric string resolves as a CIK. A short alphanumeric string
    (1-5 characters) is tried as a ticker first and, on a miss, as a name
    (so "Golub" or "Ares" still reach the search; P1-M2a). Anything else is
    a name. Ticker/CIK lookups go through `lookup_bdc`, which checks the
    latest SEC BDC Report and falls back to prior years -- the 2026 report
    is missing at least one active, large BDC (see `lookup_bdc`'s
    docstring), so "not in the latest report" is never treated as "not a
    BDC" here. The name search must identify exactly one BDC or comes back
    ambiguous rather than silently guessed (`resolve_bdc_by_search`).
    """
    cleaned = identifier.strip()

    if cleaned.isdigit():
        return _find_bdc_by_cik(int(cleaned))

    if cleaned.isalnum() and 1 <= len(cleaned) <= 5:
        return _find_bdc_by_ticker(cleaned)

    return resolve_bdc_by_search(cleaned)


def _try_resolve_company(identifier: str):
    """`resolve_company(identifier)`, or `None` when it is not a real company.

    `Company(<int>)` does not raise for an unknown CIK -- it returns a
    placeholder entity ("Entity 99999999") whose `not_found` is True -- so
    that flag is checked too; otherwise an unknown CIK would read as "a real
    company that is not a BDC".
    """
    try:
        company = resolve_company(identifier)
    except Exception as exc:
        logger.debug("Could not resolve '%s' to a company: %s", identifier, exc)
        return None
    return None if getattr(company, "not_found", False) else company


def _find_bdc_by_cik(cik: int) -> BdcLookup:
    """CIK path: a real company that isn't a BDC is `not_a_bdc_cik` (P1-L10),
    matching the accession path's NOT_A_BDC."""
    from edgar.bdc.reference import lookup_bdc

    bdc = lookup_bdc(cik=cik)
    if bdc is not None:
        return BdcLookup(bdc=bdc)
    company = _try_resolve_company(str(cik))
    return BdcLookup(not_a_bdc_cik=int(company.cik)) if company is not None else BdcLookup()


def _find_bdc_by_ticker(ticker: str) -> BdcLookup:
    """Ticker path: report ticker column, then the company's CIK, then name search.

    A ticker absent from every report's ticker column still resolves via the
    company's CIK. If that company isn't a BDC either, the string may be a
    short name ("Ares" resolves to Ares Management), so it goes to the name
    search; only when the search finds nothing is it `not_a_bdc_cik`.
    """
    from edgar.bdc.reference import lookup_bdc

    bdc = lookup_bdc(ticker=ticker.upper())
    if bdc is not None:
        return BdcLookup(bdc=bdc)

    company = _try_resolve_company(ticker)
    if company is not None:
        bdc = lookup_bdc(cik=int(company.cik))
        if bdc is not None:
            return BdcLookup(bdc=bdc)

    lookup = resolve_bdc_by_search(ticker)
    if lookup.bdc is None and lookup.ambiguous is None and company is not None:
        return BdcLookup(not_a_bdc_cik=int(company.cik))
    return lookup


def resolve_bdc_by_search(identifier: str) -> BdcLookup:
    """Fuzzy BDC name search across the `lookup_bdc` report years.

    Resolves only on a clear winner (`_pick_search_winner`); otherwise every
    hit (up to 5) comes back as an AMBIGUOUS_BDC candidate, including a
    single hit too weak to trust.
    """
    from edgar.bdc.reference import lookup_bdc
    from edgar.bdc.search import find_bdc

    results = find_bdc(identifier, top_n=_SEARCH_TOP_N, lookback_years=_BDC_LOOKBACK_YEARS)
    if results.empty:
        return BdcLookup()

    rows = results.results.to_dict("records")
    winner = _pick_search_winner(identifier, rows)
    if winner is not None:
        return BdcLookup(bdc=lookup_bdc(cik=winner), resolved_by="search")
    return BdcLookup(ambiguous=[_search_candidate(row) for row in rows[:_MAX_AMBIGUOUS_CANDIDATES]])


def _normalize_bdc_name(name: str) -> str:
    return " ".join(str(name).split()).casefold()


def _pick_search_winner(query: str, rows: list[dict]) -> Optional[int]:
    """The CIK to auto-select from score-ordered search `rows`, or `None`.

    Exactly one case-insensitive exact name match wins outright ("Ares
    Capital Corp" vs its sibling Ares funds, which all score ~99). Otherwise
    the top hit wins only when it scores >= 95 and the next best is < 90.
    """
    wanted = _normalize_bdc_name(query)
    exact = [row for row in rows if _normalize_bdc_name(row["name"]) == wanted]
    if len(exact) == 1:
        return int(exact[0]["cik"])

    top_score = float(rows[0]["score"])
    runner_up = float(rows[1]["score"]) if len(rows) > 1 else None
    if top_score >= _SEARCH_AUTO_SELECT_SCORE and (runner_up is None or runner_up < _SEARCH_RUNNER_UP_MAX):
        return int(rows[0]["cik"])
    return None


def _search_candidate(row: dict) -> dict:
    return {
        "name": str(row["name"]),
        "cik": int(row["cik"]),
        "ticker": row["ticker"] if row["ticker"] else None,
    }


def _ambiguous_bdc_response(identifier: str, candidates: list[dict]) -> Any:
    def _describe(c: dict) -> str:
        ticker_part = f", ticker {c['ticker']}" if c.get("ticker") else ""
        return f"{c['name']} (CIK {c['cik']}{ticker_part})"

    return error(
        f"'{identifier}' matches multiple BDCs; pick one by ticker, CIK, or accession_number.",
        suggestions=[_describe(c) for c in candidates],
        error_code="AMBIGUOUS_BDC",
    )


def _bdc_not_found_response(identifier: str) -> Any:
    return error(
        f"Could not find BDC: '{identifier}'",
        suggestions=[
            "Use action='bdc_search' to find BDCs by name",
            "Try a ticker (ARCC, MAIN) or CIK number",
        ],
        error_code="COMPANY_NOT_FOUND",
    )


def _not_a_bdc_response(cik: Any) -> Any:
    return error(
        f"CIK {cik} is not a Business Development Company.",
        suggestions=[
            "Use action='bdc_search' to find BDCs by name or ticker",
            "Provide a BDC identifier instead of accession_number alone",
        ],
        error_code="NOT_A_BDC",
    )


def _lookup_failure_response(identifier: str, lookup: BdcLookup) -> Optional[Any]:
    """The error response for an unresolved `lookup`, or `None` if it resolved."""
    if lookup.ambiguous is not None:
        return _ambiguous_bdc_response(identifier, lookup.ambiguous)
    if lookup.not_a_bdc_cik is not None:
        return _not_a_bdc_response(lookup.not_a_bdc_cik)
    if lookup.bdc is None:
        return _bdc_not_found_response(identifier)
    return None


# =============================================================================
# BDC activity (P1-M5): is_active from the company when the report row is stale
# =============================================================================

def _as_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _latest_filing_date(company) -> Optional[date]:
    """The company's most recent filing date from its already-loaded
    submissions page (any form), or `None` if unavailable."""
    try:
        filings = company.get_filings(trigger_full_load=False)
        latest = filings.latest() if filings is not None and len(filings) > 0 else None
        return _as_date(latest.filing_date) if latest is not None else None
    except Exception as exc:
        logger.warning(
            "Could not read the latest filing date for CIK %s: %s", getattr(company, "cik", None), exc
        )
        return None


def _bdc_is_active(bdc, company=None) -> Optional[bool]:
    """`is_active` for the response.

    A match from the latest SEC BDC Report (or one with no known report
    year) keeps the report row's own `is_active`. A match found only in an
    older report year has a stale `last_filing_date` -- ARCC's 2025 row goes
    "inactive" from 2026-11-29 although ARCC files every quarter -- so the
    same 18-month rule is applied to the company's own latest filing
    instead, and the answer is `None` when that is unavailable. `company` is
    the already-loaded Company when the caller has one; otherwise it is
    loaded here only for a stale match.
    """
    from edgar.bdc.reference import filed_within_active_window, get_latest_bdc_report_year

    report_year = getattr(bdc, "report_year", None)
    if report_year is None or report_year == get_latest_bdc_report_year():
        return bdc.is_active

    if company is None:
        try:
            company = bdc.get_company()
        except Exception as exc:
            logger.warning("Could not load company for BDC CIK %s: %s", bdc.cik, exc)
            return None
    latest = _latest_filing_date(company)
    return None if latest is None else filed_within_active_window(latest)


def bdc_identity_fields(resolution: "BdcResolution", filing) -> dict[str, Any]:
    """Shared `name`/`cik`/`is_active`/`bdc_report_year`/`state`/`resolved_by` block.

    Used by the structured-holdings, no-structured-data and non-accrual
    responses so their identity blocks stay in sync. `bdc_report_year` is the
    SEC BDC Report year the BDC was matched in (P1-M5 provenance); `null`
    when unknown.
    """
    bdc = resolution.bdc
    fields: dict[str, Any] = {
        "name": bdc.name if bdc is not None else filing.company,
        "cik": bdc.cik if bdc is not None else int(filing.cik),
        "is_active": resolution.is_active if bdc is not None else None,
        "bdc_report_year": getattr(bdc, "report_year", None) if bdc is not None else None,
    }
    if bdc is not None and bdc.state:
        fields["state"] = bdc.state
    if resolution.resolved_by:
        fields["resolved_by"] = resolution.resolved_by
    return fields


# =============================================================================
# BDC filing selection
# =============================================================================

@dataclass(frozen=True)
class BdcResolution:
    """A resolved BDC (if any) plus the chosen filing and its activity flag."""
    bdc: Any
    selection: Any
    resolved_by: Optional[str] = None
    is_active: Optional[bool] = None


def resolve_bdc_and_filing(
    identifier: Optional[str],
    accession_number: Optional[str],
    form: str,
    period: Optional[str],
):
    """Resolve the BDC (if `identifier` given) and the chosen filing.

    Returns a `BdcResolution` on success, or a `ToolResponse` the caller
    should return as-is: `COMPANY_NOT_FOUND`/`AMBIGUOUS_BDC`/`NOT_A_BDC` for
    an unresolved identifier, `NOT_A_BDC` when an accession's CIK isn't a
    BDC in any checked report year, or a filing-selection failure's own
    response (including `SELECTION_MISMATCH` when `identifier` and
    `accession_number` name different companies).
    """
    from edgar.ai.mcp.tools.selection import FilingSelectionError

    try:
        if identifier:
            return _resolve_by_identifier(identifier, accession_number, form, period)
        return _resolve_by_accession_only(accession_number)
    except FilingSelectionError as exc:
        return exc.to_response()


def _resolve_by_identifier(identifier: str, accession_number: Optional[str], form: str, period: Optional[str]):
    from edgar.ai.mcp.tools.selection import resolve_report_filing

    lookup = resolve_bdc(identifier)
    failure = _lookup_failure_response(identifier, lookup)
    if failure is not None:
        return failure
    company = lookup.bdc.get_company()
    selection = resolve_report_filing(
        form=form,
        accession_number=accession_number,
        period=period,
        company=company,
    )
    return BdcResolution(
        bdc=lookup.bdc,
        selection=selection,
        resolved_by=lookup.resolved_by,
        is_active=_bdc_is_active(lookup.bdc, company),
    )


def _resolve_by_accession_only(accession_number: Optional[str]):
    from edgar.ai.mcp.tools.selection import resolve_report_filing
    from edgar.bdc.reference import lookup_bdc

    selection = resolve_report_filing(accession_number=accession_number)
    bdc = lookup_bdc(cik=int(selection.filing.cik))
    if bdc is None:
        return _not_a_bdc_response(selection.filing.cik)
    return BdcResolution(bdc=bdc, selection=selection, is_active=_bdc_is_active(bdc))
