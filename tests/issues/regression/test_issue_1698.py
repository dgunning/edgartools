"""Regression test for GitHub Issue #1698.

``get_ttm()`` / ``TTMCalculator.calculate_ttm`` summed four quarterly
weighted-average share counts, so a TTM share count came back about four times
too large. The averaging rule for levels (share counts, rates) from bead
edgartools-djwu had been wired into ``calculate_ttm_trend`` only; the scalar path
kept an unconditional ``sum()``. Both paths now aggregate through
``TTMCalculator._aggregate_window``.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1698
"""
import json
from datetime import date
from pathlib import Path

import pytest

from edgar.entity.models import FinancialFact
from edgar.entity.parser import EntityFactsParser
from edgar.ttm.calculator import TTMCalculator

pytestmark = pytest.mark.regression

SHARES = "WeightedAverageNumberOfSharesOutstandingBasic"
FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "entity" / "snow_facts.json"


def _quarter(value, start, end, fp, unit="shares", concept=f"us-gaap:{SHARES}"):
    return FinancialFact(
        concept=concept,
        taxonomy="us-gaap",
        label=concept,
        value=value,
        numeric_value=float(value),
        unit=unit,
        period_start=start,
        period_end=end,
        period_type="duration",
        fiscal_year=2025,
        fiscal_period=fp,
        filing_date=date(2026, 2, 1),
        form_type="10-Q",
        accession="0000000000-26-000001",
    )


# ASC 260-10-55-40, -42, -44, -46: four contiguous quarters of weighted-average shares.
ASC_QUARTERS = [
    (3_333_333, date(2025, 1, 1), date(2025, 3, 31), "Q1"),
    (3_766_667, date(2025, 4, 1), date(2025, 6, 30), "Q2"),
    (4_266_666, date(2025, 7, 1), date(2025, 9, 30), "Q3"),
    (4_600_000, date(2025, 10, 1), date(2025, 12, 31), "Q4"),
]


def test_calculate_ttm_averages_weighted_average_share_counts():
    calc = TTMCalculator([_quarter(*q) for q in ASC_QUARTERS])
    ttm = calc.calculate_ttm(as_of=date(2025, 12, 31))

    assert not ttm.has_gaps
    assert ttm.value == pytest.approx(3_991_666.5)
    # The defect: the sum of four averages, four times the year's share count.
    assert ttm.value != pytest.approx(15_966_666)


def test_calculate_ttm_agrees_with_trend_on_share_counts():
    calc = TTMCalculator([_quarter(*q) for q in ASC_QUARTERS])
    trend_value = calc.calculate_ttm_trend(periods=1).iloc[0]["ttm_value"]
    assert calc.calculate_ttm(as_of=date(2025, 12, 31)).value == pytest.approx(trend_value)


def test_calculate_ttm_still_sums_monetary_flows():
    revenue = [100.0, 110.0, 120.0, 130.0]
    facts = [_quarter(v, s, e, fp, unit="USD", concept="us-gaap:Revenues")
             for v, (_, s, e, fp) in zip(revenue, ASC_QUARTERS, strict=True)]
    assert TTMCalculator(facts).calculate_ttm(as_of=date(2025, 12, 31)).value == pytest.approx(460.0)


def test_snowflake_get_ttm_share_count_is_the_window_mean():
    """Snowflake company facts (repository fixture), TTM window ending 2023-10-31.

    Quarterly basic weighted-average shares, checked against the filings' XBRL:
    three months ended 2023-10-31 = 329,310,000 and ended 2022-10-31 = 320,135,000
    (10-Q Q3 FY2024, accession 0001640147-23-000260); ended 2023-07-31 =
    327,335,000 (10-Q, 0001640147-23-000199); ended 2023-04-30 = 324,157,000
    (10-Q, 0001640147-23-000102). The window has no fiscal Q4 (not tagged as a
    three-month count), so it is gapped, but the aggregation is what is pinned here.
    """
    facts = EntityFactsParser.parse_company_facts(json.loads(FIXTURE.read_text("utf-8")))
    ttm = facts.get_ttm(SHARES, as_of="2023-10-31")

    window = {q.period_end: q.numeric_value for q in ttm.period_facts}
    assert window[date(2023, 10, 31)] == 329_310_000
    assert window[date(2022, 10, 31)] == 320_135_000
    assert window[date(2023, 7, 31)] == 327_335_000
    assert window[date(2023, 4, 30)] == 324_157_000

    assert ttm.value == pytest.approx(sum(window.values()) / 4)
    assert ttm.value == pytest.approx(325_234_250)
    # Before the fix: 1,300,937,000, the sum of the four quarters.
    assert ttm.value < 400_000_000
