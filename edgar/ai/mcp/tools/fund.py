"""
Fund Tool

Get fund, ETF, BDC, and money market fund data from SEC filings.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

import pandas as pd

from edgar.ai.mcp.tools.base import (
    tool,
    success,
    error,
    get_error_suggestions,
    classify_error,
    resolve_company,
    _cell_missing,
    _cell_number,
    ToolResponse,
)

logger = logging.getLogger(__name__)


def _df_to_records(df: pd.DataFrame, limit: int, columns: Optional[list[str]] = None) -> list[dict]:
    """DataFrame to list of dicts. Selects columns, caps rows, converts Decimal→float, NaN→None."""
    if df is None or df.empty:
        return []

    if columns:
        # Only select columns that exist
        columns = [c for c in columns if c in df.columns]
        if columns:
            df = df[columns]

    records = []
    for _, row in df.head(limit).iterrows():
        record = {}
        for k, v in row.items():
            if _cell_missing(v):
                record[k] = None
            elif isinstance(v, Decimal):
                record[k] = float(v)
            else:
                record[k] = v
        records.append(record)
    return records


@tool(
    name="edgar_fund",
    description="""Use this for mutual fund, ETF, BDC, and money market fund analysis. Supports fund lookup, portfolio holdings, money market yields, BDC investments, and BDC non-accrual evidence.

Actions: lookup (find fund by ticker/CIK), search (by name), portfolio (NPORT holdings), money_market (yields/NAV), bdc_search, bdc_portfolio, bdc_nonaccrual.

Examples:
- Fund lookup: action="lookup", identifier="VFINX"
- Fund search: action="search", query="Vanguard 500"
- Fund portfolio: action="portfolio", identifier="VFINX"
- Money market: action="money_market", identifier="VMFXX"
- BDC search: action="bdc_search", query="Ares"
- BDC portfolio (latest 10-K): action="bdc_portfolio", identifier="ARCC"
- BDC portfolio (chosen period): action="bdc_portfolio", identifier="ARCC", form="10-Q", period="2026-06-30"
- BDC portfolio (chosen filing by accession): action="bdc_portfolio", accession_number="0001628280-26-050307"
- BDC portfolio (borrower filter): action="bdc_portfolio", identifier="ARCC", form="10-Q", period="2026-06-30", borrower="Ivy Hill"
- BDC portfolio (next page): action="bdc_portfolio", identifier="ARCC", form="10-Q", period="2026-06-30", borrower="Ivy Hill", cursor="<page.next_cursor from the previous call>"
- BDC portfolio (next page, cursor alone): action="bdc_portfolio", cursor="<page.next_cursor from the previous call>"
- BDC non-accrual evidence: action="bdc_nonaccrual", identifier="ARCC", form="10-Q", period="2026-06-30"

<!-- MCP_TOOL_CALL_EXAMPLE -->
```json
{"tool":"edgar_fund","arguments":{"action":"bdc_portfolio","identifier":"ARCC","form":"10-Q","period":"2026-06-30","borrower":"Ivy Hill","limit":20}}
```

