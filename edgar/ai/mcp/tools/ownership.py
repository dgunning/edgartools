"""
Ownership Tool

Get ownership data: insider transactions, institutional holders, or fund portfolios.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from edgar.ai.mcp.tools.base import (
    tool,
    success,
    error,
    resolve_company,
    get_error_suggestions,
)

logger = logging.getLogger(__name__)


@tool(
    name="edgar_ownership",
    description="""Get ownership data: insider transactions, fund portfolios, or quarter-over-quarter portfolio changes.

- For companies: shows insider trading activity (Form 4 filings)
- For funds/institutions: shows WHAT they own (13F portfolio holdings)
- Portfolio diff: shows what changed between quarters (new positions, exits, increases, decreases)

Examples:
- Insider trades: identifier="AAPL", analysis_type="insiders"
- Berkshire portfolio: identifier="1067983", analysis_type="fund_portfolio"
- Portfolio changes: identifier="1067983", analysis_type="portfolio_diff"
- Vanguard holdings: identifier="102909", analysis_type="fund_portfolio\"""",
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
            "description": "Lookback period for insider transactions (default 90)",
            "default": 90
        },
        "limit": {
            "type": "integer",
            "description": "Max results (default 20)",
            "default": 20
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
    """Get insider trading activity from Form 4 filings."""
    try:
        company = resolve_company(identifier)

        # Get Form 4 filings
        form4_filings = company.get_filings(form="4").head(limit * 2)  # Get extra in case some fail

        transactions = []
        for filing in form4_filings:
            try:
                txn = {
                    "filing_date": str(filing.filing_date),
                    "accession_number": filing.accession_number,
                }

                # Try to extract details from the Form 4 object
                try:
                    obj = filing.obj()

                    # Get reporting owner info
                    if hasattr(obj, 'reporting_owner'):
                        owner = obj.reporting_owner
                        if hasattr(owner, 'name'):
                            txn["insider_name"] = owner.name
                        else:
                            txn["insider_name"] = str(owner)

                    # Get relationship
                    if hasattr(obj, 'is_officer'):
                        txn["is_officer"] = obj.is_officer
                    if hasattr(obj, 'is_director'):
                        txn["is_director"] = obj.is_director
                    if hasattr(obj, 'officer_title'):
                        txn["title"] = obj.officer_title

                    # Get transactions
                    if hasattr(obj, 'transactions'):
                        txn_list = []
                        for t in obj.transactions[:5]:  # Limit transactions per filing
                            txn_detail = {}
                            if hasattr(t, 'transaction_type'):
                                txn_detail["type"] = t.transaction_type
                            if hasattr(t, 'shares'):
                                txn_detail["shares"] = t.shares
                            if hasattr(t, 'price'):
                                txn_detail["price"] = float(t.price) if t.price else None
                            if hasattr(t, 'acquired_disposed'):
                                txn_detail["action"] = t.acquired_disposed
                            if txn_detail:
                                txn_list.append(txn_detail)
                        if txn_list:
                            txn["transactions"] = txn_list

                except Exception as e:
                    logger.debug(f"Could not parse Form 4 details: {e}")

                transactions.append(txn)

                if len(transactions) >= limit:
                    break

            except Exception as e:
                logger.debug(f"Could not process Form 4 filing: {e}")
                continue

        result = {
            "company": company.name,
            "cik": str(company.cik),
            "analysis": "insider_transactions",
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

            if hasattr(obj, 'holdings'):
                holdings = []
                for h in obj.holdings[:limit]:
                    holding = {}
                    if hasattr(h, 'name') or hasattr(h, 'issuer'):
                        holding["company"] = getattr(h, 'name', None) or getattr(h, 'issuer', 'Unknown')
                    if hasattr(h, 'cusip'):
                        holding["cusip"] = h.cusip
                    if hasattr(h, 'shares') or hasattr(h, 'value'):
                        holding["shares"] = getattr(h, 'shares', None)
                        holding["value"] = getattr(h, 'value', None)
                    if holding:
                        holdings.append(holding)

                result["holdings_count"] = len(obj.holdings) if hasattr(obj, 'holdings') else 0
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
        import math

        changes = []
        for _, row in df.head(limit).iterrows():
            entry = {
                "ticker": row.get("Ticker") if row.get("Ticker") and str(row.get("Ticker")) != "nan" else None,
                "issuer": row.get("Issuer", ""),
                "cusip": row.get("Cusip", ""),
                "status": row.get("Status", ""),
            }

            # Current values
            shares = row.get("Shares")
            if shares is not None and not (isinstance(shares, float) and math.isnan(shares)):
                entry["shares"] = int(shares)
            value = row.get("Value")
            if value is not None and not (isinstance(value, float) and math.isnan(value)):
                entry["value"] = int(value)

            # Previous values
            prev_shares = row.get("PrevShares")
            if prev_shares is not None and not (isinstance(prev_shares, float) and math.isnan(prev_shares)):
                entry["prev_shares"] = int(prev_shares)
            prev_value = row.get("PrevValue")
            if prev_value is not None and not (isinstance(prev_value, float) and math.isnan(prev_value)):
                entry["prev_value"] = int(prev_value)

            # Changes
            share_change = row.get("ShareChange")
            if share_change is not None and not (isinstance(share_change, float) and math.isnan(share_change)):
                entry["share_change"] = int(share_change)
            share_pct = row.get("ShareChangePct")
            if share_pct is not None and not (isinstance(share_pct, float) and math.isnan(share_pct)):
                entry["share_change_pct"] = round(share_pct, 1)
            value_change = row.get("ValueChange")
            if value_change is not None and not (isinstance(value_change, float) and math.isnan(value_change)):
                entry["value_change"] = int(value_change)

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
