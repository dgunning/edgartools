"""Regression test for GitHub Issue #1691.

TTM EPS divided four quarters of net income by the plain mean of four share
counts, and when the fourth quarter had no three-month count (a 10-K rarely
tags one) it put the FISCAL-YEAR count in that quarter's slot. That weighted
Q1-Q3 at 5/16 each and Q4 at 1/16 of the year, so even the TTM column that IS
the fiscal year disagreed with the filed annual EPS.

Now a window that is a fiscal year uses the year's filed count, a missing Q4
count is solved from the year's count and its other three quarters (day
weighted), and other windows weight their quarters by days. A quarter that
cannot be solved from its year's other quarters is solved from the filer's
cumulative counts (Q4 = FY - 9M), so a window is not left blank.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1691
"""
import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from edgar.entity.entity_facts import EntityFacts
from edgar.entity.models import FinancialFact
from edgar.entity.parser import EntityFactsParser
from edgar.httprequests import download_json
from edgar.ttm.statement import _quarter_share_count, _window_share_count

pytestmark = pytest.mark.regression

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "entity" / "snow_facts.json"


def _ttm_eps(ef, periods=8):
    return {item["concept"]: item["values"]
            for item in ef.income_statement(period="ttm", periods=periods).items
            if item["concept"] in ("EarningsPerShareBasic", "EarningsPerShareDiluted")}


def test_snowflake_fiscal_year_ttm_eps_equals_the_filed_annual_eps():
    """Snowflake FY2024 (year ended 2024-01-31), 10-K 0001640147-24-000101:
    NetIncomeLoss -836,097,000; weighted-average shares basic and diluted
    328,001,000; basic EPS -2.55."""
    facts = EntityFactsParser.parse_company_facts(json.loads(FIXTURE.read_text("utf-8")))
    eps = _ttm_eps(facts)

    expected = -836_097_000 / 328_001_000            # -2.549068
    # Before the fix: -2.555303 (FY count averaged in as if it were Q4's).
    assert eps["EarningsPerShareBasic"]["Q4 2024"] == pytest.approx(expected)
    assert eps["EarningsPerShareDiluted"]["Q4 2024"] == pytest.approx(expected)
    assert round(eps["EarningsPerShareBasic"]["Q4 2024"], 2) == -2.55


# Synthetic calendar 2025: 100M shares through September, 100M more issued on
# 1 October. Day-weighted, the year's count is (100M x 273 + 200M x 92) / 365.
QUARTERS = [(date(2025, 1, 1), date(2025, 3, 31), "Q1"), (date(2025, 4, 1), date(2025, 6, 30), "Q2"),
            (date(2025, 7, 1), date(2025, 9, 30), "Q3"), (date(2025, 10, 1), date(2025, 12, 31), "Q4")]
FY_SHARES = (100e6 * 273 + 200e6 * 92) / 365


def _fact(concept, value, start, end, fp, unit):
    return FinancialFact(
        concept=f"us-gaap:{concept}", taxonomy="us-gaap", label=concept, value=value,
        numeric_value=float(value), unit=unit, period_start=start, period_end=end,
        period_type="duration", fiscal_year=2025, fiscal_period=fp,
        filing_date=end + timedelta(days=40), form_type="10-K" if fp in ("FY", "Q4") else "10-Q",
        statement_type="IncomeStatement",
    )


def _issuance_year():
    facts = []
    for start, end, fp in QUARTERS[:3]:
        facts.append(_fact("NetIncomeLoss", 25e6, start, end, fp, "USD"))
        facts.append(_fact("Revenues", 100e6, start, end, fp, "USD"))
        facts.append(_fact("WeightedAverageNumberOfSharesOutstandingBasic", 100e6, start, end, fp, "shares"))
    year = (date(2025, 1, 1), date(2025, 12, 31), "FY")
    facts.append(_fact("NetIncomeLoss", 100e6, *year, "USD"))
    facts.append(_fact("Revenues", 400e6, *year, "USD"))
    facts.append(_fact("WeightedAverageNumberOfSharesOutstandingBasic", FY_SHARES, *year, "shares"))
    facts.append(_fact("EarningsPerShareBasic", 100e6 / FY_SHARES, *year, "USD/shares"))
    return facts


def test_issuance_year_ttm_eps_matches_the_annual_eps():
    eps = _ttm_eps(EntityFacts(cik=1, name="Issuer", facts=_issuance_year()), periods=1)
    # Before the fix: 100M / mean(100M, 100M, 100M, FY count) = 0.941, not 0.799.
    assert eps["EarningsPerShareBasic"]["Q4 2025"] == pytest.approx(100e6 / FY_SHARES)