<!-- MCP_TOOL_CALL_EXAMPLE -->
```json
{"tool":"edgar_fund","arguments":{"action":"bdc_portfolio","identifier":"ARCC","form":"10-Q","period":"2026-06-30","borrower":"Ivy Hill","limit":20,"cursor":"<page.next_cursor>"}}
```""",
    params={
        "action": {
            "type": "string",
            "enum": ["lookup", "search", "portfolio", "money_market",
                     "bdc_search", "bdc_portfolio", "bdc_nonaccrual"],
            "description": "The action to perform"
        },
        "identifier": {
            "type": "string",
            "description": "Fund ticker, series ID (S000XXXXX), class ID (C000XXXXX), or CIK. "
                            "BDC actions also accept a BDC name; a name that does not identify "
                            "exactly one BDC returns AMBIGUOUS_BDC with candidates."
        },
        "query": {
            "type": "string",
            "description": "Search text for fund or BDC name"
        },
        "limit": {
            "type": "integer",
            "description": "Max results to return (default 20, max 50)",
            "default": 20
        },
        "accession_number": {
            "type": "string",
            "description": "BDC actions only. Exact SEC accession number (NNNNNNNNNN-NN-NNNNNN) pinning "
                            "a specific filing. Takes precedence over period. May be given without "
                            "identifier for action='bdc_portfolio'."
        },
        "form": {
            "type": "string",
            "enum": ["10-K", "10-Q"],
            "description": "BDC actions only. Form type to select the filing from (default '10-K').",
            "default": "10-K"
        },
        "period": {
            "type": "string",
            "description": "BDC actions only. Reporting period (YYYY-MM-DD) that must exactly match the "
                            "chosen filing's period_of_report."
        },
        "borrower": {
            "type": "string",
            "description": "BDC actions only. Case-insensitive substring filter on the portfolio "
                            "company/borrower name or the raw investment identifier."
        },
        "cursor": {
            "type": "string",
            "description": "Continuation cursor from a previous bdc_portfolio or bdc_nonaccrual "
                            "response's page.next_cursor (or the text fallback's "
                            "text_page.next_cursor), to fetch the next page. The cursor alone is "
                            "enough: it selects its own filing, borrower and include_untyped. "
                            "form/period are ignored with a cursor; identifier, accession_number, "
                            "borrower or include_untyped, if repeated, must match it."
        },
        "include_untyped": {
            "type": "boolean",
            "description": "BDC actions only. Include investments with an unrecognized/untyped "
                            "classification (default false). Must be true or false; the strings "
                            "\"true\"/\"false\" are accepted, anything else is INVALID_ARGUMENTS.",
            "default": False
        },
    },
    required=["action"]
)
async def edgar_fund(
    action: str,
    identifier: Optional[str] = None,
    query: Optional[str] = None,
    limit: int = 20,
    accession_number: Optional[str] = None,
    form: Optional[str] = None,
    period: Optional[str] = None,
    borrower: Optional[str] = None,
    cursor: Optional[str] = None,
    include_untyped: Optional[Any] = None,
) -> Any:
    """Get fund, ETF, BDC, and money market fund data."""
    try:
        # Clamp limit
        limit = max(1, min(50, limit))

        if action == "lookup":
            if not identifier:
                return error(
                    "identifier is required for action='lookup'",
                    suggestions=["Provide a ticker (VFINX), series ID (S000002277), class ID, or CIK"],
                    error_code="INVALID_ARGUMENTS"
                )
            return await _fund_lookup(identifier)

        elif action == "search":
            if not query:
                return error(
                    "query is required for action='search'",
                    suggestions=["Provide a fund name to search for, e.g. query='Vanguard 500'"],
                    error_code="INVALID_ARGUMENTS"
                )
            return await _fund_search(query, limit)

        elif action == "portfolio":
            if not identifier:
                return error(
                    "identifier is required for action='portfolio'",
                    suggestions=["Provide a fund ticker or series ID"],
                    error_code="INVALID_ARGUMENTS"
                )
            return await _fund_portfolio(identifier, limit)

        elif action == "money_market":
            if not identifier:
                return error(
                    "identifier is required for action='money_market'",
                    suggestions=["Provide a money market fund ticker or series ID"],
                    error_code="INVALID_ARGUMENTS"
                )
            return await _money_market(identifier, limit)

        elif action == "bdc_search":
            if not query:
                return error(
                    "query is required for action='bdc_search'",
                    suggestions=["Provide a BDC name or ticker, e.g. query='Ares' or query='ARCC'"],
                    error_code="INVALID_ARGUMENTS"
                )
            return await _bdc_search(query, limit)

        elif action == "bdc_portfolio":
            if not identifier and not accession_number and not cursor:
                return error(
                    "identifier or accession_number is required for action='bdc_portfolio'",
                    suggestions=[
                        "Provide a BDC ticker (ARCC) or CIK as identifier",
                        "Or provide accession_number to pin an exact filing",
                        "Or provide the cursor from a previous page to continue",
                    ],
                    error_code="INVALID_ARGUMENTS"
                )
            return await _bdc_portfolio(
                identifier=identifier,
                accession_number=accession_number,
                form=form or "10-K",
                period=period,
                borrower=borrower,
                cursor=cursor,
                limit=limit,
                include_untyped=include_untyped,
            )

        elif action == "bdc_nonaccrual":
            if not identifier and not accession_number and not cursor:
                return error(
                    "identifier or accession_number is required for action='bdc_nonaccrual'",
                    suggestions=[
                        "Provide a BDC ticker (ARCC) or CIK as identifier",
                        "Or provide accession_number to pin an exact filing",
                        "Or provide the cursor from a previous page to continue",
                    ],
                    error_code="INVALID_ARGUMENTS"
                )
            return await _bdc_nonaccrual(
                identifier=identifier,
                accession_number=accession_number,
                form=form or "10-K",
                period=period,
                cursor=cursor,
                limit=limit,
            )

        else:
            return error(
                f"Unknown action: {action}",
                suggestions=[
                    "Use 'lookup', 'search', 'portfolio', 'money_market', "
                    "'bdc_search', 'bdc_portfolio', or 'bdc_nonaccrual'"
                ]
            )

    except Exception as e:
        logger.exception("Error in edgar_fund")
        classified = classify_error(e)
        return error(
            classified["message"],
            suggestions=classified["suggestions"],
            error_code=classified["error_code"]
        )


async def _fund_lookup(identifier: str) -> Any:
    """Look up fund hierarchy by identifier."""
    try:
        from edgar.funds.core import Fund, FundCompany, FundSeries, FundClass

        fund = Fund(identifier)

        result: dict[str, Any] = {
            "analysis": "fund_lookup",
            "name": fund.name,
            "identifier": fund.identifier,
            "original_identifier": identifier,
        }

        # Entity type
        if isinstance(fund._entity, FundClass):
            result["entity_type"] = "share_class"
        elif isinstance(fund._entity, FundSeries):
            result["entity_type"] = "series"
        elif isinstance(fund._entity, FundCompany):
            result["entity_type"] = "company"

        # Ticker
        if fund.ticker:
            result["ticker"] = fund.ticker

        # Company info
        if fund.company:
            result["company"] = {
                "name": fund.company.name,
                "cik": str(fund.company.cik),
            }

        # Series info
        if fund.series:
            result["series"] = {
                "series_id": fund.series.series_id,
                "name": fund.series.name,
            }

        # Share class info
        if fund.share_class:
            result["share_class"] = {
                "class_id": fund.share_class.class_id,
                "name": fund.share_class.name,
                "ticker": fund.share_class.ticker,
            }

        # List all series
        try:
            series_list = fund.list_series()
            if series_list and len(series_list) > 1:
                result["all_series"] = [
                    {"series_id": s.series_id, "name": s.name}
                    for s in series_list[:20]
                ]
        except Exception:
            logger.debug("Could not list series")

        # List all classes
        try:
            classes = fund.list_classes()
            if classes:
                result["all_classes"] = [
                    {"class_id": c.class_id, "name": c.name, "ticker": c.ticker}
                    for c in classes[:20]
                ]
        except Exception:
            logger.debug("Could not list classes")

        next_steps = [
            "Use action='portfolio' with this identifier to see holdings",
            "Use action='money_market' if this is a money market fund",
            "Use action='search' to find related funds",
        ]

        return success(result, next_steps=next_steps)

    except Exception as e:
        return error(str(e), suggestions=[
            "Use action='search' to find the fund by name",
            "Try a different identifier format (ticker, series ID, CIK)",
        ])


async def _fund_search(query: str, limit: int) -> Any:
    """Search for funds by name."""
    try:
        from edgar.funds.core import find_funds

        results = find_funds(query, search_type='series')

        if not results:
            return error(
                f"No funds found matching '{query}'",
                suggestions=[
                    "Try a broader search term",
                    "Use action='bdc_search' for Business Development Companies",
                ]
            )

        records = []
        for r in results[:limit]:
            record = {
                "series_id": r.series_id,
                "name": r.name,
                "cik": r.cik,
            }
            records.append(record)

        result = {
            "analysis": "fund_search",
            "query": query,
            "total_results": len(results),
            "results": records,
        }

        if len(results) > limit:
            result["note"] = f"Showing {limit} of {len(results)} results. Increase limit for more."

        next_steps = [
            "Use action='lookup' with a series_id to see full fund details",
            "Use action='portfolio' with a series_id to see holdings",
        ]

        return success(result, next_steps=next_steps)

    except Exception as e:
        return error(str(e), suggestions=get_error_suggestions(e))


async def _fund_portfolio(identifier: str, limit: int) -> Any:
    """Get fund portfolio holdings."""
    try:
        from edgar.funds.core import Fund

        fund = Fund(identifier)
        portfolio = fund.get_portfolio()

        if portfolio is None or portfolio.empty:
            return error(
                f"No portfolio data available for '{identifier}'",
                suggestions=[
                    "This fund may not file NPORT-P reports",
                    "Use action='money_market' for money market funds (N-MFP3)",
                    "Use action='lookup' to verify the fund identifier",
                ]
            )

        total_holdings = len(portfolio)

        # Try to compute total value. 'value_usd' is the real dollar column on
        # FundReport.investment_data(); the others were dead candidates that
        # never matched, so this silently fell through to 'balance' (a share/
        # unit count, not a dollar amount) whenever it was present.
        total_value = None
        value_col = None
        for col in ['value_usd', 'value', 'market_value', 'val', 'balance']:
            if col in portfolio.columns:
                value_col = col
                break
        if value_col:
            try:
                total_value = float(portfolio[value_col].sum())
            except Exception:
                pass

        records = _df_to_records(portfolio, limit)

        result: dict[str, Any] = {
            "analysis": "fund_portfolio",
            "fund": fund.name,
            "identifier": fund.identifier,
            "total_holdings": total_holdings,
            "holdings": records,
        }

        if total_value is not None:
            result["total_value"] = total_value

        if total_holdings > limit:
            result["note"] = f"Showing {limit} of {total_holdings} holdings. Increase limit for more."

        next_steps = [
            "Use action='lookup' for fund hierarchy details",
            "Use edgar_company to analyze specific portfolio companies",
        ]

        return success(result, next_steps=next_steps)

    except Exception as e:
        return error(str(e), suggestions=get_error_suggestions(e))


async def _money_market(identifier: str, limit: int) -> Any:
    """Get money market fund data from N-MFP3/N-MFP2 filings."""
    try:
        from edgar.funds.core import Fund

        fund = Fund(identifier)

        # Try N-MFP3 first, then N-MFP2
        mmf = fund.get_latest_report(form='N-MFP3')
        form_type = 'N-MFP3'
        if mmf is None:
            mmf = fund.get_latest_report(form='N-MFP2')
            form_type = 'N-MFP2'

        if mmf is None:
            return error(
                f"No money market fund report found for '{identifier}'",
                suggestions=[
                    "This may not be a money market fund",
                    "Use action='portfolio' for regular fund holdings (NPORT-P)",
                    "Use action='lookup' to verify the fund identifier",
                ]
            )

        result: dict[str, Any] = {
            "analysis": "money_market_fund",
            "fund": mmf.name,
            "form": form_type,
            "report_date": mmf.report_date,
        }

        # Core metrics
        if mmf.net_assets is not None:
            result["net_assets"] = float(mmf.net_assets)
        if mmf.fund_category:
            result["fund_category"] = mmf.fund_category
        if mmf.average_maturity_wam is not None:
            result["wam_days"] = mmf.average_maturity_wam
        if mmf.average_maturity_wal is not None:
            result["wal_days"] = mmf.average_maturity_wal
        result["num_securities"] = mmf.num_securities
        result["num_share_classes"] = mmf.num_share_classes

        # Share class data
        try:
            sc_df = mmf.share_class_data()
            if sc_df is not None and not sc_df.empty:
                result["share_classes"] = _df_to_records(sc_df, limit)
        except Exception:
            logger.debug("Could not extract share class data")

        # Holdings by category
        try:
            cat_df = mmf.holdings_by_category()
            if cat_df is not None and not cat_df.empty:
                result["holdings_by_category"] = _df_to_records(cat_df, limit)
        except Exception:
            logger.debug("Could not extract holdings by category")

        # Top portfolio holdings
        try:
            port_df = mmf.portfolio_data()
            if port_df is not None and not port_df.empty:
                cols = [c for c in ['issuer', 'title', 'category', 'market_value', 'maturity_date', 'yield_pct']
                        if c in port_df.columns]
                result["top_holdings"] = _df_to_records(port_df, limit, columns=cols)
                result["total_portfolio_securities"] = len(port_df)
        except Exception:
            logger.debug("Could not extract portfolio data")

        # Yield history (last 5 entries)
        try:
            yield_df = mmf.yield_history()
            if yield_df is not None and not yield_df.empty:
                result["yield_history"] = _df_to_records(yield_df, 5)
        except Exception:
            logger.debug("Could not extract yield history")

        next_steps = [
            "Use action='lookup' for fund hierarchy and share class details",
            "Use action='search' to find other money market funds",
        ]

        return success(result, next_steps=next_steps)

    except Exception as e:
        return error(str(e), suggestions=get_error_suggestions(e))


async def _bdc_search(query: str, limit: int) -> Any:
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
class _BdcLookup:
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


def _find_bdc(identifier: str) -> _BdcLookup:
    """Resolve a ticker, CIK, or name to a BDC.

    A purely numeric string resolves as a CIK. A short alphanumeric string
    (1-5 characters) is tried as a ticker first and, on a miss, as a name
    (so "Golub" or "Ares" still reach the search; P1-M2a). Anything else is
    a name. Ticker/CIK lookups go through `lookup_bdc`, which checks the
    latest SEC BDC Report and falls back to prior years -- the 2026 report
    is missing at least one active, large BDC (see `lookup_bdc`'s
    docstring), so "not in the latest report" is never treated as "not a
    BDC" here. The name search must identify exactly one BDC or comes back
    ambiguous rather than silently guessed (`_find_bdc_by_search`).
    """
    cleaned = identifier.strip()

    if cleaned.isdigit():
        return _find_bdc_by_cik(int(cleaned))

    if cleaned.isalnum() and 1 <= len(cleaned) <= 5:
        return _find_bdc_by_ticker(cleaned)

    return _find_bdc_by_search(cleaned)


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


def _find_bdc_by_cik(cik: int) -> _BdcLookup:
    """CIK path: a real company that isn't a BDC is `not_a_bdc_cik` (P1-L10),
    matching the accession path's NOT_A_BDC."""
    from edgar.bdc.reference import lookup_bdc

    bdc = lookup_bdc(cik=cik)
    if bdc is not None:
        return _BdcLookup(bdc=bdc)
    company = _try_resolve_company(str(cik))
    return _BdcLookup(not_a_bdc_cik=int(company.cik)) if company is not None else _BdcLookup()


