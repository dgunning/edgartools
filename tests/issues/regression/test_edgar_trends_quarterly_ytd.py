"""Regression: edgar_trends(period="quarterly") replaced quarterly revenue with 6M/9M YTD totals.

GitHub PR: https://github.com/dgunning/edgartools/pull/1168

PR #1168 added `_prefer_consolidated_totals` so an insurer's small ASC-606
contract-revenue slice would yield to consolidated `Revenues` for the same
period. However, `edgar_trends` passed the *unfiltered* time-series frame `ts`
(which still holds 6-month, 9-month YTD, and 12-month FY rows on the same
`period_end`) instead of the period-type-filtered rows.

Because `_CONSOLIDATED_TOTAL_FACTOR = 2.0`, 9M YTD (~3x a single quarter) and
6M YTD (>= 2x a single quarter) silently overwrote discrete 3-month quarterly
revenue on every company that files YTD figures:

    AAPL Q3 FY2026 (0000320193-26-000020): reported $364.357B (9M YTD) vs $109.417B (3M)
    AAPL Q2 FY2026 (0000320193-26-000013): reported $254.940B (6M YTD) vs $111.184B (3M)
    TSLA Q3 2026   (0001628280-26-066775): reported $78.669B  (9M YTD) vs $28.046B  (3M)
    MET  Q3 2026   (0001099219-26-000062): reported $58.750B  (9M YTD) vs $20.522B  (3M consolidated)

Passing the period-filtered frame to `_prefer_consolidated_totals` preserves the
same-window consolidated-over-slice upgrade (MetLife Q3 upgrades $728M -> $20.522B)
while preventing YTD/annual rows from bleeding into quarterly series.
"""

import asyncio
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
import pytest


def _make_fake_company(name: str, cik: str, series_by_concept: dict[str, pd.DataFrame]):
    class _FakeFacts:
        def time_series(self, concept: str, periods: int = 500):
            return series_by_concept.get(concept)

    return SimpleNamespace(name=name, cik=cik, get_facts=lambda: _FakeFacts())


def _trend_values(result, concept: str = "revenue") -> dict[str, float]:
    data = result.data if hasattr(result, "data") else result
    trend = data["trends"][concept]
    assert "error" not in trend, trend
    return {entry["period"]: entry["value"] for entry in trend["values"]}


# --- Offline end-to-end regression tests ------------------------------------


def test_quarterly_revenue_ignores_ytd_and_annual_rows_on_same_period_end():
    """6M/9M YTD rows sharing a period_end must never overwrite 3M quarterly revenue."""
    from edgar.ai.mcp.tools.trends import edgar_trends

    aapl_contract_rev = pd.DataFrame([
        # Q3 FY26: 3M discrete ($109.417B) alongside 9M YTD ($364.357B) on 2026-06-27
        {"fiscal_period": "Q3", "period_end": date(2026, 6, 27), "duration_days": 90, "numeric_value": 109_417_000_000.0},
        {"fiscal_period": "Q3", "period_end": date(2026, 6, 27), "duration_days": 272, "numeric_value": 364_357_000_000.0},
        # Q2 FY26: 3M discrete ($111.184B) alongside 6M YTD ($254.940B) on 2026-03-28
        {"fiscal_period": "Q2", "period_end": date(2026, 3, 28), "duration_days": 90, "numeric_value": 111_184_000_000.0},
        {"fiscal_period": "Q2", "period_end": date(2026, 3, 28), "duration_days": 181, "numeric_value": 254_940_000_000.0},
        # Q1 FY26: 3M discrete ($143.756B)
        {"fiscal_period": "Q1", "period_end": date(2025, 12, 27), "duration_days": 90, "numeric_value": 143_756_000_000.0},
    ])
    fake = _make_fake_company(
        "Apple Inc.",
        "320193",
        {"us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax": aapl_contract_rev},
    )

    with patch("edgar.ai.mcp.tools.trends.resolve_company", return_value=fake):
        result = asyncio.run(edgar_trends("AAPL", concepts=["revenue"], period="quarterly", periods=3))

    values = _trend_values(result)
    assert values == {
        "2026-Q3": 109_417_000_000.0,
        "2026-Q2": 111_184_000_000.0,
        "2025-Q1": 143_756_000_000.0,
    }


