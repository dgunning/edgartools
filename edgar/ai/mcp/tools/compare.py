"""
Compare Tool

Side-by-side comparison of multiple companies or industry analysis.
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

# Industry to helper function mapping
INDUSTRY_FUNCTIONS = {
    "pharmaceuticals": "get_pharmaceutical_companies",
    "biotechnology": "get_biotechnology_companies",
    "software": "get_software_companies",
    "semiconductors": "get_semiconductor_companies",
    "banking": "get_banking_companies",
    "investment": "get_investment_companies",
    "insurance": "get_insurance_companies",
    "real_estate": "get_real_estate_companies",
    "oil_gas": "get_oil_gas_companies",
    "retail": "get_retail_companies",
}


@tool(
    name="edgar_compare",
    description="""Compare multiple companies or analyze an industry sector.

Provide specific companies OR select an industry for automatic peer selection.

Examples:
- Compare specific: identifiers=["AAPL", "MSFT", "GOOGL"]
- Industry peers: industry="software", limit=5
- Custom metrics: identifiers=["JPM", "BAC", "WFC"], metrics=["revenue", "net_income", "assets"]""",
    params={
        "identifiers": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Companies to compare (2-10 tickers/CIKs)"
        },
        "industry": {
            "type": "string",
            "enum": list(INDUSTRY_FUNCTIONS.keys()),
            "description": "OR select industry for automatic peer selection"
        },
        "metrics": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": ["revenue", "net_income", "gross_profit", "operating_income",
                         "assets", "liabilities", "equity", "cash", "margins", "growth"]
            },
            "description": "Metrics to compare (default: revenue, net_income)",
            "default": ["revenue", "net_income"]
        },
        "periods": {
            "type": "integer",
            "description": "Number of periods (default 3)",
            "default": 3
        },
        "annual": {
            "type": "boolean",
            "description": "Annual (true) or quarterly (false)",
            "default": True
        },
        "limit": {
            "type": "integer",
            "description": "Max companies for industry comparison (default 5)",
            "default": 5
        }
    },
    required=[]
)
async def edgar_compare(
    identifiers: Optional[list[str]] = None,
    industry: Optional[str] = None,
    metrics: Optional[list[str]] = None,
    periods: int = 3,
    annual: bool = True,
    limit: int = 5
) -> Any:
    """
    Compare companies side-by-side.

    Either compares specific companies or automatically selects
    top companies from an industry sector.
    """
    metrics = metrics or ["revenue", "net_income"]

    try:
        # Determine which companies to compare
        if identifiers:
            companies_to_compare = identifiers[:10]  # Max 10
        elif industry:
            companies_to_compare = await _get_industry_companies(industry, limit)
            if not companies_to_compare:
                return error(
                    f"No companies found for industry: {industry}",
                    suggestions=["Try a different industry", "Provide specific identifiers"]
                )
        else:
            return error(
                "Provide either 'identifiers' or 'industry'",
                suggestions=[
                    "identifiers=['AAPL', 'MSFT'] for specific companies",
                    "industry='software' for automatic peer selection"
                ]
            )

        if len(companies_to_compare) < 2:
            return error(
                "Need at least 2 companies to compare",
                suggestions=["Add more tickers to identifiers"]
            )

        # Compare companies
        comparisons = []
        errors = []

        for ident in companies_to_compare:
            company_data = await _compare_company(ident, metrics, periods, annual)
            if "error" in company_data:
                errors.append({"identifier": ident, "error": company_data["error"]})
            else:
                comparisons.append(company_data)

        result = {
            "comparison": {
                "companies_count": len(comparisons),
                "metrics": metrics,
                "periods": periods,
                "period_type": "annual" if annual else "quarterly",
            },
            "companies": comparisons,
        }

        if errors:
            result["errors"] = errors

        if industry:
            result["industry"] = industry

        next_steps = [
            "Use edgar_company for detailed analysis of a specific company",
            "Use edgar_filing to read specific SEC filings"
        ]

        return success(result, next_steps=next_steps)

    except Exception as e:
        logger.exception("Error in edgar_compare")
        return error(str(e), suggestions=get_error_suggestions(e))


async def _get_industry_companies(industry: str, limit: int) -> list[str]:
    """Get top companies from an industry sector."""
    try:
        from edgar.ai import helpers

        function_name = INDUSTRY_FUNCTIONS.get(industry)
        if not function_name:
            return []

        get_companies = getattr(helpers, function_name, None)
        if not get_companies:
            return []

        companies_df = get_companies()

        # Filter to companies with tickers
        if 'ticker' in companies_df.columns:
            public = companies_df[companies_df['ticker'].notna()]
            return public['ticker'].head(limit).tolist()

        return []

    except Exception as e:
        logger.warning(f"Could not get industry companies: {e}")
        return []


async def _compare_company(
    identifier: str,
    metrics: list[str],
    periods: int,
    annual: bool
) -> dict:
    """Get comparison data for a single company."""
    try:
        company = resolve_company(identifier)

        result = {
            "identifier": identifier,
            "name": company.name,
            "cik": str(company.cik),
        }

        # Get financials
        try:
            income = company.income_statement(periods=periods, annual=annual)

            # Extract key metrics
            if hasattr(income, 'to_llm_string'):
                result["income_statement"] = income.to_llm_string()
            else:
                result["income_statement"] = str(income)

        except Exception as e:
            result["financials_error"] = str(e)

        return result

    except Exception as e:
        return {"identifier": identifier, "error": str(e)}
