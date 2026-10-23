"""Regression test for GitHub Issue #1782.

TTM diluted EPS divided the window's income by the average of the quarters'
diluted share counts. A profitable quarter's diluted count includes options
that are antidilutive for a loss, so a loss window containing one was divided
by too many shares (ASC 260-10-45-17, -20). A rolling window with a loss now
uses the basic count; the control number is income from continuing operations
where tagged (ASC 260-10-45-18). A fiscal-year window keeps the filed diluted
count, which already applies the year's test.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1782
"""
from datetime import date, timedelta

import pytest

from edgar.entity.entity_facts import EntityFacts
from edgar.entity.models import FinancialFact
from edgar.entity.parser import EntityFactsParser
from edgar.httprequests import download_json

pytestmark = pytest.mark.regression

QUARTERS = [((1, 1), (3, 31)), ((4, 1), (6, 30)), ((7, 1), (9, 30)), ((10, 1), (12, 31))]


def _fact(concept, value, start, end, fp, unit):
    return FinancialFact(
        concept=f"us-gaap:{concept}", taxonomy="us-gaap", label=concept, value=value,
        numeric_value=float(value), unit=unit, period_start=start, period_end=end,
        period_type="duration", fiscal_year=start.year, fiscal_period=fp,
        filing_date=end + timedelta(days=40), form_type="10-K" if fp in ("FY", "Q4") else "10-Q",
        statement_type="IncomeStatement",
    )


def _option_issuer(incomes, continuing=None):
    """Basic shares 100 every quarter; 10 incremental option shares in each
    profitable quarter's diluted count. ``incomes`` maps year -> four quarters."""
    facts = []
    for year, quarter_incomes in incomes.items():
        for q, (((sm, sd), (em, ed)), income) in enumerate(zip(QUARTERS, quarter_incomes, strict=True), 1):
            start, end, fp = date(year, sm, sd), date(year, em, ed), f"Q{q}"
            diluted = 110 if income > 0 else 100
            facts += [
                _fact("NetIncomeLoss", income, start, end, fp, "USD"),
                _fact("Revenues", 200, start, end, fp, "USD"),
                _fact("WeightedAverageNumberOfSharesOutstandingBasic", 100, start, end, fp, "shares"),
                _fact("WeightedAverageNumberOfDilutedSharesOutstanding", diluted, start, end, fp, "shares"),
                _fact("EarningsPerShareBasic", income / 100, start, end, fp, "USD/shares"),
                _fact("EarningsPerShareDiluted", income / diluted, start, end, fp, "USD/shares"),
            ]
            if continuing is not None:
                facts.append(_fact("IncomeLossFromContinuingOperations", continuing, start, end, fp, "USD"))
    return facts


def _ttm_eps(facts, periods=4):
    ef = facts if isinstance(facts, EntityFacts) else EntityFacts(cik=1, name="Option issuer", facts=facts)
    return {item["concept"]: item["values"]
            for item in ef.income_statement(period="ttm", periods=periods).items
            if item["concept"] in ("EarningsPerShareBasic", "EarningsPerShareDiluted")}


def test_issue_reproduction_fiscal_year_loss():
    """The issue's FY2024: Q1 +50, Q2-Q4 -100 each, filed FY diluted count 100."""
    facts = _option_issuer({2024: [50, -100, -100, -100]})
    year = (date(2024, 1, 1), date(2024, 12, 31), "FY")
    for c, v, u in [("NetIncomeLoss", -250, "USD"), ("Revenues", 800, "USD"),
                    ("WeightedAverageNumberOfSharesOutstandingBasic", 100, "shares"),
                    ("WeightedAverageNumberOfDilutedSharesOutstanding", 100, "shares"),
                    ("EarningsPerShareBasic", -2.5, "USD/shares"), ("EarningsPerShareDiluted", -2.5, "USD/shares")]:
        facts.append(_fact(c, v, *year, u))
    eps = _ttm_eps(facts, periods=1)
    # Before: diluted -2.439024 (the mean diluted count, 102.5).
    assert eps["EarningsPerShareBasic"]["Q4 2024"] == pytest.approx(-2.5)
    assert eps["EarningsPerShareDiluted"]["Q4 2024"] == pytest.approx(-2.5)


def test_rolling_loss_window_uses_the_basic_count():
    # Window ending Q1 2025: Q2-Q4 2024 (-100 each) and Q1 2025 (+50) = -250.
    eps = _ttm_eps(_option_issuer({2024: [-100, -100, -100, -100], 2025: [50, -100, -100, -100]}))
    assert eps["EarningsPerShareDiluted"]["Q1 2025"] == pytest.approx(eps["EarningsPerShareBasic"]["Q1 2025"])
    assert eps["EarningsPerShareDiluted"]["Q1 2025"] == pytest.approx(-250 / 100, rel=1e-3)


def test_profitable_window_keeps_the_diluted_count():
    eps = _ttm_eps(_option_issuer({2024: [100, 100, 100, 100], 2025: [100, 100, 100, 100]}))
    assert eps["EarningsPerShareDiluted"]["Q1 2025"] == pytest.approx(400 / 110)


def test_continuing_operations_income_is_the_control_number():
    """Net loss from a discontinued operation, continuing operations profitable:
    the options are dilutive, so the diluted count stays (ASC 260-10-45-18)."""
    eps = _ttm_eps(_option_issuer({2024: [-100] * 4, 2025: [50, -100, -100, -100]}, continuing=20))
    basic = eps["EarningsPerShareBasic"]["Q1 2025"]
    assert eps["EarningsPerShareDiluted"]["Q1 2025"] > basic


# Lyft (LYFT), company facts. 10-Q 0001759509-24-000102: the quarter to
# 2024-06-30 earned 5,014,000 with 406,512,000 basic and 411,969,000 diluted
# shares; the six months, a loss of 26,521,000, report basic = diluted =
# 404,033,000. The TTM window ending 2024-09-30 is a loss.
LYFT_FACTS = "https://data.sec.gov/api/xbrl/companyfacts/CIK0001759509.json"


@pytest.mark.vcr
def test_lyft_loss_window_with_a_profitable_quarter():
    facts = EntityFactsParser.parse_company_facts(download_json(LYFT_FACTS))
    eps = _ttm_eps(facts, periods=12)

    basic = eps["EarningsPerShareBasic"]["Q3 2024"]
    diluted = eps["EarningsPerShareDiluted"]["Q3 2024"]
    assert basic < 0
    # Before the fix: -0.160942, Q2 2024's option shares averaged into the loss.
    assert diluted == pytest.approx(basic)
    assert diluted == pytest.approx(-0.161482, abs=1e-6)
