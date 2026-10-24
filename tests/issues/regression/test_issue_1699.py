"""Regression test for GitHub Issue #1699.

``TTMCalculator.calculate_ttm`` labelled ``TTMMetric.periods`` with each
quarter's raw ``fiscal_year``. ``quarterize`` keeps the latest-filed fact for a
period, and a quarter repeated as a comparative carries the later filing's
fiscal year, so Apple's TTM revenue to 2023-07-01 read
[(2022, 'Q4'), (2024, 'Q1'), (2024, 'Q2'), (2024, 'Q3')]. Labels now come from
the period end and the fiscal year-end month, as ``calculate_ttm_trend`` does.

A 52/53-week year that closes a few days into the month after its fiscal
year-end month (Costco 2023-09-03, Home Depot 2026-02-01) is labelled with the
year it closes, not the next one.

Not changed: ``as_of`` still selects by period end, not by what was filed by
that date (a point-in-time view is a design decision), and ``fiscal_period``
still comes from the latest-filed fact, so a re-filed comparative can read 'FY'.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1699
"""
from datetime import date

import pytest

from edgar.entity.enhanced_statement import calculate_fiscal_year_for_label
from edgar.entity.parser import EntityFactsParser
from edgar.httprequests import download_json

pytestmark = pytest.mark.regression

# Apple company facts. Fiscal year ends late September. Quarterly revenue
# (RevenueFromContractWithCustomerExcludingAssessedTax), fiscal 2023:
# Q1 to 2022-12-31 117,154,000,000; Q2 to 2023-04-01 94,836,000,000;
# Q3 to 2023-07-01 81,797,000,000 (10-Q 0000320193-23-000077); fiscal 2022 Q4
# to 2022-09-24 90,146,000,000. The latest-filed copies are the fiscal 2024
# 10-Qs' comparatives, e.g. 10-Q 0000320193-24-000006 for Q1.
AAPL_FACTS = "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json"


@pytest.mark.vcr
def test_apple_ttm_revenue_periods_are_labelled_by_their_own_fiscal_year():
    facts = EntityFactsParser.parse_company_facts(download_json(AAPL_FACTS))
    ttm = facts.get_ttm_revenue(as_of=date(2023, 7, 1))

    assert ttm.value == 383_933_000_000
    assert [q.period_end for q in ttm.period_facts] == [
        date(2022, 9, 24), date(2022, 12, 31), date(2023, 4, 1), date(2023, 7, 1)]
    # Before the fix: [(2022, 'Q4'), (2024, 'Q1'), (2024, 'Q2'), (2024, 'Q3')].
    assert ttm.periods == [(2022, "Q4"), (2023, "Q1"), (2023, "Q2"), (2023, "Q3")]


@pytest.mark.parametrize("period_end, fye_month, label", [
    (date(2023, 9, 3), 8, 2023),    # Costco FY2023 closes in September
    (date(2026, 2, 1), 1, 2026),    # Home Depot FY2025 (named FY2026 here) closes in February
    (date(2023, 1, 1), 12, 2022),   # existing December rule
    (date(2023, 11, 20), 8, 2024),  # Costco Q1 of the next year
])
def test_year_end_drifting_into_the_next_month_closes_its_fiscal_year(period_end, fye_month, label):
    assert calculate_fiscal_year_for_label(period_end, fye_month) == label


# Costco: fiscal 2023 is 2022-08-29..2023-09-03, net income 6,292,000,000 (10-K
# 0000909832-23-000042). Home Depot: 2025-02-03..2026-02-01, net income
# 14,156,000,000 (10-K 0001628280-26-019436).
COST_FACTS = "https://data.sec.gov/api/xbrl/companyfacts/CIK0000909832.json"
HD_FACTS = "https://data.sec.gov/api/xbrl/companyfacts/CIK0000354950.json"


@pytest.mark.vcr
def test_fifty_two_fifty_three_week_year_is_labelled_by_the_year_it_closes():
    cost = EntityFactsParser.parse_company_facts(download_json(COST_FACTS)).get_ttm("NetIncomeLoss", as_of="2023-09-05")
    assert cost.value == 6_292_000_000
    # Before the fix: [(2023, 'Q1'), (2023, 'Q2'), (2023, 'Q3'), (2024, 'Q4')].
    assert cost.periods == [(2023, "Q1"), (2023, "Q2"), (2023, "Q3"), (2023, "Q4")]

    hd = EntityFactsParser.parse_company_facts(download_json(HD_FACTS)).get_ttm("NetIncomeLoss", as_of="2026-02-01")
    assert hd.value == 14_156_000_000
    # Before the fix: the quarter ending 2026-02-01 read (2027, 'Q4').
    assert hd.periods == [(2026, "Q1"), (2026, "Q2"), (2026, "Q3"), (2026, "Q4")]
