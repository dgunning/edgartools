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

# Map user-friendly concept names to XBRL concepts, in priority order.
#
# Fully qualified on purpose. EntityFacts.time_series passes
# `exact=":" in concept` down to FactQuery.by_concept, so an unqualified name
# takes the substring branch and matches every concept *containing* it:
# "Revenue" pulled in CostOfRevenue, DeferredRevenue and
# ContractWithCustomerLiabilityRevenueRecognized — 14 concepts for NVIDIA — and
# the tool answered with whichever of them survived truncation. "Assets" and
# "Liabilities" were worse, matching AssetsCurrent, OtherAssets*,
# LiabilitiesCurrent and the rest. The colon selects exact matching (GH #1138).
#
# Several concepts have more than one legitimate name and companies migrate
# between them, so each entry lists its variants and the series takes the
# highest-ranked one present in each period.
CONCEPT_MAP = {
    "revenue": (
        "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
        "us-gaap:SalesRevenueNet",
        "us-gaap:Revenues",
    ),
    "net_income": ("us-gaap:NetIncomeLoss", "us-gaap:ProfitLoss"),
    "total_assets": ("us-gaap:Assets",),
    "total_liabilities": ("us-gaap:Liabilities",),
    "equity": (
        "us-gaap:StockholdersEquity",
        "us-gaap:StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ),
    "gross_profit": ("us-gaap:GrossProfit",),
    "operating_income": ("us-gaap:OperatingIncomeLoss",),
    "eps": ("us-gaap:EarningsPerShareBasic", "us-gaap:EarningsPerShareBasicAndDiluted"),
}

# Row cap per concept when pulling facts. The series is cut to the caller's
# `periods` only after the period-type filter, so this bounds pathological
# restatement histories rather than the answer.
_FACT_ROW_CAP = 500



# Reporting windows, in days, that count as a year and as a quarter. Wide
# enough for 52/53-week fiscal calendars and for the short stub a company
# reports when it changes fiscal year end.
_ANNUAL_DAYS = (300, 400)
_QUARTERLY_DAYS = (60, 120)


# Concept families whose variants are alternative names for one consolidated
# total, where a same-period candidate many times larger is that total rather
# than a rival name for it. Not net income: ProfitLoss exceeds NetIncomeLoss by
# the noncontrolling interest, and preferring it would change whose earnings are
# reported.
_CONSOLIDATED_TOTAL_CONCEPTS = frozenset({"revenue"})


def _prefer_consolidated_totals(all_rows, chosen):
    """Replace a ranked pick with the same-period total it is a slice of.

    The variant list orders *names*; it cannot tell that one name measures a
    part of what another measures. Insurers and banks tag ASC-606 contract
    revenue beside a far larger consolidated `Revenues` for the same period, and
    the contract tag ranks first — MetLife's revenue trend read $2.4B against
    the $77.1B its own income statement reports, and disagreed with
    `get_revenue()` for the same company and year.

    Uses the same threshold as the standardized getters
    (`is_consolidated_total_over`) rather than a second copy of the rule, which
    is what let the two surfaces drift apart in the first place.
    """
    from edgar.entity.utils import is_consolidated_total_over

    largest = all_rows.groupby('period_end')['numeric_value'].max()

    def _total_for(row):
        candidate = largest.get(row.period_end)
        if is_consolidated_total_over(candidate, row.numeric_value):
            return candidate
        return row.numeric_value

    chosen = chosen.copy()
    chosen['numeric_value'] = [_total_for(row) for row in chosen.itertuples()]
    return chosen


def _of_period_type(ts, period):
    """Rows whose reporting window matches the period type the caller asked for.

    `fiscal_period` does not answer this. Companyfacts labels quarterly facts
    `FY` as well: General Mills' 90-day Q3 and its 370-day fiscal year are both
    `fiscal_period == 'FY'` with `fiscal_year == 2026`. Filtering on that alone
    let a quarter into an annual series, where it rendered under the same year
    label as the real annual figure — two rows both reading "2026", one of them
    a quarter.

    `duration_days` is the discriminator, and `time_series` returns it for
    exactly this reason. Instants have no duration: a balance-sheet concept like
    Assets is a point in time and belongs in either series, so nulls are kept.
    """
    if period == "annual":
        low, high = _ANNUAL_DAYS
        rows = ts[ts['fiscal_period'] == 'FY']
    else:
        low, high = _QUARTERLY_DAYS
        rows = ts[ts['fiscal_period'].isin(['Q1', 'Q2', 'Q3', 'Q4', 'FY'])]

    duration = rows['duration_days']
    return rows[duration.isna() | duration.between(low, high)]


def _concept_series(facts, xbrl_concepts):
    """Rows for the highest-ranked concept variant available in each period.

    Companies migrate between equally valid tags, so a single concept name
    yields a series with holes — or, worse, one that simply stops. Each variant
    is pulled separately and tagged with its rank; the caller keeps one row per
    period after filtering to the period type it wants.
    """
    import pandas as pd

    frames = []
    for rank, concept in enumerate(xbrl_concepts):
        ts = facts.time_series(concept, periods=_FACT_ROW_CAP)
        if ts is None or ts.empty:
            continue
        ts = ts.copy()
        ts['_concept_rank'] = rank
        frames.append(ts)

    if not frames:
        return None
    return pd.concat(frames, ignore_index=True)


@tool(
    name="edgar_trends",
    description="""Use this for financial trend analysis over time. Returns XBRL-sourced time series with growth rates for revenue, income, EPS, and other metrics across multiple periods.

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
            xbrl_concepts = CONCEPT_MAP.get(concept_name)
            if not xbrl_concepts:
                continue

            try:
                ts = _concept_series(facts, xbrl_concepts)

                if ts is None or ts.empty:
                    trends[concept_name] = {"error": "No data available"}
                    continue

                # Filter by period type BEFORE cutting to `periods`. The old
                # order truncated a mixed pile of annual, quarterly and instant
                # rows first, so the annual fact the caller asked for could be
                # cut away entirely and a different concept answered in its
                # place. It also made the result depend on filing cadence: a new
                # 10-Q pushed the correct annual row out of the window, which is
                # why the same call returned different concepts for different
                # values of `periods` (GH #1138).
                filtered = _of_period_type(ts, period)

                # One row per period: the highest-ranked concept present, then
                # the largest value, which drops segment-level facts reported
                # under the same concept as the consolidated figure.
                if not filtered.empty:
                    filtered = (filtered
                                .sort_values(['period_end', '_concept_rank', 'numeric_value'],
                                             ascending=[False, True, False])
                                .drop_duplicates(subset=['period_end'], keep='first'))

                    if concept_name in _CONSOLIDATED_TOTAL_CONCEPTS:
                        filtered = _prefer_consolidated_totals(ts, filtered)

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
            "Use edgar_read to read the company's latest 10-K sections for context",
        ]

        return success(result, next_steps=next_steps)

    except ValueError as e:
        return error(str(e), suggestions=get_error_suggestions(e))
    except Exception as e:
        logger.exception(f"Error in edgar_trends for {identifier}")
        return error(str(e), suggestions=get_error_suggestions(e))
