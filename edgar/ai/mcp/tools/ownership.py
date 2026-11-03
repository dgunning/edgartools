"""
Ownership Tool

Get ownership data: insider transactions, institutional holders, or fund portfolios.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from edgar.ai.mcp.tools.base import (
    tool,
    success,
    error,
    resolve_company,
    get_error_suggestions,
    _cell_number,
    _cell_text,
    _holding_rows,
)

logger = logging.getLogger(__name__)

# Upper bound on `limit`, matching edgar_monitor and edgar_screen. The insider
# path parses up to `limit` Form 4 filings, so an unbounded limit would let
# one call fetch every Form 4 a company has ever filed.
_MAX_LIMIT = 100

# Trades reported per Form 4 entry. Form4 lists market sales before exercises
# and derivative rows, so a low cap hides exercises behind a run of sale lines;
# `transaction_total` and `transactions_truncated` say when rows were left out.
_MAX_TRADES_PER_FILING = 25


@tool(
    name="edgar_ownership",
    description="""Use this for insider trading activity (Form 4) or institutional fund portfolios (13F). For companies, use analysis_type="insiders". For funds/institutions, use analysis_type="fund_portfolio" with the fund's CIK.

Examples:
- Insider trades: identifier="AAPL", analysis_type="insiders"
- Berkshire portfolio: identifier="1067983", analysis_type="fund_portfolio"
- Portfolio changes: identifier="1067983", analysis_type="portfolio_diff\"""",
    params={
        "identifier": {
            "type": "string",
            "description": "Company ticker/CIK (for insiders) OR fund/institution CIK (for fund_portfolio/portfolio_diff)"
        },
        "analysis_type": {
            "type": "string",
            "enum": ["insiders", "fund_portfolio", "portfolio_diff"],
            "description": "insiders=Form 4 insider trades, fund_portfolio=13F holdings, portfolio_diff=quarter-over-quarter changes"
        },
        "days": {
            "type": "integer",
            "description": "Only Form 4s filed in the last N days (default 90)",
            "default": 90,
            "minimum": 1
        },
        "limit": {
            "type": "integer",
            "description": "Max results (default 20, max 100)",
            "default": 20,
            "minimum": 1,
            "maximum": _MAX_LIMIT
        }
    },
    required=["identifier", "analysis_type"]
)
async def edgar_ownership(
    identifier: str,
    analysis_type: str,
    days: int = 90,
    limit: int = 20
) -> Any:
    """
    Get ownership information.

    Routes to appropriate analysis based on analysis_type.
    """
    try:
        limit = min(max(int(limit), 1), _MAX_LIMIT)
        if analysis_type == "insiders":
            return await _get_insider_transactions(identifier, days, limit)
        elif analysis_type == "fund_portfolio":
            return await _get_fund_holdings(identifier, limit)
        elif analysis_type == "portfolio_diff":
            return await _get_portfolio_diff(identifier, limit)
        elif analysis_type == "institutions":
            # Graceful redirect for legacy callers
            return error(
                "The 'institutions' analysis type has been removed. SEC EDGAR does not "
                "provide a reverse-lookup API for institutional holders of a stock.",
                suggestions=[
                    "Use analysis_type='fund_portfolio' with a fund's CIK to see what it holds",
                    "Use edgar_search with form='13F-HR' to find institutional filings",
                    "Use analysis_type='insiders' to see insider trading activity",
                ]
            )
        else:
            return error(
                f"Unknown analysis_type: {analysis_type}",
                suggestions=["Use 'insiders', 'fund_portfolio', or 'portfolio_diff'"]
            )

    except Exception as e:
        logger.exception("Error in edgar_ownership")
        return error(str(e), suggestions=get_error_suggestions(e))



