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
    description="""Get ownership data: insider transactions, institutional holders, or fund portfolios.

- For companies: shows WHO owns the stock (insiders, institutions)
- For funds/institutions: shows WHAT they own (13F portfolio)

Examples:
- Insider trades: identifier="AAPL", analysis_type="insiders"
- Who owns Apple: identifier="AAPL", analysis_type="institutions"
- Berkshire portfolio: identifier="1067983", analysis_type="fund_portfolio\"""",
    params={
        "identifier": {
            "type": "string",
            "description": "Company ticker/CIK OR fund/institution CIK"
        },
        "analysis_type": {
            "type": "string",
            "enum": ["insiders", "institutions", "fund_portfolio"],
            "description": "insiders=Form 4 trades, institutions=13F holders, fund_portfolio=what a fund owns"
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
        elif analysis_type == "institutions":
            return await _get_institutional_holders(identifier, limit)
        elif analysis_type == "fund_portfolio":
            return await _get_fund_holdings(identifier, limit)
        else:
            return error(
                f"Unknown analysis_type: {analysis_type}",
                suggestions=["Use 'insiders', 'institutions', or 'fund_portfolio'"]
            )

    except Exception as e:
        logger.exception("Error in edgar_ownership")
        return error(str(e), suggestions=get_error_suggestions(e))


async def _get_insider_transactions(identifier: str, days: int, limit: int) -> Any:
    """Get insider trading activity from Form 4 filings."""
    try:
        company = resolve_company(identifier)

        # Get Form 4 filings (convert to list to enable slicing)
        form4_filings = list(company.get_filings(form="4"))[:limit * 2]  # Get extra in case some fail

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
            "Use analysis_type='institutions' to see institutional holders",
            "Use edgar_company for full company analysis"
        ]

        return success(result, next_steps=next_steps)

    except Exception as e:
        return error(str(e), suggestions=get_error_suggestions(e))


async def _get_institutional_holders(identifier: str, limit: int) -> Any:
    """Get institutional holders from 13F filings that mention this company."""
    try:
        company = resolve_company(identifier)

        # Note: Getting all 13F filers that hold a specific stock is complex
        # and requires cross-referencing many 13F filings.
        # For now, we provide guidance on how to approach this.

        result = {
            "company": company.name,
            "cik": str(company.cik),
            "analysis": "institutional_holders",
            "note": (
                "To find institutional holders, you would need to analyze 13F filings "
                "from major institutions. Consider using edgar_search with form='13F-HR' "
                "to find recent 13F filings, then use edgar_ownership with "
                "analysis_type='fund_portfolio' to see each fund's holdings."
            ),
            "suggested_institutions": [
                {"name": "Berkshire Hathaway", "cik": "1067983"},
                {"name": "BlackRock", "cik": "1364742"},
                {"name": "Vanguard", "cik": "102909"},
                {"name": "State Street", "cik": "93751"},
            ]
        }

        next_steps = [
            "Use edgar_ownership with a fund CIK and analysis_type='fund_portfolio'",
            "Use edgar_search with form='13F-HR' to find institutional filings"
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
            "Use edgar_search with form='13F-HR' for other institutional filings"
        ]

        return success(result, next_steps=next_steps)

    except Exception as e:
        return error(str(e), suggestions=get_error_suggestions(e))
