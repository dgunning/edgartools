"""Regression test for GitHub Issue #1695.

TTM summed the four quarterly amounts of per-share earnings lines, both
EarningsPerShare* and lines such as
``IncomeLossFromContinuingOperationsPerBasicShare``. Per-share earnings are a
ratio for their own period and quarterly amounts need not add up to the year
(ASC 260-10-55-50). The TTM value is now the filed fiscal-year amount when the
window is a fiscal year (even when no Q4 quarter can be derived), and otherwise
there is none (``calculate_ttm`` raises, a trend row is NaN). Dividends per
share are a flow and still sum.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1695
"""
from datetime import date

import pandas as pd
import pytest

from edgar.entity.entity_facts import EntityFacts
from edgar.entity.models import FinancialFact
from edgar.entity.parser import EntityFactsParser
from edgar.httprequests import download_json
from edgar.ttm import TTMCalculator

pytestmark = pytest.mark.regression

CONTINUING = "IncomeLossFromContinuingOperationsPerBasicShare"
END_DAY = {3: 31, 6: 30, 9: 30, 12: 31}


def _facts(concept, quarters, year_value):
    """Calendar 2025: four quarters (Q4 from the 10-K) and the fiscal year."""
    def fact(start, end, v, fp, form):
        return FinancialFact(concept=f"us-gaap:{concept}", taxonomy="us-gaap", label=concept,
                             value=v, numeric_value=v, unit="USD/shares", period_start=start,
                             period_end=end, period_type="duration", fiscal_year=2025, fiscal_period=fp,
                             filing_date=date(2026, 2, 20), form_type=form, accession="0000000000-26-000001")
    out = [fact(date(2025, sm, 1), date(2025, sm + 2, END_DAY[sm + 2]), v, f"Q{i + 1}", "10-K" if i == 3 else "10-Q")
           for i, (sm, v) in enumerate(zip((1, 4, 7, 10), quarters, strict=True))]
    out.append(fact(date(2025, 1, 1), date(2025, 12, 31), year_value, "FY", "10-K"))
    return out


def test_issue_reproduction_fiscal_year_window_is_the_filed_annual_amount():
    """ASC 260-10-55-38 to 55-48 Example 1: quarters 0.89, 1.19, 0.12, (0.11); year 1.87."""
    ef = EntityFacts(cik=1, name="Example", facts=_facts(CONTINUING, [0.89, 1.19, 0.12, -0.11], 1.87))
    ttm = ef.get_ttm(CONTINUING)
    # Before the fix: 2.09, the sum of the quarters.
    assert ttm.value == pytest.approx(1.87)
    assert not ttm.has_gaps


def test_rolling_window_has_no_twelve_month_per_share_amount():
    facts = _facts(CONTINUING, [0.89, 1.19, 0.12, -0.11], 1.87)
    prior_q4 = FinancialFact(concept=f"us-gaap:{CONTINUING}", taxonomy="us-gaap", label=CONTINUING,
                             value=0.5, numeric_value=0.5, unit="USD/shares", period_start=date(2024, 10, 1),
                             period_end=date(2024, 12, 31), period_type="duration", fiscal_year=2024,
                             fiscal_period="Q4", filing_date=date(2025, 2, 20), form_type="10-K")
    calc = TTMCalculator(facts + [prior_q4])
    with pytest.raises(ValueError, match="per-share earnings amount"):
        calc.calculate_ttm(as_of=date(2025, 9, 30))
    trend = calc.calculate_ttm_trend(periods=2)
    assert trend.iloc[0]["ttm_value"] == pytest.approx(1.87)
    assert pd.isna(trend.iloc[1]["ttm_value"])


@pytest.mark.parametrize("concept", ["EarningsPerShareBasic", "EarningsPerShareDiluted",
                                     "IncomeLossFromContinuingOperationsPerBasicAndDilutedShare",
                                     "NetIncomeLossPerOutstandingLimitedPartnershipUnitBasicAndDiluted"])
