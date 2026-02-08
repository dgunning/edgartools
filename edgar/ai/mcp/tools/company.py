"""
Company Intelligence Tool

The main "tell me about X" tool that combines profile, financials,
filings, and ownership in one call.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from edgar.ai.mcp.tools.base import (
    tool,
    success,
    error,
    resolve_company,
    format_company_profile,
    format_filing_summary,
    get_error_suggestions,
    truncate_text,
)

logger = logging.getLogger(__name__)


@tool(
    name="edgar_company",
    description="""Get company information and analysis. Combines profile, financials,
filings, and ownership data in one call. Use 'include' to control what data is returned.

Examples:
- Basic info: identifier="AAPL"
- Full analysis: identifier="AAPL", include=["profile", "financials", "filings", "ownership"]
- Just financials: identifier="MSFT", include=["financials"], periods=8""",
    params={
        "identifier": {
            "type": "string",
            "description": "Company ticker (AAPL), CIK (320193), or name (Apple Inc)"
        },
        "include": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": ["profile", "financials", "filings", "ownership"]
            },
            "description": "Data to include. Default: profile, financials, filings",
            "default": ["profile", "financials", "filings"]
        },
        "periods": {
            "type": "integer",
            "description": "Number of financial periods (default 4)",
            "default": 4
        },
        "annual": {
            "type": "boolean",
            "description": "Annual (true) or quarterly (false) financials",
            "default": True
        }
    },
    required=["identifier"]
)
async def edgar_company(
    identifier: str,
    include: Optional[list[str]] = None,
    periods: int = 4,
    annual: bool = True
) -> Any:
    """
    Get comprehensive company intelligence.

    Combines multiple data sources into a single response to minimize
    round trips while allowing control over what's included.
    """
    include = include or ["profile", "financials", "filings"]

    try:
        company = resolve_company(identifier)

        result = {
            "company": company.name,
            "cik": str(company.cik),
        }

        # Profile - basic company info
        if "profile" in include:
            result["profile"] = _build_profile(company)

        # Financials - income, balance, cash flow
        if "financials" in include:
            result["financials"] = _build_financials(company, periods, annual)

        # Recent filings
        if "filings" in include:
            result["recent_filings"] = _build_filings(company)

        # Ownership - insiders and institutions
        if "ownership" in include:
            result["ownership"] = _build_ownership(company)

        # Determine next steps based on what was included
        next_steps = []
        if "financials" not in include:
            next_steps.append("Add 'financials' to include for financial statements")
        if "ownership" not in include:
            next_steps.append("Add 'ownership' to include for insider/institutional data")
        next_steps.append("Use edgar_compare to compare with peer companies")
        next_steps.append("Use edgar_filing to read specific SEC filing content")

        return success(result, next_steps=next_steps)

    except ValueError as e:
        return error(str(e), suggestions=get_error_suggestions(e))
    except Exception as e:
        logger.exception(f"Error in edgar_company for {identifier}")
        return error(str(e), suggestions=get_error_suggestions(e))


def _build_profile(company) -> dict:
    """Build company profile section."""
    profile = format_company_profile(company)

    # Add additional details if available
    if hasattr(company, 'entity_type'):
        profile["entity_type"] = company.entity_type

    if hasattr(company, 'category'):
        profile["category"] = company.category

    return profile


def _build_financials(company, periods: int, annual: bool) -> dict:
    """Build financials section with all three statements."""
    financials = {
        "periods": periods,
        "period_type": "annual" if annual else "quarterly"
    }
    facts = company.get_facts()

    # Income Statement
    try:
        income = facts.income_statement(periods=periods, annual=annual)
        if hasattr(income, 'to_llm_string'):
            financials["income_statement"] = income.to_llm_string()
        elif hasattr(income, 'to_dict'):
            financials["income_statement"] = income.to_dict()
        else:
            financials["income_statement"] = str(income)
    except Exception as e:
        logger.debug(f"Could not get income statement: {e}")
        financials["income_statement"] = {"error": str(e)}

    # Balance Sheet
    try:
        balance = facts.balance_sheet(periods=periods, annual=annual)
        if hasattr(balance, 'to_llm_string'):
            financials["balance_sheet"] = balance.to_llm_string()
        elif hasattr(balance, 'to_dict'):
            financials["balance_sheet"] = balance.to_dict()
        else:
            financials["balance_sheet"] = str(balance)
    except Exception as e:
        logger.debug(f"Could not get balance sheet: {e}")
        financials["balance_sheet"] = {"error": str(e)}

    # Cash Flow
    try:
        cash_flow = facts.cash_flow(periods=periods, annual=annual)
        if hasattr(cash_flow, 'to_llm_string'):
            financials["cash_flow"] = cash_flow.to_llm_string()
        elif hasattr(cash_flow, 'to_dict'):
            financials["cash_flow"] = cash_flow.to_dict()
        else:
            financials["cash_flow"] = str(cash_flow)
    except Exception as e:
        logger.debug(f"Could not get cash flow: {e}")
        financials["cash_flow"] = {"error": str(e)}

    return financials


def _build_filings(company, limit: int = 10) -> list[dict]:
    """Build recent filings section."""
    try:
        filings = company.get_filings().head(limit)
        return [format_filing_summary(f) for f in filings]
    except Exception as e:
        logger.debug(f"Could not get filings: {e}")
        return [{"error": str(e)}]


def _build_ownership(company) -> dict:
    """Build ownership section with insider and institutional data."""
    ownership = {}

    # Insider transactions (Form 4)
    try:
        form4_filings = company.get_filings(form="4").head(20)
        insider_txns = []

        for filing in form4_filings[:10]:
            try:
                txn = {
                    "date": str(filing.filing_date),
                    "accession": filing.accession_number,
                }
                # Try to get more details from the filing object
                try:
                    obj = filing.obj()
                    if hasattr(obj, 'reporting_owner'):
                        txn["insider"] = str(obj.reporting_owner)
                    if hasattr(obj, 'transactions'):
                        txn["transaction_count"] = len(obj.transactions)
                except Exception as e:
                    logger.debug(f"Could not parse Form 4 details: {e}")
                insider_txns.append(txn)
            except Exception as e:
                logger.debug(f"Could not parse Form 4: {e}")
                continue

        ownership["insider_transactions"] = insider_txns
        ownership["insider_filing_count"] = len(form4_filings)

    except Exception as e:
        logger.debug(f"Could not get insider data: {e}")
        ownership["insider_transactions"] = {"error": str(e)}

    # Institutional holders summary
    # Note: Full 13F analysis is complex - provide summary here
    ownership["institutional_note"] = (
        "Use edgar_ownership with analysis_type='institutions' for detailed institutional holder data"
    )

    return ownership
