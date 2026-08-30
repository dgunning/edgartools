"""Regression test for GitHub Issue #1138.

`edgar_trends(concepts=["revenue"])` did not return revenue. What it returned
depended on `periods`, and it was wrong for some companies at every value.

Two defects composed:

1. `EntityFacts.time_series` passes `exact=":" in concept` to
   `FactQuery.by_concept`. No value in CONCEPT_MAP contained a colon, so every
   lookup took the substring branch and matched every concept *containing* the
   name: "Revenue" matched CostOfRevenue, DeferredRevenue and 12 others for
   NVIDIA. "Assets" and "Liabilities" were worse.

2. `time_series` sorted by filing_date and truncated to `periods * 3` rows
   BEFORE the tool filtered to `fiscal_period == 'FY'`. The correct annual fact
   could be cut from the window entirely, and the value-descending dedup then
   picked the largest surviving wrong concept.

Together they made the answer depend on filing cadence rather than on anything
the caller asked for: NVIDIA's `periods=8` result was correct when the issue was
filed and became cost of revenue after a 10-Q landed on 2026-08-26.

Ground truth is each company's own income statement:
  NVDA FY2026 215,938,000,000   FY2025 130,497,000,000   FY2024 60,922,000,000
  AAPL FY2025 416,161,000,000   FY2024 391,035,000,000   FY2023 383,285,000,000

GitHub Issue: https://github.com/dgunning/edgartools/issues/1138
"""
import asyncio

import pytest

from edgar.ai.mcp.tools.trends import CONCEPT_MAP


def _trend_values(result, concept="revenue"):
    data = result.data if hasattr(result, "data") else result
    trend = data["trends"][concept]
    assert "error" not in trend, trend
    return {entry["period"]: entry["value"] for entry in trend["values"]}


# --- Offline: the property that made the substring collision possible --------

def test_every_mapped_concept_is_qualified():
    """A colon is what selects exact matching, so it is the whole fix for (1).

    Asserted on the map rather than on a result because an unqualified name
    fails silently — it returns a plausible number from a different concept.
    """
    for name, variants in CONCEPT_MAP.items():
        assert isinstance(variants, tuple), f"{name} must list its variants"
        assert variants, f"{name} has no concepts"
        for concept in variants:
            assert ":" in concept, (
                f"{name} -> {concept!r} has no taxonomy prefix, so "
                "FactQuery.by_concept would match every concept containing it"
            )


def test_revenue_lists_the_migrating_tags():
    """Companies move between these, so a single name yields a broken series."""
    assert "us-gaap:Revenues" in CONCEPT_MAP["revenue"]
    assert ("us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
            in CONCEPT_MAP["revenue"])


# --- Network: the reported symptom ------------------------------------------

@pytest.mark.network
@pytest.mark.regression
@pytest.mark.parametrize("periods", [3, 4, 5, 8])
def test_revenue_does_not_change_with_the_number_of_periods(periods):
    """`periods` asks for a window length, not for a different concept."""
    from edgar.ai.mcp.tools.trends import edgar_trends

    values = _trend_values(asyncio.run(
        edgar_trends("NVDA", concepts=["revenue"], periods=periods)))

    assert values["2026"] == 215_938_000_000
    assert len(values) == periods


@pytest.mark.network
@pytest.mark.regression
def test_the_series_is_revenue_rather_than_a_concept_containing_the_word():
    """Apple read as revenue falling from $383B to $7.7B."""
    from edgar.ai.mcp.tools.trends import edgar_trends

    values = _trend_values(asyncio.run(
        edgar_trends("AAPL", concepts=["revenue"], periods=3)))

    assert values["2025"] == 416_161_000_000
    assert values["2024"] == 391_035_000_000
    assert values["2023"] == 383_285_000_000


@pytest.mark.network
@pytest.mark.regression
def test_a_tag_migration_does_not_leave_a_hole_in_the_series():
    """NVIDIA changed tags mid-series; both sides must appear."""
    from edgar.ai.mcp.tools.trends import edgar_trends

    values = _trend_values(asyncio.run(
        edgar_trends("NVDA", concepts=["revenue"], periods=5)))

    assert values["2026"] == 215_938_000_000   # tagged Revenues
    assert values["2024"] == 60_922_000_000    # tagged contract revenue
    assert all(v is not None for v in values.values())


@pytest.mark.network
@pytest.mark.regression
def test_the_broad_substrings_return_their_own_concept():
    """`Assets`/`Liabilities` collided with every Current/Other/Intangible variant."""
    from edgar.ai.mcp.tools.trends import edgar_trends

    result = asyncio.run(edgar_trends(
        "AAPL", concepts=["total_assets", "total_liabilities"], periods=1))

    assert _trend_values(result, "total_assets")["2025"] == 359_241_000_000
    assert _trend_values(result, "total_liabilities")["2025"] == 285_508_000_000


# --- A quarter must not appear in an annual series ---------------------------

def test_the_period_type_filter_uses_the_reporting_window():
    """`fiscal_period` does not separate annual facts from quarterly ones.

    Companyfacts labels quarterly facts `FY` too: General Mills' 90-day Q3 and
    its 370-day fiscal year are both `fiscal_period == 'FY'` with
    `fiscal_year == 2026`. Filtering on that alone let a quarter into the annual
    series under the same year label as the real annual figure.

    Instants have no duration -- a balance-sheet concept is a point in time --
    and must survive the filter in either mode.
    """
    import pandas as pd

    from edgar.ai.mcp.tools.trends import _of_period_type

    rows = pd.DataFrame([
        {"fiscal_period": "FY", "duration_days": 370, "numeric_value": 18_424_600_000},
        {"fiscal_period": "FY", "duration_days": 90, "numeric_value": 4_436_700_000},
        {"fiscal_period": "FY", "duration_days": None, "numeric_value": 30_000_000_000},
    ])

    annual = _of_period_type(rows, "annual")
    assert list(annual['numeric_value']) == [18_424_600_000, 30_000_000_000]

    quarterly = _of_period_type(rows, "quarterly")
    assert list(quarterly['numeric_value']) == [4_436_700_000, 30_000_000_000]


@pytest.mark.network
@pytest.mark.regression
def test_an_annual_series_has_one_row_per_year():
    """GIS returned two rows both labelled 2026, one of them a quarter."""
    from edgar.ai.mcp.tools.trends import edgar_trends

    values = _trend_values(asyncio.run(
        edgar_trends("GIS", concepts=["revenue"], periods=3)))

    assert len(values) == 3
    assert set(values) == {"2026", "2025", "2024"}
    assert values["2026"] == 18_424_600_000