def test_missing_q4_count_is_solved_day_weighted_not_copied_from_the_year():
    facts = _issuance_year()
    counts = [f for f in facts if f.concept.endswith("SharesOutstandingBasic")]
    quarter_counts = {f.period_end: f for f in counts if f.fiscal_period != "FY"}
    annual_counts = {f.period_end: f for f in counts if f.fiscal_period == "FY"}
    q4 = _fact("NetIncomeLoss", 25e6, *QUARTERS[3], "USD")

    assert _quarter_share_count(q4, quarter_counts, annual_counts) == pytest.approx(200e6)
    # No year count to solve from: no Q4 count at all rather than a substitute.
    assert _quarter_share_count(q4, quarter_counts, {}) is None

    window = [_fact("NetIncomeLoss", 25e6, s, e, fp, "USD") for s, e, fp in QUARTERS]
    assert _window_share_count(window, quarter_counts, annual_counts) == pytest.approx(FY_SHARES)


def test_missing_count_is_solved_from_cumulative_counts():
    """Q1 has no three-month count, so Q4 cannot be solved from the other three
    quarters; the nine-month and fiscal-year counts solve it exactly."""
    q1, q2, q3, q4 = QUARTERS
    y = date(2025, 1, 1)
    nine = _fact("WeightedAverageNumberOfSharesOutstandingBasic", 99e6, y, q3[1], "Q3", "shares")
    year = _fact("WeightedAverageNumberOfSharesOutstandingBasic", 98e6, y, q4[1], "FY", "shares")
    quarter_counts = {q[1]: _fact("WeightedAverageNumberOfSharesOutstandingBasic", c, *q, "shares")
                      for q, c in ((q2, 99e6), (q3, 98.5e6))}
    cumulative = {(f.period_start, f.period_end): f for f in (nine, year)}
    q4_fact = _fact("NetIncomeLoss", 25e6, *q4, "USD")

    expected = (98e6 * 365 - 99e6 * 273) / 92
    # Before the fix: None, so every window containing Q4 was blank.
    assert _quarter_share_count(q4_fact, quarter_counts, {year.period_end: year}, cumulative) == pytest.approx(expected)
    # Without the nine-month count there is nothing to solve from.
    assert _quarter_share_count(q4_fact, quarter_counts, {year.period_end: year}, {}) is None


# Alphabet company facts. No three-month share count is tagged for Q1 2023, so
# Q4 2023 cannot be solved from 2023's other quarters. Basic weighted shares
# (millions): 9M 2023 12,677 (10-Q 0001652044-24-000118), FY2023 12,630 (10-K
# 0001652044-26-000018), Q3 2023 12,581, Q1 2024 12,415, Q2 2024 12,343, Q3 2024
# 12,290. Net income (millions): Q3 2023 19,689; FY2023 73,795 less 9M 53,108 =
# Q4 20,687; Q1 2024 23,662; Q2 23,619; Q3 26,301. Diluted: 9M 2023 12,761,
# FY2023 12,722, Q3 2023 12,696, Q1 2024 12,527, Q2 12,495, Q3 12,419.
GOOGL_FACTS = "https://data.sec.gov/api/xbrl/companyfacts/CIK0001652044.json"


def _hand_eps(income, counts_days):
    return sum(income) / (sum(c * d for c, d in counts_days) / sum(d for _, d in counts_days))


@pytest.mark.vcr
def test_alphabet_windows_spanning_an_unsolved_fourth_quarter_are_not_blank():
    eps = _ttm_eps(EntityFactsParser.parse_company_facts(download_json(GOOGL_FACTS)), periods=12)
    basic, diluted = eps["EarningsPerShareBasic"], eps["EarningsPerShareDiluted"]

    q4_basic = (12_630 * 365 - 12_677 * 273) / 92      # 12,490.5
    q4_diluted = (12_722 * 365 - 12_761 * 273) / 92    # 12,606.3
    q2_income = [19_689, 20_687, 23_662, 23_619]
    q3_income = [20_687, 23_662, 23_619, 26_301]
    # Before the fix: None in all four cells.
    assert basic["Q2 2024"] == pytest.approx(_hand_eps(q2_income, [(12_581, 92), (q4_basic, 92), (12_415, 91), (12_343, 91)]))
    assert basic["Q3 2024"] == pytest.approx(_hand_eps(q3_income, [(q4_basic, 92), (12_415, 91), (12_343, 91), (12_290, 92)]))
    assert diluted["Q2 2024"] == pytest.approx(_hand_eps(q2_income, [(12_696, 92), (q4_diluted, 92), (12_527, 91), (12_495, 91)]))
    assert diluted["Q3 2024"] == pytest.approx(_hand_eps(q3_income, [(q4_diluted, 92), (12_527, 91), (12_495, 91), (12_419, 92)]))
    # Within 1% of the sum of the filed quarterly EPS (basic 1.56 + 1.66 + 1.91 + 1.91).
    assert basic["Q2 2024"] == pytest.approx(7.04, rel=0.01)