async def _get_insider_transactions(identifier: str, days: int, limit: int) -> Any:
    """Get insider trading activity from Form 4 filings filed in the last `days` days."""
    try:
        company = resolve_company(identifier)
        days = max(int(days), 1)
        since = date.today() - timedelta(days=days)

        form4_filings = company.get_filings(
            form="4", filing_date=f"{since.isoformat()}:"
        ).head(limit)

        transactions = [_insider_entry(filing) for filing in form4_filings]

        result = {
            "company": company.name,
            "cik": str(company.cik),
            "analysis": "insider_transactions",
            "days": days,
            "since": since.isoformat(),
            "transaction_count": len(transactions),
            "transactions": transactions,
        }

        next_steps = [
            "Use analysis_type='fund_portfolio' with a fund's CIK to see its holdings",
            "Use edgar_company for full company analysis"
        ]

        return success(result, next_steps=next_steps)

    except Exception as e:
        return error(str(e), suggestions=get_error_suggestions(e))


def _insider_entry(filing) -> dict[str, Any]:
    """Summarise one Form 4: who filed it, their role, and its transactions."""
    entry: dict[str, Any] = {
        "form": filing.form,
        "filing_date": str(filing.filing_date),
        "accession_number": filing.accession_number,
    }
    try:
        form4 = filing.obj()
        summary = form4.get_ownership_summary()
        owners = form4.reporting_owners.owners
        insider = {
            "insider_name": form4.insider_name,
            "title": form4.position,
            "is_officer": any(o.is_officer for o in owners),
            "is_director": any(o.is_director for o in owners),
            "is_ten_pct_owner": any(o.is_ten_pct_owner for o in owners),
        }
    except Exception as e:
        logger.debug(f"Could not parse Form 4 {filing.accession_number}: {e}")
        entry["error"] = f"Could not parse Form 4: {e}"
        return entry

    entry.update(insider)
    trades = summary.transactions
    entry["transaction_total"] = len(trades)
    entry["transactions_truncated"] = len(trades) > _MAX_TRADES_PER_FILING
    entry["transactions"] = [
        {
            "type": t.transaction_type,
            "code": t.code,
            "description": t.code_description,
            "security": t.security_title,
            "shares": t.shares_numeric,
            "price": t.price_numeric,
            "value": t.value_numeric,
            "is_derivative": t.is_derivative,
        }
        for t in trades[:_MAX_TRADES_PER_FILING]
    ]
    return entry


async def _get_fund_holdings(identifier: str, limit: int) -> Any:
    """Get portfolio holdings for an institutional investor (13F filer)."""
    try:
        # For 13F filers, they often don't have tickers
        # Try to resolve, accepting CIK directly
        try:
            company = resolve_company(identifier)
        except ValueError:
            # If standard resolution fails for funds, they might need CIK
            return error(
                f"Could not find fund: {identifier}",
                suggestions=[
                    "13F filers (hedge funds, institutions) often need CIK, not ticker",
                    "Example: Berkshire Hathaway CIK is 1067983",
                    "Use edgar_search to find the fund's CIK"
                ]
            )

        # Get 13F filings
        filings_13f = company.get_filings(form="13F-HR")

        if not filings_13f or len(filings_13f) == 0:
            return error(
                f"No 13F filings found for {identifier}",
                suggestions=[
                    "This may not be an institutional investor required to file 13F",
                    "13F is required for institutions managing >$100M in securities",
                    "Try a known fund CIK like 1067983 (Berkshire)"
                ]
            )

        # Get the most recent 13F
        latest_13f = filings_13f[0]

        result = {
            "fund": company.name,
            "cik": str(company.cik),
            "analysis": "fund_portfolio",
            "filing_date": str(latest_13f.filing_date),
            "accession_number": latest_13f.accession_number,
        }

        # Try to extract holdings
        try:
            obj = latest_13f.obj()

            holdings_table = getattr(obj, 'holdings', None)

            if holdings_table is not None:
                holdings = _holding_rows(holdings_table, limit)

                result["holdings_count"] = len(holdings_table)
                result["holdings"] = holdings

                # Calculate total value if available
                if holdings and all(h.get("value") for h in holdings):
                    result["total_value_shown"] = sum(h["value"] for h in holdings if h.get("value"))

        except Exception as e:
            logger.warning(f"Could not extract 13F holdings: {e}")
            result["holdings_error"] = str(e)

        next_steps = [
            "Use edgar_company to analyze specific holdings",
            "Use edgar_search with form='13F-HR' for other institutional filings",
            "Use analysis_type='portfolio_diff' to see quarter-over-quarter changes",
        ]

        return success(result, next_steps=next_steps)

    except Exception as e:
        return error(str(e), suggestions=get_error_suggestions(e))


