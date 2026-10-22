"""
Regression tests for Issue #1778: EarningsRelease.get_key_metrics() returned a
revenue component ("New and used equipment sales") instead of total revenues.

The revenue loop took the first row whose label contained 'sales' or 'revenue'.
Total rows are now preferred over aggregate labels, which are preferred over
component rows.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1778
"""

import pandas as pd
import pytest

from edgar import find
from edgar.earnings import (
    EarningsRelease,
    FinancialTable,
    Scale,
    StatementType,
    _classify_row_type,
    _revenue_label_rank,
)


def _earnings_with(labels, values):
    df = pd.DataFrame({"Three Months Ended June 30, 2025": values}, index=labels).astype(object)
    table = FinancialTable(
        dataframe=df,
        scale=Scale.MILLIONS,
        statement_type=StatementType.INCOME_STATEMENT,
        row_types={label: _classify_row_type(label) for label in labels},
        periods=list(df.columns),
    )
    release = EarningsRelease.__new__(EarningsRelease)
    release._tables = [table]
    return release


@pytest.mark.regression
class TestIssue1778TotalRevenue:
    def test_total_row_beats_leading_component(self):
        release = _earnings_with(
            ["New and used equipment sales", "Parts sales", "Service revenues", "Total revenues",
             "Net loss"],
            [265.6, 75.6, 64.9, 481.2, -6.1],
        )
        assert release.get_key_metrics()["revenue"] == pytest.approx(481_200_000)

    def test_total_cost_of_revenues_is_not_revenue(self):
        assert _revenue_label_rank("total cost of revenues") == 2
        assert _revenue_label_rank("net sales") == 1
        assert _revenue_label_rank("total net revenues") == 0
        assert _revenue_label_rank("operating income") == 3

    def test_aggregate_label_beats_component(self):
        release = _earnings_with(["Product sales", "Net sales"], [40.0, 100.0])
        assert release.get_key_metrics()["revenue"] == pytest.approx(100_000_000)

    def test_first_loose_match_still_used_without_total(self):
        release = _earnings_with(["Subscription revenue", "Services revenue"], [7.0, 3.0])
        assert release.get_key_metrics()["revenue"] == pytest.approx(7_000_000)

    @pytest.mark.network
    @pytest.mark.vcr
    def test_alta_equipment_q2_2025_total_revenues(self):
        # Alta Equipment Group 8-K EX-99.1, accession 0000950170-25-105056: Total revenues 481.2 (millions)
        earnings = find("0000950170-25-105056").obj().earnings
        assert earnings.get_key_metrics()["revenue"] == pytest.approx(481_200_000)

    @pytest.mark.network
    @pytest.mark.vcr
    def test_caterpillar_total_sales_and_revenues(self):
        # Caterpillar 8-K, accession 0000018230-26-000040: Total sales and revenues 20,543 (millions)
        earnings = find("0000018230-26-000040").obj().earnings
        assert earnings.get_key_metrics()["revenue"] == pytest.approx(20_543_000_000)