def _find_bdc_by_ticker(ticker: str) -> _BdcLookup:
    """Ticker path: report ticker column, then the company's CIK, then name search.

    A ticker absent from every report's ticker column still resolves via the
    company's CIK. If that company isn't a BDC either, the string may be a
    short name ("Ares" resolves to Ares Management), so it goes to the name
    search; only when the search finds nothing is it `not_a_bdc_cik`.
    """
    from edgar.bdc.reference import lookup_bdc

    bdc = lookup_bdc(ticker=ticker.upper())
    if bdc is not None:
        return _BdcLookup(bdc=bdc)

    company = _try_resolve_company(ticker)
    if company is not None:
        bdc = lookup_bdc(cik=int(company.cik))
        if bdc is not None:
            return _BdcLookup(bdc=bdc)

    lookup = _find_bdc_by_search(ticker)
    if lookup.bdc is None and lookup.ambiguous is None and company is not None:
        return _BdcLookup(not_a_bdc_cik=int(company.cik))
    return lookup


def _find_bdc_by_search(identifier: str) -> _BdcLookup:
    """Fuzzy BDC name search across the `lookup_bdc` report years.

    Resolves only on a clear winner (`_pick_search_winner`); otherwise every
    hit (up to 5) comes back as an AMBIGUOUS_BDC candidate, including a
    single hit too weak to trust.
    """
    from edgar.bdc.reference import lookup_bdc
    from edgar.bdc.search import find_bdc

    results = find_bdc(identifier, top_n=_SEARCH_TOP_N, lookback_years=_BDC_LOOKBACK_YEARS)
    if results.empty:
        return _BdcLookup()

    rows = results.results.to_dict("records")
    winner = _pick_search_winner(identifier, rows)
    if winner is not None:
        return _BdcLookup(bdc=lookup_bdc(cik=winner), resolved_by="search")
    return _BdcLookup(ambiguous=[_search_candidate(row) for row in rows[:_MAX_AMBIGUOUS_CANDIDATES]])


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