async def _get_portfolio_diff(identifier: str, limit: int) -> Any:
    """Get quarter-over-quarter portfolio changes for a 13F filer."""
    try:
        try:
            company = resolve_company(identifier)
        except ValueError:
            return error(
                f"Could not find fund: {identifier}",
                suggestions=[
                    "13F filers (hedge funds, institutions) often need CIK, not ticker",
                    "Example: Berkshire Hathaway CIK is 1067983",
                    "Use edgar_search to find the fund's CIK"
                ]
            )

        # Get latest 13F filing
        filings_13f = company.get_filings(form="13F-HR")

        if not filings_13f or len(filings_13f) == 0:
            return error(
                f"No 13F filings found for {identifier}",
                suggestions=[
                    "This may not be an institutional investor required to file 13F",
                    "13F is required for institutions managing >$100M in securities",
                ]
            )

        latest_13f = filings_13f[0]
        obj = latest_13f.obj()

        comparison = obj.compare_holdings()
        if comparison is None:
            return error(
                "Could not compare holdings — no previous quarter data available",
                suggestions=[
                    "Use analysis_type='fund_portfolio' to see current holdings",
                    "The fund may only have one 13F filing",
                ]
            )

        # Serialize the comparison DataFrame
        df = comparison.data

        changes = []
        for _, row in df.head(limit).iterrows():
            entry = {
                "ticker": _cell_text(row.get("Ticker")),
                "issuer": _cell_text(row.get("Issuer")) or "",
                "cusip": _cell_text(row.get("Cusip")) or "",
                "status": _cell_text(row.get("Status")) or "",
            }
            # Option rows share a CUSIP with the equity row; say which one this is (GH #1848)
            put_call = _cell_text(row.get("PutCall"))
            if put_call:
                entry["put_call"] = put_call

            # Current values
            shares = _cell_number(row.get("Shares"), as_int=True)
            if shares is not None:
                entry["shares"] = shares
            value = _cell_number(row.get("Value"), as_int=True)
            if value is not None:
                entry["value"] = value

            # Previous values
            prev_shares = _cell_number(row.get("PrevShares"), as_int=True)
            if prev_shares is not None:
                entry["prev_shares"] = prev_shares
            prev_value = _cell_number(row.get("PrevValue"), as_int=True)
            if prev_value is not None:
                entry["prev_value"] = prev_value

            # Changes
            share_change = _cell_number(row.get("ShareChange"), as_int=True)
            if share_change is not None:
                entry["share_change"] = share_change
            share_pct = _cell_number(row.get("ShareChangePct"))
            if share_pct is not None:
                entry["share_change_pct"] = round(share_pct, 1)
            value_change = _cell_number(row.get("ValueChange"), as_int=True)
            if value_change is not None:
                entry["value_change"] = value_change

            changes.append(entry)

        # Summary by status
        status_counts = df["Status"].value_counts().to_dict()

        result = {
            "fund": company.name,
            "cik": str(company.cik),
            "analysis": "portfolio_diff",
            "current_period": comparison.current_period,
            "previous_period": comparison.previous_period,
            "total_positions": len(df),
            "summary": status_counts,
            "changes": changes,
        }

        if len(df) > limit:
            result["note"] = f"Showing {limit} of {len(df)} positions. Increase limit for more."

        next_steps = [
            "Use analysis_type='fund_portfolio' to see full current holdings",
            "Use edgar_company to analyze specific portfolio companies",
            "Use edgar_trends to check financial trends for holdings of interest",
        ]

        return success(result, next_steps=next_steps)

    except Exception as e:
        return error(str(e), suggestions=get_error_suggestions(e))
