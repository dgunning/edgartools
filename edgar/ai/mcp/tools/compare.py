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

# Mapping from metric names to the statement type that provides them
METRIC_STATEMENT_MAP = {
    "revenue": "income",
    "net_income": "income",
    "gross_profit": "income",
    "operating_income": "income",
    "assets": "balance",
    "liabilities": "balance",
    "equity": "balance",
    "margins": "income",
    "growth": "income",
}

# Mapping from metric names to EntityFacts getter methods
METRIC_GETTERS = {
    "revenue": "get_revenue",
    "net_income": "get_net_income",
    "gross_profit": "get_gross_profit",
    "operating_income": "get_operating_income",
    "assets": "get_total_assets",
    "liabilities": "get_total_liabilities",
    "equity": "get_shareholders_equity",
}

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
                         "assets", "liabilities", "equity", "margins", "growth"]
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
    """Get comparison data for a single company, extracting requested metrics."""
    try:
        company = resolve_company(identifier)

        result = {
            "identifier": identifier,
            "name": company.name,
            "cik": str(company.cik),
        }

        try:
            facts = company.get_facts()
        except Exception as e:
            result["financials_error"] = str(e)
            return result

        extracted = {}
        # Track raw values for derived metric computation
        _revenue_val = None
        _net_income_val = None
        _gross_profit_val = None

        for metric in metrics:
            if metric in ("margins", "growth"):
                continue  # Derived metrics handled below

            getter_name = METRIC_GETTERS.get(metric)
            if not getter_name:
                continue

            try:
                getter = getattr(facts, getter_name, None)
                if getter:
                    value = getter(annual=annual)
                    if value is not None:
                        extracted[metric] = value
                        # Cache for derived metrics
                        if metric == "revenue":
                            _revenue_val = value
                        elif metric == "net_income":
                            _net_income_val = value
                        elif metric == "gross_profit":
                            _gross_profit_val = value
            except Exception as e:
                logger.debug(f"Could not get {metric} for {identifier}: {e}")

        # Compute margins if requested
        if "margins" in metrics:
            # Fetch revenue/net_income/gross_profit if not already fetched
            if _revenue_val is None:
                try:
                    _revenue_val = facts.get_revenue(annual=annual)
                except Exception:
                    pass
            if _net_income_val is None:
                try:
                    _net_income_val = facts.get_net_income(annual=annual)
                except Exception:
                    pass
            if _gross_profit_val is None:
                try:
                    _gross_profit_val = facts.get_gross_profit(annual=annual)
                except Exception:
                    pass

            if _revenue_val and _revenue_val != 0:
                if _net_income_val is not None:
                    extracted["net_margin"] = f"{_net_income_val / _revenue_val * 100:.1f}%"
                if _gross_profit_val is not None:
                    extracted["gross_margin"] = f"{_gross_profit_val / _revenue_val * 100:.1f}%"

        # Compute revenue growth if requested (uses time_series for YoY)
        if "growth" in metrics:
            try:
                ts = facts.time_series("Revenue", periods=periods + 1)
                if ts is not None and not ts.empty:
                    # Filter to annual periods only
                    annual_ts = ts[ts['fiscal_period'] == 'FY'] if annual else ts
                    if len(annual_ts) >= 2:
                        values = annual_ts['numeric_value'].tolist()
                        if len(values) >= 2 and values[1] and values[1] != 0:
                            extracted["revenue_growth_yoy"] = f"{(values[0] - values[1]) / abs(values[1]) * 100:.1f}%"
            except Exception as e:
                logger.debug(f"Could not compute growth for {identifier}: {e}")

        result["metrics"] = extracted

        # Include statements for context based on which statement types are needed
        needs_income = any(METRIC_STATEMENT_MAP.get(m) == "income" for m in metrics)
        needs_balance = any(METRIC_STATEMENT_MAP.get(m) == "balance" for m in metrics)

        if needs_income:
            try:
                income = facts.income_statement(periods=periods, annual=annual)
                if hasattr(income, 'to_llm_string'):
                    result["income_statement"] = income.to_llm_string()
                else:
                    result["income_statement"] = str(income)
            except Exception as e:
                logger.debug(f"Could not get income statement for {identifier}: {e}")

        if needs_balance:
            try:
                balance = facts.balance_sheet(periods=periods, annual=annual)
                if hasattr(balance, 'to_llm_string'):
                    result["balance_sheet"] = balance.to_llm_string()
                else:
                    result["balance_sheet"] = str(balance)
            except Exception as e:
                logger.debug(f"Could not get balance sheet for {identifier}: {e}")

        return result

    except Exception as e:
        return {"identifier": identifier, "error": str(e)}