def _lookup_failure_response(identifier: str, lookup: _BdcLookup) -> Optional[Any]:
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


def _bdc_identity_fields(resolution: "_BdcResolution", filing) -> dict[str, Any]:
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
class _BdcResolution:
    """A resolved BDC (if any) plus the chosen filing and its activity flag."""
    bdc: Any
    selection: Any
    resolved_by: Optional[str] = None
    is_active: Optional[bool] = None


def _resolve_bdc_and_filing(
    identifier: Optional[str],
    accession_number: Optional[str],
    form: str,
    period: Optional[str],
):
    """Resolve the BDC (if `identifier` given) and the chosen filing.

    Returns a `_BdcResolution` on success, or a `ToolResponse` the caller
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

    lookup = _find_bdc(identifier)
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
    return _BdcResolution(
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
    return _BdcResolution(bdc=bdc, selection=selection, is_active=_bdc_is_active(bdc))


# =============================================================================
# Cursor routing (P1-H1, P1-H2 / constraints rule 7b)
# =============================================================================

_PORTFOLIO_CURSOR_TOOL = "edgar_fund:bdc_portfolio"
_SOI_TEXT_CURSOR_TOOL = "edgar_fund:bdc_soi_text"
_NONACCRUAL_CURSOR_TOOL = "edgar_fund:bdc_nonaccrual"


@dataclass(frozen=True)
class _PeekedCursor:
    """What a cursor says about itself before any filing is loaded."""
    tool: str
    accession: str
    query: Optional[dict]


def _canonical_accession(value: str) -> str:
    """`value` stripped, with an 18-digit form rewritten to NNNNNNNNNN-NN-NNNNNN."""
    cleaned = value.strip()
    if len(cleaned) == 18 and cleaned.isdigit():
        return f"{cleaned[:10]}-{cleaned[10:12]}-{cleaned[12:]}"
    return cleaned


def _cursor_error_response(message: str, error_code: str) -> Any:
    from edgar.ai.mcp.tools.continuation import CursorError

    return CursorError(message, error_code=error_code).to_response()


def _peek_bdc_cursor(cursor: Optional[str], *, allowed_tools: tuple[str, ...], accession_number: Optional[str]):
    """Peek `cursor` to route the call. Returns `(peeked_or_None, error_or_None)`.

    A cursor is self-describing (rule 7b): its accession selects the filing,
    so a bare cursor is enough to continue. Rejected up front, before any
    filing is loaded: an undecodable cursor (`INVALID_CURSOR`), a cursor from
    another tool/action, or an `accession_number` naming a different filing
    (`CURSOR_MISMATCH`). The full identity and fingerprint checks still run
    later against the loaded filing.
    """
    from edgar.ai.mcp.tools.continuation import CursorError, peek_cursor

    if not cursor:
        return None, None
    try:
        payload = peek_cursor(cursor)
    except CursorError as exc:
        return None, exc.to_response()

    accession = payload.get("acc")
    if not isinstance(accession, str) or not accession:
        return None, _cursor_error_response("Cursor does not name a filing.", "INVALID_CURSOR")
    if payload.get("tool") not in allowed_tools:
        return None, _cursor_error_response(
            "Cursor was issued for a different tool or action than this call.", "CURSOR_MISMATCH"
        )
    if accession_number and _canonical_accession(accession_number) != accession:
        return None, _cursor_error_response(
            "Cursor was issued for a different filing than accession_number.", "CURSOR_MISMATCH"
        )
    return _PeekedCursor(tool=payload["tool"], accession=accession, query=payload.get("q")), None


def _selection_args(peeked: Optional[_PeekedCursor], accession_number: Optional[str], period: Optional[str]):
    """`(accession_number, period)` to select with: the cursor's own accession
    when continuing (form/period ignored), else the caller's selectors."""
    if peeked is None:
        return accession_number, period
    return peeked.accession, None


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


