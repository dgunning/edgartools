"""
Regression test for edgartools-885h: the component fallback answered a request
for one unit with a figure in another.

When the unit filter correctly rejected every candidate fact,
`_get_standardized_concept_value` fell through to its component calculation, and
that calculation checked the two components against EACH OTHER — which
establishes only that they can be added — before normalising with no target unit
at all. Any request the unit filter had just rejected came back as a USD sum.

    get_revenue(unit='EUR')     -> GrossProfit + CostOfGoodsAndServicesSold, in USD
    get_revenue(unit='shares')  -> the same figure

This was latent until bare concept names were indexed (GH #1202, same release):
before that, `get_fact('GrossProfit')` returned None, the components were never
found, and the fallback returned None for the wrong reason. The three tests that
caught it live in the network lane, so it never showed in `test-fast`. These are
offline and do.
"""

from datetime import date

import pytest

from edgar.entity.entity_facts import EntityFacts
from edgar.entity.models import FinancialFact

GROSS_PROFIT = 60_000_000.0
COST_OF_GOODS = 40_000_000.0


def _fact(concept: str, value: float, unit: str = "USD") -> FinancialFact:
    return FinancialFact(
        concept=f"us-gaap:{concept}",
        taxonomy="us-gaap",
        label=concept,
        value=value,
        numeric_value=value,
        unit=unit,
        period_type="duration",
        period_start=date(2024, 1, 1),
        period_end=date(2024, 12, 31),
        fiscal_year=2024,
        fiscal_period="FY",
        filing_date=date(2025, 2, 1),
        form_type="10-K",
        statement_type="IncomeStatement",
    )


@pytest.fixture
def facts_without_revenue() -> EntityFacts:
    """
    A company that tags no revenue concept at all, only its two components.

    That is what forces `get_revenue()` down the fallback path — the path where
    the unit was being dropped.
    """
    return EntityFacts(
        cik=123456,
        name="Test Company Inc.",
        facts=[
            _fact("GrossProfit", GROSS_PROFIT),
            _fact("CostOfGoodsAndServicesSold", COST_OF_GOODS),
        ],
    )


def test_the_fallback_still_answers_the_default_unit(facts_without_revenue):
    """
    The control. With no revenue concept tagged, revenue is the sum of the two
    components — this is the behaviour the fallback exists to provide, and it
    must survive the fix.
    """
    assert facts_without_revenue.get_revenue() == GROSS_PROFIT + COST_OF_GOODS


def test_an_incompatible_unit_is_not_answered_in_dollars(facts_without_revenue):
    """
    `shares` is not a currency. The components are both USD, so no figure here
    answers the question and the right answer is None.
    """
    assert facts_without_revenue.get_revenue(unit="shares") is None


def test_a_different_currency_is_not_answered_in_dollars(facts_without_revenue):
    """
    EUR is *compatible* with USD — same unit type — which is exactly why the old
    check passed it. Compatibility is not equality, and an explicitly requested
    unit is a strict request: returning a USD figure would be wrong by a factor
    of the exchange rate, silently.
    """
    assert facts_without_revenue.get_revenue(unit="EUR") is None


def test_the_requested_unit_is_answered_when_it_matches(facts_without_revenue):
    """Asking for the unit the components are actually in still works."""
    assert facts_without_revenue.get_revenue(unit="USD") == GROSS_PROFIT + COST_OF_GOODS


def test_gross_profit_carried_the_same_defect():
    """
    `_calculate_gross_profit_from_components` had the identical branch, so it
    would have surfaced the same way once a filer tagged revenue and cost but
    not gross profit.
    """
    facts = EntityFacts(
        cik=123456,
        name="Test Company Inc.",
        facts=[
            _fact("Revenues", 100_000_000.0),
            _fact("CostOfGoodsAndServicesSold", COST_OF_GOODS),
        ],
    )

    assert facts.get_gross_profit() == 60_000_000.0
    assert facts.get_gross_profit(unit="shares") is None
    assert facts.get_gross_profit(unit="EUR") is None
