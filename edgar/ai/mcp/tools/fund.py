"""
Fund Tool

Get fund, ETF, BDC, and money market fund data from SEC filings.
"""

from __future__ import annotations

import logging
import math
from decimal import Decimal
from typing import Any, Optional

import pandas as pd

from edgar.ai.mcp.tools.base import (
    tool,
    success,
    error,
    get_error_suggestions,
    classify_error,
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
            if isinstance(v, Decimal):
                record[k] = float(v)
            elif isinstance(v, float) and math.isnan(v):
                record[k] = None
            elif pd.isna(v):
                record[k] = None
            else:
                record[k] = v
        records.append(record)
    return records


@tool(
    name="edgar_fund",
    description="""Get fund, ETF, BDC (Business Development Company), and money market fund data.

Actions:
- lookup: Get fund hierarchy (company/series/class) by ticker, series ID, class ID, or CIK
- search: Search for funds by name
- portfolio: Get fund portfolio holdings (NPORT-P filings)
- money_market: Get money market fund data (N-MFP3/N-MFP2 filings) — yields, share classes, holdings
- bdc_search: Search for Business Development Companies by name or ticker
- bdc_portfolio: Get BDC portfolio investments from Schedule of Investments

Examples:
- Fund lookup: action="lookup", identifier="VFINX"
- Fund search: action="search", query="Vanguard 500"
- Fund portfolio: action="portfolio", identifier="VFINX"
- Money market: action="money_market", identifier="VMFXX"
- BDC search: action="bdc_search", query="Ares"
- BDC portfolio: action="bdc_portfolio", identifier="ARCC\"""",
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
    },
    required=["action"]
)
async def edgar_fund(
    action: str,
    identifier: Optional[str] = None,
    query: Optional[str] = None,
    limit: int = 20,
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
            if not identifier:
                return error(
                    "identifier is required for action='bdc_portfolio'",
                    suggestions=["Provide a BDC ticker (ARCC) or CIK"],
                    error_code="INVALID_ARGUMENTS"
                )
            return await _bdc_portfolio(identifier, limit)

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

        # Try to compute total value
        total_value = None
        value_col = None
        for col in ['value', 'market_value', 'val', 'balance']:
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


async def _bdc_portfolio(identifier: str, limit: int) -> Any:
    """Get BDC portfolio investments from Schedule of Investments."""
    try:
        from edgar.bdc.reference import get_bdc_list
        from edgar.bdc.search import find_bdc

        bdcs = get_bdc_list()
        bdc = None

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

        if bdc is None:
            return error(
                f"Could not find BDC: '{identifier}'",
                suggestions=[
                    "Use action='bdc_search' to find BDCs by name",
                    "Try a ticker (ARCC, MAIN) or CIK number",
                ]
            )

        result: dict[str, Any] = {
            "analysis": "bdc_portfolio",
            "name": bdc.name,
            "cik": bdc.cik,
            "is_active": bdc.is_active,
        }

        if bdc.state:
            result["state"] = bdc.state

        # Try portfolio_investments first
        investments = None
        try:
            investments = bdc.portfolio_investments()
        except Exception:
            logger.debug("Could not get portfolio_investments")

        if investments is not None and len(investments) > 0:
            # Extract investment data
            inv_records = []
            for inv in investments[:limit]:
                inv_dict: dict[str, Any] = {}
                if hasattr(inv, 'name'):
                    inv_dict["name"] = inv.name
                if hasattr(inv, 'investment_type'):
                    inv_dict["type"] = str(inv.investment_type) if inv.investment_type else None
                if hasattr(inv, 'fair_value') and inv.fair_value is not None:
                    inv_dict["fair_value"] = float(inv.fair_value) if isinstance(inv.fair_value, Decimal) else inv.fair_value
                if hasattr(inv, 'cost') and inv.cost is not None:
                    inv_dict["cost"] = float(inv.cost) if isinstance(inv.cost, Decimal) else inv.cost
                if hasattr(inv, 'interest_rate') and inv.interest_rate is not None:
                    inv_dict["interest_rate"] = float(inv.interest_rate) if isinstance(inv.interest_rate, Decimal) else inv.interest_rate
                if inv_dict:
                    inv_records.append(inv_dict)

            total_count = len(investments)

            # Compute summary stats
            total_fair_value = None
            total_cost = None
            try:
                fv_values = [float(i.fair_value) for i in investments if hasattr(i, 'fair_value') and i.fair_value is not None]
                if fv_values:
                    total_fair_value = sum(fv_values)
                cost_values = [float(i.cost) for i in investments if hasattr(i, 'cost') and i.cost is not None]
                if cost_values:
                    total_cost = sum(cost_values)
            except Exception:
                pass

            result["total_investments"] = total_count
            if total_fair_value is not None:
                result["total_fair_value"] = total_fair_value
            if total_cost is not None:
                result["total_cost"] = total_cost
            result["investments"] = inv_records

            if total_count > limit:
                result["note"] = f"Showing {limit} of {total_count} investments. Increase limit for more."

        else:
            # Fallback to schedule_of_investments as string representation
            try:
                soi = bdc.schedule_of_investments()
                if soi is not None:
                    result["schedule_of_investments"] = str(soi)[:4000]
                    result["note"] = "Showing text summary of Schedule of Investments (structured data unavailable)"
                else:
                    result["note"] = "No portfolio investment data available for this BDC"
            except Exception:
                result["note"] = "Could not retrieve portfolio investment data for this BDC"

        next_steps = [
            "Use action='bdc_search' to find other BDCs",
            "Use edgar_company with this CIK for full company analysis",
            "Use edgar_filing to read the BDC's latest 10-K or 10-Q",
        ]

        return success(result, next_steps=next_steps)

    except Exception as e:
        return error(str(e), suggestions=get_error_suggestions(e))
