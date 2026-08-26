"""
Ownership Tool

Get ownership data: insider transactions, institutional holders, or fund portfolios.
"""

from __future__ import annotations

import logging
from typing import Any

from edgar.ai.mcp.tools.base import (
    tool,
    success,
    error,
    resolve_company,
    get_error_suggestions,
    _cell_number,
    _cell_text,
)

logger = logging.getLogger(__name__)


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

            holdings_table = getattr(obj, 'holdings', None)

            if holdings_table is not None:
                # ``ThirteenF.holdings`` is a DataFrame, and iterating one yields
                # its column names rather than its rows: every attribute probe
                # missed and the list came back empty for every fund. Walk it the
                # way ``_get_portfolio_diff`` below already walks its comparison.
                holdings = []
                for _, row in holdings_table.head(limit).iterrows():
                    holding = {}
                    issuer = _cell_text(row.get("Issuer"))
                    if issuer:
                        holding["company"] = issuer
                    cusip = _cell_text(row.get("Cusip"))
                    if cusip:
                        holding["cusip"] = cusip
                    # Independently, the way company and cusip are: writing the
                    # pair together put an explicit `"value": null` in the
                    # response for a row whose value did not parse, and a caller
                    # testing `"value" in holding` reads that as a value.
                    shares = _cell_number(row.get("SharesPrnAmount"), as_int=True)
                    if shares is not None:
                        holding["shares"] = shares
                    value = _cell_number(row.get("Value"), as_int=True)
                    if value is not None:
                        holding["value"] = value
                    if holding:
                        holdings.append(holding)

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