def test_every_per_share_earnings_family_is_the_filed_year(concept):
    facts = _facts(concept, [0.89, 1.19, 0.12, -0.11], 1.87)
    # Before the fix: 2.09 for each of these names.
    assert TTMCalculator(facts).calculate_ttm().value == pytest.approx(1.87)


def test_fiscal_year_without_a_fourth_quarter_is_the_filed_year():
    """Per-share lines get no derived Q4, so the quarterly window ends at Q3."""
    facts = [f for f in _facts(CONTINUING, [0.89, 1.19, 0.12, -0.11], 1.87) if f.fiscal_period != "Q4"]
    ttm = TTMCalculator(facts).calculate_ttm(as_of=date(2025, 12, 31))
    # Before the fix: ValidationError.
    assert ttm.value == pytest.approx(1.87)
    assert ttm.as_of_date == date(2025, 12, 31)


def test_dividends_per_share_still_sum():
    facts = _facts("CommonStockDividendsPerShareDeclared", [0.25, 0.25, 0.25, 0.30], 1.05)
    assert TTMCalculator(facts).calculate_ttm().value == pytest.approx(1.05)


# AMC Entertainment, income (loss) from continuing operations per basic share,
# 2017. 10-K 0001411579-19-000013 (quarterly data): Q1 0.07, Q2 (1.35), Q3 (0.33),
# Q4 (2.14). 10-K 0001411579-18-000014: full year (3.80). The quarters sum to (3.75).
AMC_FACTS = "https://data.sec.gov/api/xbrl/companyfacts/CIK0001411579.json"


@pytest.mark.vcr
def test_amc_2017_continuing_operations_eps_is_the_filed_year():
    facts = EntityFactsParser.parse_company_facts(download_json(AMC_FACTS))
    concept_facts = [f for f in facts if f.concept.endswith(CONTINUING)]
    calc = TTMCalculator(concept_facts)

    ttm = calc.calculate_ttm(as_of=date(2017, 12, 31))
    assert sorted(q.numeric_value for q in ttm.period_facts) == [-2.14, -1.35, -0.33, 0.07]
    # Before the fix: -3.75, the sum of the quarters.
    assert ttm.value == pytest.approx(-3.80)


@pytest.mark.vcr
def test_amc_2018_eps_is_the_filed_year_whatever_the_concept_name():
    """AMC 2018 basic EPS, 10-K 0001411579-19-000013: quarters 0.14, 0.17, (0.82),
    1.65 (sum 1.14); full year 0.91. Split-adjusted for the 2023 1-for-10 reverse
    split, the year is 9.10."""
    facts = EntityFactsParser.parse_company_facts(download_json(AMC_FACTS))
    eps = facts.get_ttm("EarningsPerShareBasic", as_of="2018-12-31")
    continuing = facts.get_ttm(CONTINUING, as_of="2018-12-31")
    # Before the fix: EarningsPerShareBasic summed to 11.40 with has_gaps=False.
    assert eps.value == pytest.approx(9.10)
    assert continuing.value == pytest.approx(9.10)


# Citigroup, income from continuing operations per basic share. FY2024 10-K
# 0000831001-25-000067: 6.03. The 10-Qs report Q1 1.60, Q2 1.54, Q3 1.53; no
# fourth quarter is filed or derivable for a per-share line.
CITI_FACTS = "https://data.sec.gov/api/xbrl/companyfacts/CIK0000831001.json"


@pytest.mark.vcr
def test_citigroup_fy2024_continuing_operations_eps_without_a_fourth_quarter():
    facts = EntityFactsParser.parse_company_facts(download_json(CITI_FACTS))
    # Before the fix: ValidationError, whose suggestion (as_of on a year end) was this call.
    ttm = facts.get_ttm(CONTINUING, as_of="2024-12-31")
    assert ttm.value == pytest.approx(6.03)
    assert ttm.as_of_date == date(2024, 12, 31)
    with pytest.raises(ValueError, match="not a fiscal year"):
        facts.get_ttm(CONTINUING, as_of="2025-09-30")