def _portfolio_query(borrower: Optional[str], include_untyped: Optional[bool], peeked: Optional[_PeekedCursor]) -> dict:
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


def _decode_page_cursor(cursor: Optional[str], *, tool: str, accession: str, query: dict):
    """Decode a page cursor, if given. Returns `(payload_or_None, error_response_or_None)`.

    Thin wrapper over `continuation.try_decode_cursor` (shared with
    edgar_notes/edgar_read) so this module's call sites don't change.
    """
    from edgar.ai.mcp.tools.continuation import try_decode_cursor

    return try_decode_cursor(cursor, tool=tool, accession=accession, query=query)


def _build_next_cursor(tool: str, accession: str, offset: int, fp: str, query: Optional[dict]):
    """Encode a page cursor. Returns `(cursor_or_None, error_response_or_None)`.

    Thin wrapper over `continuation.try_encode_cursor` (shared with
    edgar_notes/edgar_read) so this module's call sites don't change.
    """
    from edgar.ai.mcp.tools.continuation import try_encode_cursor

    return try_encode_cursor(tool=tool, accession=accession, offset=offset, fp=fp, query=query)


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
    resolution: _BdcResolution,
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
        **_bdc_identity_fields(resolution, filing),
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


def _resolve_cursor_offset(cursor_payload: Optional[dict], fp: str):
    """The page offset a decoded cursor points at. Returns `(offset, error_response)`;
    `offset` is `0` with no cursor. Checks the fingerprint -- the one part of
    cursor validation that needs the just-computed extraction fingerprint,
    so it can't happen inside `_decode_page_cursor` (which runs before
    extraction)."""
    from edgar.ai.mcp.tools.continuation import CursorError, check_fingerprint

    if cursor_payload is None:
        return 0, None
    try:
        check_fingerprint(cursor_payload, fp)
    except CursorError as exc:
        return None, exc.to_response()
    return cursor_payload["off"], None


