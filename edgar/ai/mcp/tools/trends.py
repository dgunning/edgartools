"""
Trends Tool

Financial time series with growth rates. No other SEC MCP server does this
with XBRL-sourced data.
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

# Map user-friendly concept names to XBRL concept identifiers
CONCEPT_MAP = {
    "revenue": "Revenue",
    "net_income": "NetIncomeLoss",
    "total_assets": "Assets",
    "total_liabilities": "Liabilities",
    "equity": "StockholdersEquity",
    "gross_profit": "GrossProfit",
    "operating_income": "OperatingIncomeLoss",
    "eps": "EarningsPerShareBasic",
}


@tool(
    name="edgar_trends",
    description="""Get financial trends over time for a company. Returns XBRL-sourced
time series data with growth rates — answers 'How has revenue grown over N years?'

Examples:
- Revenue trend: identifier="AAPL", concepts=["revenue"]
- Multi-metric: identifier="MSFT", concepts=["revenue", "net_income", "eps"], periods=10
- Quarterly: identifier="TSLA", period="quarterly", periods=8""",
    params={
        "identifier": {
            "type": "string",
            "description": "Company ticker (AAPL), CIK (320193), or name"
        },
        "concepts": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": list(CONCEPT_MAP.keys()),
            },
            "description": "Financial concepts to track (default: revenue, net_income)",
            "default": ["revenue", "net_income"]
        },
        "periods": {
            "type": "integer",
            "description": "Number of periods to retrieve (default 8)",
            "default": 8
        },
        "period": {
            "type": "string",
            "enum": ["annual", "quarterly"],
            "description": "Period type (default: annual)",
            "default": "annual"
        },
        "include_growth": {
            "type": "boolean",
            "description": "Calculate YoY/QoQ growth rates (default true)",
            "default": True
        }
    },
    required=["identifier"]
)
async def edgar_trends(
    identifier: str,
    concepts: Optional[list[str]] = None,
    periods: int = 8,
    period: str = "annual",
    include_growth: bool = True,
) -> Any:
    """Get financial time series with growth rates."""
    concepts = concepts or ["revenue", "net_income"]

    try:
        company = resolve_company(identifier)
        facts = company.get_facts()

        trends = {}

        for concept_name in concepts:
            xbrl_concept = CONCEPT_MAP.get(concept_name)
            if not xbrl_concept:
                continue

            try:
                ts = facts.time_series(xbrl_concept, periods=periods * 3)

                if ts is None or ts.empty:
                    trends[concept_name] = {"error": "No data available"}
                    continue

                # Filter by period type
                if period == "annual":
                    filtered = ts[ts['fiscal_period'] == 'FY']
                else:
                    filtered = ts[ts['fiscal_period'].isin(['Q1', 'Q2', 'Q3', 'Q4'])]

                # When multiple values exist per period_end (e.g., segment vs total),
                # keep the largest value which is typically the consolidated total
                if not filtered.empty:
                    filtered = (filtered
                                .sort_values('numeric_value', ascending=False)
                                .drop_duplicates(subset=['period_end'], keep='first')
                                .sort_values('period_end', ascending=False))

                # Limit to requested periods
                filtered = filtered.head(periods)

                if filtered.empty:
                    trends[concept_name] = {"error": f"No {period} data available"}
                    continue

                # Build values list
                values = []
                for _, row in filtered.iterrows():
                    entry = {
                        "value": row['numeric_value'],
                    }
                    period_end = row['period_end']
                    if period == "annual":
                        entry["period"] = str(period_end.year) if hasattr(period_end, 'year') else str(period_end)
                    else:
                        entry["period"] = f"{period_end.year}-{row['fiscal_period']}" if hasattr(period_end, 'year') else str(period_end)
                    values.append(entry)

                trend_data = {"values": values}

                # Compute growth rates
                if include_growth and len(values) >= 2:
                    growth_rates = []
                    for i in range(len(values) - 1):
                        current_val = values[i]["value"]
                        previous_val = values[i + 1]["value"]
                        if current_val is not None and previous_val is not None and previous_val != 0:
                            rate = (current_val - previous_val) / abs(previous_val) * 100
                            growth_rates.append({
                                "period": values[i]["period"],
                                "growth": f"{rate:.1f}%",
                            })
                        else:
                            growth_rates.append({
                                "period": values[i]["period"],
                                "growth": None,
                            })
                    trend_data["growth_rates"] = growth_rates

                    # CAGR if we have enough annual data
                    if period == "annual" and len(values) >= 3:
                        first_val = values[-1]["value"]
                        last_val = values[0]["value"]
                        n_years = len(values) - 1
                        if first_val and last_val and first_val > 0 and last_val > 0:
                            cagr = (last_val / first_val) ** (1 / n_years) - 1
                            trend_data["cagr"] = f"{cagr * 100:.1f}%"
                            trend_data["cagr_years"] = n_years

                trends[concept_name] = trend_data

            except Exception as e:
                logger.debug(f"Could not get time series for {concept_name}: {e}")
                trends[concept_name] = {"error": str(e)}

        result = {
            "company": company.name,
            "cik": str(company.cik),
            "period_type": period,
            "trends": trends,
        }

        next_steps = [
            "Use edgar_compare to compare these trends with peer companies",
            "Use edgar_filing to read the company's latest 10-K for context",
        ]

        return success(result, next_steps=next_steps)

    except ValueError as e:
        return error(str(e), suggestions=get_error_suggestions(e))
    except Exception as e:
        logger.exception(f"Error in edgar_trends for {identifier}")
        return error(str(e), suggestions=get_error_suggestions(e))
