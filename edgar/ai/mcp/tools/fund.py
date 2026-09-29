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
)
from edgar.ai.mcp.tools.bdc.identity import bdc_search
from edgar.ai.mcp.tools.bdc.nonaccrual import bdc_nonaccrual
from edgar.ai.mcp.tools.bdc.portfolio import bdc_portfolio

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
            return await bdc_search(query, limit)

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
            return await bdc_portfolio(
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
            return await bdc_nonaccrual(
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
