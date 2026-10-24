"""Regression test for GitHub Issue #1686.

The EPS share-count lookups in ``EntityFacts._prepare_quarterly_facts`` and
``TTMStatementBuilder._trend_for_eps`` named
``WeightedAverageNumberOfSharesOutstandingBasicAndDiluted`` (plural "Shares"),
which is not a us-gaap element. The real element is
``WeightedAverageNumberOfShareOutstandingBasicAndDiluted``, so a filer that tags
its one basic-and-diluted count with it got no derived Q4 EPS and no TTM EPS.
Neither diluted list held the combined element at all.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1686
"""
import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from edgar.entity.entity_facts import EntityFacts
from edgar.entity.models import FinancialFact
from edgar.entity.parser import EntityFactsParser

pytestmark = pytest.mark.regression

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "entity" / "snow_facts.json"
COMBINED = "WeightedAverageNumberOfShareOutstandingBasicAndDiluted"


def _eps_values(df, column):
    rows = df[df["label"].str.contains("Earnings Per Share", case=False, na=False)]
    return [float(v) for v in rows[column]]


def test_snowflake_q4_fy2021_eps_is_derived_from_the_combined_share_count():
    """Snowflake FY2021 (year ended 2021-01-31) tagged its share count only with
    the combined element.

    Inputs read from the filings' XBRL:
    10-K 0001640147-21-000073: NetIncomeLoss FY2021 = -539,102,000;
    WeightedAverageNumberOfShareOutstandingBasicAndDiluted FY2021 = 141,613,196.
    10-Q 0001640147-20-000023: NetIncomeLoss nine months to 2020-10-31 =
    -340,167,000; combined weighted-average count for the nine months = 93,763,599.
    """
    facts = EntityFactsParser.parse_company_facts(json.loads(FIXTURE.read_text("utf-8")))
    df = facts.income_statement(periods=40, period="quarterly", as_dataframe=True)

    q4_income = -539_102_000 - -340_167_000
    q4_shares = 4 * 141_613_196 - 3 * 93_763_599   # the derivation's volatile-share route
    expected = q4_income / q4_shares                # -0.6976..., reported as $(0.70)

    basic, diluted = _eps_values(df, "Q4 2021")
    assert basic == pytest.approx(expected)
    assert diluted == pytest.approx(expected)
    assert round(basic, 2) == -0.70


def _fact(concept, value, start, end, fp, unit):
    return FinancialFact(
        concept=f"us-gaap:{concept}", taxonomy="us-gaap", label=concept,
        value=value, numeric_value=float(value), unit=unit,
        period_start=start, period_end=end, period_type="duration",
        fiscal_year=end.year if fp != "FY" else start.year, fiscal_period=fp,
        filing_date=end + timedelta(days=40),
        form_type="10-K" if fp == "FY" else "10-Q", statement_type="IncomeStatement",
    )


def test_ttm_eps_uses_a_filer_that_tags_only_the_combined_element():
    """Synthetic calendar-year filer: net income 100 a quarter, 50 shares, tagged
    with the combined basic-and-diluted element only. TTM EPS = 400 / 50 = 8."""
    quarters = [((1, 1), (3, 31), "Q1"), ((4, 1), (6, 30), "Q2"),
                ((7, 1), (9, 30), "Q3"), ((10, 1), (12, 31), "Q4")]
    facts = []
    for year in (2023, 2024):
        for (sm, sd), (em, ed), fp in quarters:
            start, end = date(year, sm, sd), date(year, em, ed)
            facts.append(_fact("NetIncomeLoss", 100, start, end, fp, "USD"))
            facts.append(_fact("Revenues", 500, start, end, fp, "USD"))
            facts.append(_fact(COMBINED, 50, start, end, fp, "shares"))
            facts.append(_fact("EarningsPerShareBasic", 2, start, end, fp, "USD/shares"))
            facts.append(_fact("EarningsPerShareDiluted", 2, start, end, fp, "USD/shares"))
    ef = EntityFacts(cik=1, name="Combined-share filer", facts=facts)

    items = {i["concept"]: i["values"] for i in ef.income_statement(period="ttm", periods=4).items}
    basic = items["EarningsPerShareBasic"]
    diluted = items["EarningsPerShareDiluted"]
    assert basic["Q4 2024"] == pytest.approx(8.0)
    assert diluted["Q4 2024"] == pytest.approx(8.0)
