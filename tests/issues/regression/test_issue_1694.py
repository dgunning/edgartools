"""Regression test for GitHub Issue #1694.

TTM income and cash-flow statements summed every four adjacent quarterized facts
without checking that they were consecutive. When a quarter was missing from the
series, the window reached back a year further, so a ~15-month total was printed
under a TTM column. Snowflake's Q4 2025 TTM realized gain on equity securities
came out as +36,832,000 (four quarters spanning 2023-11-01 to 2025-01-31, two
fiscal fourth quarters and no Q2 FY2025) against the -17,414,000 the FY2025 10-K
reports.

``calculate_ttm`` already flagged such windows with ``has_gaps``;
``calculate_ttm_trend`` now carries the same ``has_gaps`` flag per row, and the
statement builder leaves a gapped window's cell empty.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1694
"""
import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from edgar.entity.models import FinancialFact
from edgar.entity.parser import EntityFactsParser
from edgar.httprequests import download_json
from edgar.ttm.calculator import TTMCalculator

pytestmark = pytest.mark.regression

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "entity" / "snow_facts.json"


@pytest.fixture(scope="module")
def snow_ttm_income():
    facts = EntityFactsParser.parse_company_facts(json.loads(FIXTURE.read_text("utf-8")))
    statement = facts.income_statement(period="ttm", periods=8)
    return {item["concept"].split(":")[-1]: item["values"] for item in statement.items}


def _quarter(value, start, end, fp):
    return FinancialFact(
        concept="us-gaap:Revenues",
        taxonomy="us-gaap",
        label="Revenues",
        value=value,
        numeric_value=float(value),
        unit="USD",
        period_start=start,
        period_end=end,
        period_type="duration",
        fiscal_year=end.year,
        fiscal_period=fp,
        filing_date=end,
        form_type="10-Q",
        accession="0000000000-00-000000",
    )


def test_trend_flags_a_window_that_skips_a_quarter():
    # 2024 Q2 is missing, so the window ending 2024-12-31 reaches back to 2023 Q4.
    quarters = [
        _quarter(100, date(2023, 10, 1), date(2023, 12, 31), "Q4"),
        _quarter(110, date(2024, 1, 1), date(2024, 3, 31), "Q1"),
        _quarter(130, date(2024, 7, 1), date(2024, 9, 30), "Q3"),
        _quarter(140, date(2024, 10, 1), date(2024, 12, 31), "Q4"),
    ]
    trend = TTMCalculator(quarters).calculate_ttm_trend(periods=1)
    assert bool(trend.iloc[0]["has_gaps"]) is True


def test_trend_does_not_flag_consecutive_quarters():
    quarters = [
        _quarter(100, date(2024, 1, 1), date(2024, 3, 31), "Q1"),
        _quarter(110, date(2024, 4, 1), date(2024, 6, 30), "Q2"),
        _quarter(120, date(2024, 7, 1), date(2024, 9, 30), "Q3"),
        _quarter(130, date(2024, 10, 1), date(2024, 12, 31), "Q4"),
    ]
    trend = TTMCalculator(quarters).calculate_ttm_trend(periods=1)
    assert bool(trend.iloc[0]["has_gaps"]) is False
    assert trend.iloc[0]["ttm_value"] == 460


def test_gapped_ttm_column_is_empty_not_a_fifteen_month_sum(snow_ttm_income):
    """Snowflake FY2025 10-K (accession 0001640147-25-000052) reports
    EquitySecuritiesFvNiRealizedGainLoss of -17,414,000 for 2024-02-01..2025-01-31.
    The fixture has no Q2 FY2025 quarter, so no consecutive window ends there."""
    row = snow_ttm_income["EquitySecuritiesFvNiRealizedGainLoss"]
    assert row["Q4 2025"] is None
    assert row["Q3 2025"] is None
    assert row["Q1 2026"] is None
    # Before the fix: 36,832,000 in the Q4 2025 column.
    assert 36_832_000 not in row.values()


def test_consecutive_ttm_column_matches_the_filed_fiscal_year(snow_ttm_income):
    """Snowflake FY2025 10-K (accession 0001640147-25-000052): NetIncomeLoss for
    2024-02-01..2025-01-31 is -1,285,640,000; the Q4 2025 TTM window is four
    consecutive quarters, so it must equal the filed fiscal year."""
    assert snow_ttm_income["NetIncomeLoss"]["Q4 2025"] == pytest.approx(-1_285_640_000)


WEEK = 7


def _weeks(start, *lengths):
    """Consecutive quarters of the given lengths in weeks, from ``start``."""
    out, s = [], start
    for i, w in enumerate(lengths, 1):
        e = s + timedelta(days=w * WEEK - 1)
        out.append(_quarter(100, s, e, f"Q{i}"))
        s = e + timedelta(days=1)
    return out


@pytest.mark.parametrize("weeks", [(12, 12, 12, 16), (12, 12, 12, 17), (13, 13, 13, 14)])
def test_fifty_two_fifty_three_week_quarters_are_consecutive(weeks):
    quarters = _weeks(date(2024, 9, 2), *weeks)
    calc = TTMCalculator(quarters)
    # Before the fix: a 16- or 17-week quarter (112/119 days) counted as a gap.
    assert bool(calc.calculate_ttm_trend(periods=1).iloc[0]["has_gaps"]) is False
    assert calc.calculate_ttm().has_gaps is False


def test_window_longer_than_a_year_is_a_gap():
    # Four 17-week quarters: each end-to-end gap is allowed, the 476-day span is not.
    quarters = _weeks(date(2024, 1, 1), 17, 17, 17, 17)
    assert TTMCalculator(quarters).calculate_ttm().has_gaps is True


# Costco, 52/53-week year ending on the Sunday nearest the end of August, with a
# 16-week fourth quarter. FY2025 10-K 0000909832-25-000101 (2024-09-02..2025-08-31):
# net income 8,099,000,000; basic EPS 18.24.
COST_FACTS = "https://data.sec.gov/api/xbrl/companyfacts/CIK0000909832.json"


@pytest.mark.vcr
def test_costco_fy2025_ttm_column_matches_the_filed_year():
    facts = EntityFactsParser.parse_company_facts(download_json(COST_FACTS))
    ttm = facts.get_ttm("NetIncomeLoss", as_of="2025-08-31")
    assert ttm.value == 8_099_000_000
    # Before the fix: has_gaps=True here and an empty statement cell below.
    assert ttm.has_gaps is False

    rows = {item["concept"].split(":")[-1]: item["values"]
            for item in facts.income_statement(period="ttm", periods=8).items}
    assert rows["NetIncomeLoss"]["Q4 2025"] == pytest.approx(8_099_000_000)
    assert round(rows["EarningsPerShareBasic"]["Q4 2025"], 2) == 18.24
