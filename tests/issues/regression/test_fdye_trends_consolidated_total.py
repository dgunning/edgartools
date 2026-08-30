"""edgar_trends reported the ASC-606 slice while get_revenue() reported the total.

Follow-up to the `edgartools-fdye` fix in the standardized concept getters.
`edgar_trends` does its own concept selection, so it did not inherit that fix,
and the two surfaces disagreed about the same company and year:

    MET trends: 2025=2,436,000,000     (the ASC-606 slice)
    MET getter: 2025=77,084,000,000    (consolidated Revenues)

MetLife tags both for FY2025, and the variant list ranks the contract tag first.
The list orders *names*; it cannot tell that one name measures a part of what
another measures.

The fix reuses `is_consolidated_total_over` rather than adding a third copy of
the threshold — two copies drifting apart is what the bead objected to.
"""
import asyncio

import pytest


def _revenue(ticker, periods=2):
    from edgar.ai.mcp.tools.trends import edgar_trends

    result = asyncio.run(edgar_trends(ticker, concepts=["revenue"], periods=periods))
    data = result.data if hasattr(result, "data") else result
    trend = data["trends"]["revenue"]
    assert "error" not in trend, trend
    return {entry["period"]: entry["value"] for entry in trend["values"]}


# --- Offline ----------------------------------------------------------------

def test_a_dwarfing_same_period_row_replaces_the_ranked_pick():
    import pandas as pd

    from edgar.ai.mcp.tools.trends import _prefer_consolidated_totals

    all_rows = pd.DataFrame([
        {"period_end": "2025-12-31", "numeric_value": 2_436_000_000},   # slice
        {"period_end": "2025-12-31", "numeric_value": 77_084_000_000},  # total
    ])
    chosen = all_rows.head(1)

    assert list(_prefer_consolidated_totals(all_rows, chosen)['numeric_value']) == [
        77_084_000_000
    ]


def test_a_near_equal_row_does_not_replace_it():
    """Two names for one figure sit close together and must not fight."""
    import pandas as pd

    from edgar.ai.mcp.tools.trends import _prefer_consolidated_totals

    all_rows = pd.DataFrame([
        {"period_end": "2025-12-31", "numeric_value": 100},
        {"period_end": "2025-12-31", "numeric_value": 150},
    ])
    chosen = all_rows.head(1)

    assert list(_prefer_consolidated_totals(all_rows, chosen)['numeric_value']) == [100]


def test_it_never_crosses_periods():
    import pandas as pd

    from edgar.ai.mcp.tools.trends import _prefer_consolidated_totals

    all_rows = pd.DataFrame([
        {"period_end": "2026-05-31", "numeric_value": 18_424_600_000},
        {"period_end": "2024-05-26", "numeric_value": 90_000_000_000},
    ])
    chosen = all_rows.head(1)

    assert list(_prefer_consolidated_totals(all_rows, chosen)['numeric_value']) == [
        18_424_600_000
    ]


def test_only_revenue_opts_in():
    """Net income's variants are not slices of one another."""
    from edgar.ai.mcp.tools.trends import _CONSOLIDATED_TOTAL_CONCEPTS

    assert _CONSOLIDATED_TOTAL_CONCEPTS == frozenset({"revenue"})


# --- Network ----------------------------------------------------------------

@pytest.mark.network
@pytest.mark.regression
def test_the_trend_agrees_with_the_getter_for_an_insurer():
    from edgar import Company

    assert _revenue("MET")["2025"] == Company("MET").get_facts().get_revenue()
    assert _revenue("MET")["2025"] == 77_084_000_000


@pytest.mark.network
@pytest.mark.regression
@pytest.mark.parametrize("ticker,year,expected", [
    ("GIS",  "2026", 18_424_600_000),   # control: lower-ranked concept, newer period
    ("NVDA", "2026", 215_938_000_000),
    ("AAPL", "2025", 416_161_000_000),
])
def test_the_cross_check_leaves_correct_series_alone(ticker, year, expected):
    assert _revenue(ticker)[year] == expected
