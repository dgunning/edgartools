"""Regression test for GitHub Issue #1675.

When a year-to-date period had been recast (an original and a later restated
fact for the same period), ``TTMCalculator._find_matching_ytd9`` (and the Q2/Q3
operand finders) maximised only ``period_end``, so ``max`` returned whichever
fact was listed first. The derived quarter changed with input order. Operands
are now ranked by period, then source form, then filing date.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1675
"""
import json
from datetime import date
from pathlib import Path

import pytest

from edgar.entity.models import FinancialFact
from edgar.entity.parser import EntityFactsParser
from edgar.ttm import TTMCalculator

pytestmark = pytest.mark.regression

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "entity" / "snow_facts.json"


def _fact(start, end, value, filed, fp):
    return FinancialFact(concept="us-gaap:Revenues", taxonomy="us-gaap", label="Revenue",
                         value=value, numeric_value=value, unit="USD", period_type="duration",
                         period_start=date.fromisoformat(start), period_end=date.fromisoformat(end),
                         fiscal_year=2023, fiscal_period=fp, filing_date=date.fromisoformat(filed),
                         form_type="10-K" if fp == "FY" else "10-Q")


# The issue's inputs: original nine months 750 (incl. a disposed operation),
# FY 800 and recast nine months 600 on the continuing basis.
ISSUE_FACTS = [
    _fact("2023-01-01", "2023-03-31", 250, "2023-05-01", "Q1"),
    _fact("2023-04-01", "2023-06-30", 250, "2023-08-01", "Q2"),
    _fact("2023-07-01", "2023-09-30", 250, "2023-11-01", "Q3"),
    _fact("2023-01-01", "2023-09-30", 750, "2023-11-01", "Q3"),
    _fact("2023-01-01", "2023-12-31", 800, "2024-02-20", "FY"),
    _fact("2023-01-01", "2023-09-30", 600, "2024-05-01", "Q3"),
]


def _q4(facts, period_end):
    return next(q for q in TTMCalculator(facts).quarterize() if q.period_end == period_end)


@pytest.mark.parametrize("order", ["as filed", "reversed"])
def test_derived_q4_does_not_depend_on_input_order(order):
    facts = ISSUE_FACTS if order == "as filed" else list(reversed(ISSUE_FACTS))
    q4 = _q4(facts, date(2023, 12, 31))
    # Before the fix: 50 (800 - original 750) as filed, 200 reversed.
    assert q4.numeric_value == 200
    assert q4.calculation_context == "derived_q4_fy_minus_ytd9"


def test_snowflake_recast_nine_months_is_paired_with_the_recast_year():
    """Snowflake EquitySecuritiesFvNiUnrealizedGainLoss, fiscal 2022 (company facts):

    nine months to 2021-10-31: 500,000 in 10-Q 0001640147-21-000271 (filed
    2021-12-03), recast to 8,515,000 in 10-Q 0001640147-22-000100 (2022-12-02);
    fiscal year to 2022-01-31: 5,400,000 in the original 10-K, recast to
    27,621,000 in 10-K 0001640147-23-000030 (2023-03-29).
    """
    facts = EntityFactsParser.parse_company_facts(json.loads(FIXTURE.read_text("utf-8")))
    concept_facts = [f for f in facts if f.concept.endswith("EquitySecuritiesFvNiUnrealizedGainLoss")]

    nine_months = {f.numeric_value for f in concept_facts
                   if f.period_start == date(2021, 2, 1) and f.period_end == date(2021, 10, 31)}
    assert nine_months == {500_000, 8_515_000}

    expected = 27_621_000 - 8_515_000
    # Before the fix: 27,121,000 (recast year minus the ORIGINAL nine months)
    # in fixture order, 19,106,000 reversed.
    assert _q4(concept_facts, date(2022, 1, 31)).numeric_value == expected
    assert _q4(list(reversed(concept_facts)), date(2022, 1, 31)).numeric_value == expected
