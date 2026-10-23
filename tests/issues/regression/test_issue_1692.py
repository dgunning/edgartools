"""Regression test for GitHub Issue #1692.

TTM EPS (``TTMStatementBuilder._trend_for_eps``) and the derived Q4 EPS
(``EntityFacts._prepare_quarterly_facts``) divided ``NetIncomeLoss`` even when
the filer tags ``NetIncomeLossAvailableToCommonStockholdersBasic``. Basic EPS
divides income available to common stockholders (ASC 260-10-45-10, -11), so a
preferred-stock issuer's derived EPS was overstated by its preferred dividends.
The quarterly path also merged both concepts into one list, so one derivation
could pair one concept's year with the other's quarters.

The numerator is now income available to common (diluted: the diluted
variant, then basic), one concept per derivation. Net income stands in only
where the filer's facts do not show it differing.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1692
"""
from datetime import date, timedelta

import pytest

from edgar.entity.entity_facts import EntityFacts
from edgar.entity.models import FinancialFact
from edgar.entity.parser import EntityFactsParser
from edgar.httprequests import download_json

pytestmark = pytest.mark.regression

QUARTERS = [((1, 1), (3, 31), "Q1"), ((4, 1), (6, 30), "Q2"), ((7, 1), (9, 30), "Q3")]


def _fact(concept, value, start, end, fp, unit):
    return FinancialFact(
        concept=f"us-gaap:{concept}", taxonomy="us-gaap", label=concept, value=value,
        numeric_value=float(value), unit=unit, period_start=start, period_end=end,
        period_type="duration", fiscal_year=start.year, fiscal_period=fp,
        filing_date=end + timedelta(days=40), form_type="10-K" if fp == "FY" else "10-Q",
        statement_type="IncomeStatement",
    )


def _preferred_issuer(available_quarters=True):
    """The issue's synthetic preferred issuer: net income 1,000 a quarter,
    preferred dividends 100, income available to common 900, basic shares 100,
    diluted 105. Filed EPS 9.00 basic and 8.5714 diluted a quarter."""
    quarter = {"NetIncomeLoss": 1000.0, "Revenues": 5000.0,
               "EarningsPerShareBasic": 9.0, "EarningsPerShareDiluted": 900 / 105}
    if available_quarters:
        quarter["NetIncomeLossAvailableToCommonStockholdersBasic"] = 900.0
    shares = {"WeightedAverageNumberOfSharesOutstandingBasic": 100.0,
              "WeightedAverageNumberOfDilutedSharesOutstanding": 105.0}
    year = {"NetIncomeLoss": 4000.0, "Revenues": 20000.0,
            "NetIncomeLossAvailableToCommonStockholdersBasic": 3600.0,
            "EarningsPerShareBasic": 36.0, "EarningsPerShareDiluted": 3600 / 105}

    def unit(c):
        return "shares" if c in shares else "USD/shares" if "PerShare" in c else "USD"

    facts = []
    for y in (2023, 2024, 2025):
        for (sm, sd), (em, ed), fp in QUARTERS:
            for c, v in {**quarter, **shares}.items():
                facts.append(_fact(c, v, date(y, sm, sd), date(y, em, ed), fp, unit(c)))
        for c, v in {**year, **shares}.items():
            facts.append(_fact(c, v, date(y, 1, 1), date(y, 12, 31), "FY", unit(c)))
    return EntityFacts(cik=1, name="Example Preferred Issuer", facts=facts)


def _ttm_eps(ef, periods=4):
    return {item["concept"]: item["values"]
            for item in ef.income_statement(period="ttm", periods=periods).items
            if item["concept"] in ("EarningsPerShareBasic", "EarningsPerShareDiluted")}


def test_ttm_eps_divides_income_available_to_common():
    eps = _ttm_eps(_preferred_issuer())
    # Before the fix: 40.00 and 38.0952 in every column (net income 4,000).
    assert list(eps["EarningsPerShareBasic"].values()) == pytest.approx([36.0] * 4)
    assert list(eps["EarningsPerShareDiluted"].values()) == pytest.approx([3600 / 105] * 4)


def test_derived_q4_eps_divides_income_available_to_common():
    df = _preferred_issuer().income_statement(period="quarterly", periods=8, as_dataframe=True)
    basic = df.loc["EarningsPerShareBasic"]
    diluted = df.loc["EarningsPerShareDiluted"]
    # Before the fix: 10.00 and 9.5238 (net income 1,000).
    assert basic["Q4 2025"] == pytest.approx(9.0)
    assert diluted["Q4 2025"] == pytest.approx(900 / 105)


def test_net_income_does_not_stand_in_where_the_filer_shows_it_differs():
    """Income available to common tagged for the year only: the fiscal-year
    window uses it, the rolling windows have no numerator, and net income (which
    the overlapping years' facts show is different) is not substituted for it."""
    eps = _ttm_eps(_preferred_issuer(available_quarters=False))["EarningsPerShareBasic"]
    assert eps["Q4 2025"] == pytest.approx(36.0)
    assert eps["Q3 2025"] is None


# Public Storage (PSA), company facts. FY2025 10-K 0001628280-26-007696:
# NetIncomeLoss 1,784,348,000; net income allocable to common shareholders
# 1,585,585,000; weighted-average shares basic 175,447,000, diluted 175,902,000;
# EPS basic 9.04, diluted 9.01.
PSA_FACTS = "https://data.sec.gov/api/xbrl/companyfacts/CIK0001393311.json"


@pytest.mark.vcr
def test_public_storage_fy2025_ttm_eps_matches_the_filed_eps():
    facts = EntityFactsParser.parse_company_facts(download_json(PSA_FACTS))
    eps = _ttm_eps(facts, periods=8)

    basic = eps["EarningsPerShareBasic"]["Q4 2025"]
    diluted = eps["EarningsPerShareDiluted"]["Q4 2025"]
    # Before the fix: 10.17 and 10.14, net income over the share counts.
    assert basic == pytest.approx(1_585_585_000 / 175_447_000)
    assert diluted == pytest.approx(1_585_585_000 / 175_902_000)
    assert (round(basic, 2), round(diluted, 2)) == (9.04, 9.01)
