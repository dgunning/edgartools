"""EntityFacts must not return continuing operating cash as a company-wide total.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1987
"""
from datetime import date

import pytest

from edgar.entity.entity_facts import EntityFacts
from edgar.entity.models import FinancialFact

pytestmark = [pytest.mark.fast, pytest.mark.regression]

TOTAL = "NetCashProvidedByUsedInOperatingActivities"
CONTINUING = TOTAL + "ContinuingOperations"
DISCONTINUED = "CashProvidedByUsedInOperatingActivitiesDiscontinuedOperations"


def _fact(concept, value, start=date(2024, 10, 1)):
    return FinancialFact(
        concept=f"us-gaap:{concept}", taxonomy="us-gaap", label=concept,
        value=value, numeric_value=float(value), unit="USD",
        period_start=start, period_end=date(2025, 9, 30), period_type="duration",
        fiscal_year=2025, fiscal_period="FY", filing_date=date(2025, 12, 22),
        form_type="10-K", statement_type="CashFlowStatement",
    )


@pytest.mark.parametrize("period", ["2025-FY", None])
def test_sifco_continuing_operating_cash_is_not_the_total(period):
    # SIFCO FY2025 10-K (0001628280-25-058405) reports these two amounts separately.
    facts = EntityFacts(90168, "SIFCO Industries", [
        _fact(CONTINUING, 127_000), _fact(DISCONTINUED, 5_000),
    ])

    assert facts.get_fact(f"us-gaap:{CONTINUING}", period).numeric_value == 127_000
    assert facts.get_concept("operating_cash_flow", period=period) is None
    assert facts.get_concept("operating_cash_flow", period=period, return_metadata=True) is None


@pytest.mark.parametrize("extra_facts,expected", [
    ([_fact(TOTAL, 132_000), _fact(DISCONTINUED, 5_000)], 132_000),
    ([], 127_000),
    ([_fact(DISCONTINUED, 0)], 127_000),
    ([_fact(DISCONTINUED, 5_000, start=date(2025, 7, 1))], 127_000),
])
def test_reported_total_wins_and_only_matching_nonzero_discontinued_cash_blocks_fallback(
    extra_facts, expected,
):
    facts = EntityFacts(90168, "SIFCO Industries", [_fact(CONTINUING, 127_000), *extra_facts])

    assert facts.get_concept("operating_cash_flow", period="2025-FY") == expected