def _bdc_portfolio_with_holdings(
    *,
    resolution: _BdcResolution,
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

    offset, err = _resolve_cursor_offset(cursor_payload, fp)
    if err is not None:
        return err

    matching, page_items, page_meta = _filter_and_paginate(full_list, query["borrower"], offset, limit)

    next_cursor = None
    if page_meta["remaining"] > 0:
        next_cursor, err = _build_next_cursor(
            _PORTFOLIO_CURSOR_TOOL, filing.accession_number, offset + page_meta["returned"], fp, query
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


async def _bdc_portfolio(
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
    peeked, err = _peek_bdc_cursor(
        cursor, allowed_tools=(_PORTFOLIO_CURSOR_TOOL, _SOI_TEXT_CURSOR_TOOL), accession_number=accession_number
    )
    if err is not None:
        return err

    accession_number, period = _selection_args(peeked, accession_number, period)
    resolution = _resolve_bdc_and_filing(identifier, accession_number, form, period)
    if isinstance(resolution, ToolResponse):
        return resolution
    filing = resolution.selection.filing

    if peeked is not None and peeked.tool == _SOI_TEXT_CURSOR_TOOL:
        return _bdc_portfolio_no_structured_data(filing=filing, resolution=resolution, cursor=cursor)

    query = _portfolio_query(borrower, include_untyped, peeked)
    cursor_payload, err = _decode_page_cursor(
        cursor, tool=_PORTFOLIO_CURSOR_TOOL, accession=filing.accession_number, query=query
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


_NO_SOI_STATEMENT_REASON = (
    "This filing's XBRL has no Schedule of Investments statement and no "
    "dimensional investment facts were found."
)
_NO_STRUCTURED_FIELDS_REASON = (
    "Structured per-investment fields could not be extracted from this "
    "filing's XBRL; showing the raw Schedule of Investments text instead."
)


def _no_xbrl_response(accession: str) -> Any:
    return error(
        f"No XBRL data found for filing {accession}.",
        suggestions=[
            "Use edgar_read to read this filing as raw text instead",
            "Try a different filing from this BDC",
        ],
        error_code="NO_XBRL",
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
        return None, _no_xbrl_response(filing.accession_number)

    soi = xbrl.statements.schedule_of_investments()
    text = str(soi) if soi is not None else ""
    reason = _NO_SOI_STATEMENT_REASON if soi is None else _NO_STRUCTURED_FIELDS_REASON
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
    cursor_payload, err = _decode_page_cursor(cursor, tool=_SOI_TEXT_CURSOR_TOOL, accession=accession, query=None)
    if err is not None:
        return None, None, err
    offset, err = _resolve_cursor_offset(cursor_payload, fp)
    if err is not None:
        return None, None, err

    page_text, meta = paginate_text(text, offset=offset)

    next_cursor = None
    if meta["next_offset"] is not None:
        next_cursor, err = _build_next_cursor(_SOI_TEXT_CURSOR_TOOL, accession, meta["next_offset"], fp, None)
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
    resolution: _BdcResolution,
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
        **_bdc_identity_fields(resolution, filing),
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


# =============================================================================
# bdc_nonaccrual
# =============================================================================

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
    resolution: _BdcResolution,
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
        **_bdc_identity_fields(resolution, filing),
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


def _bdc_nonaccrual_page(resolution: _BdcResolution, result, cursor_payload: Optional[dict], limit: int) -> Any:
    """Page the extracted non-accrual investments and build the response."""
    from edgar.ai.mcp.tools.continuation import fingerprint, paginate

    filing = resolution.selection.filing
    full_list = list(result.investments)
    fp = fingerprint(json.dumps(_nonaccrual_investment_record(inv), sort_keys=True) for inv in full_list)

    offset, err = _resolve_cursor_offset(cursor_payload, fp)
    if err is not None:
        return err

    page_items, page_meta = paginate(full_list, offset=offset, limit=limit)

    next_cursor = None
    if page_meta["remaining"] > 0:
        next_cursor, err = _build_next_cursor(
            _NONACCRUAL_CURSOR_TOOL, filing.accession_number, offset + page_meta["returned"], fp, None
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


async def _bdc_nonaccrual(
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
    peeked, err = _peek_bdc_cursor(
        cursor, allowed_tools=(_NONACCRUAL_CURSOR_TOOL,), accession_number=accession_number
    )
    if err is not None:
        return err

    accession_number, period = _selection_args(peeked, accession_number, period)
    resolution = _resolve_bdc_and_filing(identifier, accession_number, form, period)
    if isinstance(resolution, ToolResponse):
        return resolution
    accession = resolution.selection.filing.accession_number

    cursor_payload, err = _decode_page_cursor(
        cursor, tool=_NONACCRUAL_CURSOR_TOOL, accession=accession, query=None
    )
    if err is not None:
        return err

    result = _load_nonaccrual_result(resolution.selection.filing)
    if result is None:
        return _no_xbrl_response(accession)

    return _bdc_nonaccrual_page(resolution, result, cursor_payload, limit)
