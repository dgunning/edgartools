"""
Fund Tool

Get fund, ETF, BDC, and money market fund data from SEC filings.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Optional

import pandas as pd

from edgar.ai.mcp.tools.base import (
    tool,
    success,
    error,
    get_error_suggestions,
    classify_error,
    _cell_missing,
    _cell_number,
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
    description="""Use this for mutual fund, ETF, BDC, and money market fund analysis. Supports fund lookup, portfolio holdings, money market yields, and BDC investments.

Actions: lookup (find fund by ticker/CIK), search (by name), portfolio (NPORT holdings), money_market (yields/NAV), bdc_search, bdc_portfolio.

Examples:
- Fund lookup: action="lookup", identifier="VFINX"
- Fund search: action="search", query="Vanguard 500"
- Fund portfolio: action="portfolio", identifier="VFINX"
- Money market: action="money_market", identifier="VMFXX"
- BDC search: action="bdc_search", query="Ares"
- BDC portfolio (latest 10-K): action="bdc_portfolio", identifier="ARCC"
- BDC portfolio (chosen period): action="bdc_portfolio", identifier="ARCC", form="10-Q", period="2026-06-30"
- BDC portfolio (chosen filing by accession): action="bdc_portfolio", accession_number="0001628280-26-050307"
- BDC portfolio (borrower filter): action="bdc_portfolio", identifier="ARCC", borrower="Ivy Hill"
- BDC portfolio (next page): action="bdc_portfolio", identifier="ARCC", cursor="<page.next_cursor from the previous call>\"""",
    params={
        "action": {
            "type": "string",
            "enum": ["lookup", "search", "portfolio", "money_market",
                     "bdc_search", "bdc_portfolio"],
            "description": "The action to perform"
        },
        "identifier": {
            "type": "string",
            "description": "Fund ticker, series ID (S000XXXXX), class ID (C000XXXXX), or CIK"
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
            "description": "Continuation cursor from a previous bdc_portfolio response's "
                            "page.next_cursor (or the text fallback's next_cursor), to fetch the next page."
        },
        "include_untyped": {
            "type": "boolean",
            "description": "BDC actions only. Include investments with an unrecognized/untyped "
                            "classification (default false).",
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
    include_untyped: bool = False,
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
            if not identifier and not accession_number:
                return error(
                    "identifier or accession_number is required for action='bdc_portfolio'",
                    suggestions=[
                        "Provide a BDC ticker (ARCC) or CIK as identifier",
                        "Or provide accession_number to pin an exact filing",
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

        else:
            return error(
                f"Unknown action: {action}",
                suggestions=["Use 'lookup', 'search', 'portfolio', 'money_market', 'bdc_search', or 'bdc_portfolio'"]
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


def _find_bdc(identifier: str):
    """Resolve a ticker, CIK, or name to a BDCEntity, or None if not found."""
    from edgar.bdc.reference import get_bdc_list
    from edgar.bdc.search import find_bdc

    bdcs = get_bdc_list()

    # Try ticker first
    bdc = bdcs.get_by_ticker(identifier.upper())

    # Try CIK
    if bdc is None:
        try:
            bdc = bdcs.get_by_cik(int(identifier))
        except (ValueError, TypeError):
            pass

    # Try search as fallback
    if bdc is None:
        search_results = find_bdc(identifier, top_n=1)
        if not search_results.empty:
            bdc = search_results[0]

    return bdc


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


async def _bdc_portfolio(
    identifier: Optional[str],
    accession_number: Optional[str],
    form: str,
    period: Optional[str],
    borrower: Optional[str],
    cursor: Optional[str],
    limit: int,
    include_untyped: bool,
) -> Any:
    """Get BDC portfolio investments from a chosen filing's Schedule of Investments.

    Resolves exactly one filing via the shared selection resolver — by
    accession number, period, or the BDC's latest 10-K/10-Q — then extracts
    holdings via `portfolio_investments_from_filing` (cached: extraction
    costs roughly 11s for a large BDC like ARCC) and pages/filters the
    result. Falls back to the raw Schedule of Investments text (also paged)
    when the filing's XBRL has no per-investment structured data, and errors
    with NO_XBRL when the filing has no XBRL at all.
    """
    from edgar import __version__ as edgar_version
    from edgar.ai.mcp.tools.base import format_source
    from edgar.ai.mcp.tools.continuation import (
        CursorError,
        check_fingerprint,
        decode_cursor,
        encode_cursor,
        fingerprint,
        paginate,
        results_cache,
    )
    from edgar.ai.mcp.tools.selection import FilingSelectionError, resolve_report_filing
    from edgar.bdc.investments import portfolio_investments_from_filing
    from edgar.bdc.reference import get_bdc_list, is_bdc_cik

    bdc = None
    try:
        if identifier:
            bdc = _find_bdc(identifier)
            if bdc is None:
                return error(
                    f"Could not find BDC: '{identifier}'",
                    suggestions=[
                        "Use action='bdc_search' to find BDCs by name",
                        "Try a ticker (ARCC, MAIN) or CIK number",
                    ],
                    error_code="COMPANY_NOT_FOUND",
                )
            selection = resolve_report_filing(
                form=form,
                accession_number=accession_number,
                period=period,
                company=bdc.get_company(),
            )
        else:
            selection = resolve_report_filing(accession_number=accession_number)
            if not is_bdc_cik(int(selection.filing.cik)):
                return error(
                    f"CIK {selection.filing.cik} is not a Business Development Company.",
                    suggestions=[
                        "Use action='bdc_search' to find BDCs by name or ticker",
                        "Provide a BDC identifier instead of accession_number alone",
                    ],
                    error_code="NOT_A_BDC",
                )
            bdc = get_bdc_list().get_by_cik(int(selection.filing.cik))
    except FilingSelectionError as exc:
        return exc.to_response()

    filing = selection.filing
    selected_by = selection.selected_by
    accession = filing.accession_number

    normalized_borrower = borrower.strip().lower() if borrower else None
    query = {"borrower": normalized_borrower, "include_untyped": bool(include_untyped)}

    cursor_payload = None
    if cursor:
        try:
            cursor_payload = decode_cursor(
                cursor,
                tool="edgar_fund:bdc_portfolio",
                accession=accession,
                query=query,
            )
        except CursorError as exc:
            return exc.to_response()

    cache_key = ("bdc_portfolio", accession, bool(include_untyped), edgar_version)
    investments = results_cache.get(cache_key)
    if investments is None:
        investments = portfolio_investments_from_filing(filing, include_untyped=include_untyped)
        if investments is not None:
            results_cache.put(cache_key, investments)

    if investments is None or len(investments) == 0:
        return _bdc_portfolio_no_structured_data(
            filing=filing,
            selected_by=selected_by,
            bdc=bdc,
            cursor=cursor,
        )

    full_list = list(investments)
    fp = fingerprint(inv.identifier for inv in full_list)

    offset = 0
    if cursor_payload is not None:
        try:
            check_fingerprint(cursor_payload, fp)
        except CursorError as exc:
            return exc.to_response()
        offset = cursor_payload["off"]

    if normalized_borrower:
        matching = [
            inv for inv in full_list
            if normalized_borrower in (inv.company_name or "").lower()
            or normalized_borrower in (inv.identifier or "").lower()
        ]
    else:
        matching = full_list

    page_items, page_meta = paginate(matching, offset=offset, limit=limit)

    next_cursor = None
    if page_meta["remaining"] > 0:
        try:
            next_cursor = encode_cursor(
                tool="edgar_fund:bdc_portfolio",
                accession=accession,
                offset=offset + page_meta["returned"],
                fp=fp,
                query=query,
            )
        except CursorError as exc:
            return exc.to_response()

    dq = investments.data_quality
    result: dict[str, Any] = {
        "analysis": "bdc_portfolio",
        "name": bdc.name if bdc is not None else filing.company,
        "cik": bdc.cik if bdc is not None else int(filing.cik),
        "is_active": bdc.is_active if bdc is not None else None,
        "source": format_source(filing, selected_by),
        "total_investments": len(full_list),
        "total_fair_value": float(investments.total_fair_value),
        "total_cost": float(investments.total_cost),
        "investments": [_investment_record(inv) for inv in page_items],
        "page": {
            "offset": page_meta["offset"],
            "returned": page_meta["returned"],
            "total_matching": len(matching),
            "total_extracted": len(full_list),
            "remaining": page_meta["remaining"],
            "next_cursor": next_cursor,
        },
        "extraction": {
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
        },
    }

    if bdc is not None and bdc.state:
        result["state"] = bdc.state

    if normalized_borrower:
        filtered_fv = sum(
            (inv.fair_value for inv in matching if inv.fair_value is not None), Decimal(0)
        )
        filtered_cost = sum(
            (inv.cost for inv in matching if inv.cost is not None), Decimal(0)
        )
        result["filtered_totals"] = {
            "count": len(matching),
            "fair_value": float(filtered_fv),
            "cost": float(filtered_cost),
        }

    if page_meta["remaining"] > 0:
        result["note"] = (
            f"{page_meta['remaining']} more matching investment(s) remain. "
            "Pass the returned cursor to action='bdc_portfolio' to continue."
        )

    next_steps = [
        "Use action='bdc_search' to find other BDCs",
        "Use edgar_company with this CIK for full company analysis",
    ]
    if next_cursor:
        next_steps.append("Pass the returned cursor to continue paging through investments")
    else:
        next_steps.append("Use edgar_read to read the BDC's filing sections")

    return success(result, next_steps=next_steps)


def _bdc_portfolio_no_structured_data(filing, selected_by: str, bdc, cursor: Optional[str]) -> Any:
    """Fallback when the filing's XBRL has no per-investment structured data.

    Returns the raw Schedule of Investments text, paged, or a NO_XBRL error
    when the filing carries no XBRL at all.
    """
    from edgar.ai.mcp.tools.base import format_source
    from edgar.ai.mcp.tools.continuation import (
        CursorError,
        check_fingerprint,
        decode_cursor,
        encode_cursor,
        fingerprint,
        paginate_text,
        text_cache,
    )

    accession = filing.accession_number
    xbrl = filing.xbrl()
    if xbrl is None:
        return error(
            f"No XBRL data found for filing {accession}.",
            suggestions=[
                "Use edgar_read to read this filing as raw text instead",
                "Try a different filing from this BDC",
            ],
            error_code="NO_XBRL",
        )

    soi = xbrl.statements.schedule_of_investments()

    text_cache_key = ("bdc_soi_text", accession)
    text = text_cache.get(text_cache_key)
    if text is None:
        text = str(soi) if soi is not None else ""
        text_cache.put(text_cache_key, text, size_bytes=len(text.encode("utf-8")))

    fp = fingerprint([text])

    offset = 0
    if cursor:
        try:
            payload = decode_cursor(cursor, tool="edgar_fund:bdc_soi_text", accession=accession, query=None)
            check_fingerprint(payload, fp)
        except CursorError as exc:
            return exc.to_response()
        offset = payload["off"]

    page_text, text_meta = paginate_text(text, offset=offset)

    next_cursor = None
    if text_meta["next_offset"] is not None:
        try:
            next_cursor = encode_cursor(
                tool="edgar_fund:bdc_soi_text",
                accession=accession,
                offset=text_meta["next_offset"],
                fp=fp,
                query=None,
            )
        except CursorError as exc:
            return exc.to_response()

    reason = (
        "This filing's XBRL has no Schedule of Investments statement and no "
        "dimensional investment facts were found."
        if soi is None else
        "Structured per-investment fields could not be extracted from this "
        "filing's XBRL; showing the raw Schedule of Investments text instead."
    )

    result: dict[str, Any] = {
        "analysis": "bdc_portfolio",
        "name": bdc.name if bdc is not None else filing.company,
        "cik": bdc.cik if bdc is not None else int(filing.cik),
        "is_active": bdc.is_active if bdc is not None else None,
        "source": format_source(filing, selected_by),
        "total_investments": 0,
        "total_fair_value": None,
        "total_cost": None,
        "investments": [],
        "schedule_of_investments": page_text,
        "structured_data_unavailable": {"reason": reason},
        "text_page": {
            "offset": text_meta["offset"],
            "returned_chars": text_meta["returned_chars"],
            "total_chars": text_meta["total_chars"],
            "remaining_chars": text_meta["remaining_chars"],
            "next_cursor": next_cursor,
        },
    }

    if bdc is not None and bdc.state:
        result["state"] = bdc.state

    if text_meta["remaining_chars"] > 0:
        result["note"] = (
            f"{text_meta['remaining_chars']} more character(s) of the Schedule of "
            "Investments text remain. Pass the returned cursor to continue."
        )

    next_steps = [
        "Use edgar_notes to look up disclosures for this filing",
        "Use edgar_read to read the full filing text",
    ]

    return success(result, next_steps=next_steps)