def test_quarterly_insurer_upgrades_slice_to_3m_total_without_jumping_to_ytd():
    """MetLife Q3 must upgrade its 91d ASC-606 slice ($728M) to 91d Revenues ($20.522B), not 9M YTD ($58.75B)."""
    from edgar.ai.mcp.tools.trends import edgar_trends

    asc606_slice = pd.DataFrame([
        {"fiscal_period": "Q3", "period_end": date(2026, 9, 30), "duration_days": 91, "numeric_value": 728_000_000.0},
        {"fiscal_period": "Q3", "period_end": date(2026, 9, 30), "duration_days": 272, "numeric_value": 2_186_000_000.0},
        {"fiscal_period": "Q2", "period_end": date(2026, 6, 30), "duration_days": 90, "numeric_value": 724_000_000.0},
        {"fiscal_period": "Q2", "period_end": date(2026, 6, 30), "duration_days": 180, "numeric_value": 1_458_000_000.0},
    ])
    consolidated = pd.DataFrame([
        {"fiscal_period": "Q3", "period_end": date(2026, 9, 30), "duration_days": 91, "numeric_value": 20_522_000_000.0},
        {"fiscal_period": "Q3", "period_end": date(2026, 9, 30), "duration_days": 272, "numeric_value": 58_750_000_000.0},
        {"fiscal_period": "Q2", "period_end": date(2026, 6, 30), "duration_days": 90, "numeric_value": 19_154_000_000.0},
        {"fiscal_period": "Q2", "period_end": date(2026, 6, 30), "duration_days": 180, "numeric_value": 38_228_000_000.0},
    ])
    fake = _make_fake_company(
        "METLIFE INC",
        "1099219",
        {
            "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax": asc606_slice,
            "us-gaap:Revenues": consolidated,
        },
    )

    with patch("edgar.ai.mcp.tools.trends.resolve_company", return_value=fake):
        result = asyncio.run(edgar_trends("MET", concepts=["revenue"], period="quarterly", periods=2))

    values = _trend_values(result)
    assert values == {
        "2026-Q3": 20_522_000_000.0,
        "2026-Q2": 19_154_000_000.0,
    }


def test_annual_insurer_still_upgrades_slice_to_fy_total():
    """Annual mode continues to prefer same-year consolidated Revenues over ASC-606 slice."""
    from edgar.ai.mcp.tools.trends import edgar_trends

    asc606_slice = pd.DataFrame([
        {"fiscal_period": "FY", "period_end": date(2025, 12, 31), "duration_days": 364, "numeric_value": 2_436_000_000.0},
    ])
    consolidated = pd.DataFrame([
        {"fiscal_period": "FY", "period_end": date(2025, 12, 31), "duration_days": 364, "numeric_value": 77_084_000_000.0},
        # A stray multi-year row should not leak into annual either
        {"fiscal_period": "FY", "period_end": date(2025, 12, 31), "duration_days": 730, "numeric_value": 200_000_000_000.0},
    ])
    fake = _make_fake_company(
        "METLIFE INC",
        "1099219",
        {
            "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax": asc606_slice,
            "us-gaap:Revenues": consolidated,
        },
    )

    with patch("edgar.ai.mcp.tools.trends.resolve_company", return_value=fake):
        result = asyncio.run(edgar_trends("MET", concepts=["revenue"], period="annual", periods=1))

    assert _trend_values(result) == {"2025": 77_084_000_000.0}


# --- Network regression against verified SEC 10-Q filings -------------------


@pytest.mark.network
@pytest.mark.regression
@pytest.mark.parametrize("ticker,period_key,expected", [
    # Apple Q3 FY2026 10-Q (0000320193-26-000020): 3M $109.417B vs 9M YTD $364.357B
    ("AAPL", "2026-Q3", 109_417_000_000),
    # Apple Q2 FY2026 10-Q (0000320193-26-000013): 3M $111.184B vs 6M YTD $254.940B
    ("AAPL", "2026-Q2", 111_184_000_000),
    # Tesla Q3 2026 10-Q (0001628280-26-066775): 3M $28.046B vs 9M YTD $78.669B
    ("TSLA", "2026-Q3", 28_046_000_000),
    # MetLife Q3 2026 10-Q (0001099219-26-000062): 3M consolidated $20.522B (vs $728M slice & $58.75B 9M YTD)
    ("MET", "2026-Q3", 20_522_000_000),
])
def test_quarterly_revenue_matches_discrete_10q_filings(ticker, period_key, expected):
    from edgar.ai.mcp.tools.trends import edgar_trends

    result = asyncio.run(
        edgar_trends(ticker, concepts=["revenue"], period="quarterly", periods=6)
    )
    values = _trend_values(result)
    assert values[period_key] == expected
