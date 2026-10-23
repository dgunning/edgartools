"""Year-over-year revenue growth was computed from unaligned fact rows.

``EntityFacts._analyze_growth`` (the ``to_llm_context`` growth focus) and the MCP
``edgar_compare`` growth metric took the first two rows of
``time_series('Revenue')``: whatever concepts the substring matched
(``ContractWithCustomerLiabilityRevenueRecognized``, deferred revenue), in any unit,
period length or order. Snowflake's Q1 FY2026 read -17.96% against a filed +25.75%.

Growth now compares one concept, one unit and one period length (a quarter or a
year), with the prior period ending a year before the latest one, and says it is not
available when no such pair exists.

Ground truth: Snowflake 10-Q 0001640147-25-000110 (filed 2025-05-30), revenue
(us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax) of $1,042,074,000 for
the quarter ended 2025-04-30 against $828,709,000 a year earlier, read from the
filing's XBRL: +25.75%. The tracked fixture ``tests/fixtures/entity/snow_facts.json``
is Snowflake's SEC company facts, so this runs offline.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1671
"""

import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from edgar.ai.mcp.tools import compare as compare_tool
from edgar.entity.entity_facts import EntityFacts
from edgar.entity.models import DataQuality, FinancialFact
from edgar.entity.parser import EntityFactsParser

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "entity" / "snow_facts.json"
REVENUE = 'us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax'


def _fact(concept, value, start, end, unit='USD', filed=date(2025, 8, 1), fp='Q2'):
    return FinancialFact(
        concept=concept, taxonomy=concept.split(':')[0], label=concept, value=value,
        numeric_value=value, unit=unit, scale=1, period_start=start, period_end=end,
        period_type='duration', fiscal_year=2025, fiscal_period=fp, filing_date=filed,
        accession='0000000000-25-000001', form_type='10-Q', data_quality=DataQuality.HIGH,
    )


def _facts(*facts):
    return EntityFacts(cik=1, name='Test Corp', facts=list(facts))


@pytest.fixture(scope="module")
def snowflake():
    return EntityFactsParser.parse_company_facts(json.loads(FIXTURE.read_text("utf-8")))


@pytest.mark.fast
def test_snowflake_quarter_matches_the_filed_growth(snowflake):
    growth = snowflake.to_llm_context(focus_areas=["growth"])["focus_analysis"]["growth"]
    yoy = growth["revenue_growth_yoy"]
    assert yoy["value"] == 25.75
    assert yoy["concept"] == REVENUE
    assert yoy["period_comparison"] == "quarter ended 2025-04-30 vs quarter ended 2024-04-30"

    raw = snowflake._revenue_growth_yoy()
    assert (raw["current"], raw["prior"]) == (1_042_074_000, 828_709_000)


@pytest.mark.fast
def test_other_concepts_and_period_lengths_are_not_paired():
    """Deferred-revenue release and a six-month YTD window used to be the first rows."""
    facts = _facts(
        _fact('us-gaap:ContractWithCustomerLiabilityRevenueRecognized', 479.0,
              date(2025, 1, 27), date(2025, 7, 27)),
        _fact('us-gaap:ContractWithCustomerLiabilityRevenueRecognized', 758.0,
              date(2024, 1, 29), date(2024, 7, 28)),
        _fact(REVENUE, 1800.0, date(2025, 1, 27), date(2025, 7, 27)),   # six months
        _fact(REVENUE, 1000.0, date(2025, 4, 28), date(2025, 7, 27)),
        _fact(REVENUE, 800.0, date(2024, 4, 29), date(2024, 7, 28)),
    )
    growth = facts._revenue_growth_yoy()
    assert growth["value"] == 25.0
    assert growth["duration"] == "quarterly"


@pytest.mark.fast
def test_rows_are_compared_in_chronological_order_whatever_the_filing_order():
    """Microsoft's fiscal 2024 and 2025 came out reversed; filing order is not period order."""
    facts = _facts(
        _fact(REVENUE, 281_724.0, date(2024, 7, 1), date(2025, 6, 30), filed=date(2026, 7, 30), fp='FY'),
        _fact(REVENUE, 331_839.0, date(2025, 7, 1), date(2026, 6, 30), filed=date(2026, 7, 30), fp='FY'),
        _fact(REVENUE, 245_122.0, date(2023, 7, 1), date(2024, 6, 30), filed=date(2026, 7, 30), fp='FY'),
    )
    assert facts._revenue_growth_yoy(annual_only=True)["value"] == 17.79


@pytest.mark.fast
def test_one_amount_in_two_currencies_and_no_prior_year_is_not_available():
    """Palatin: 8,830,000 USD and 7,500,000 EUR are one amount; fiscal 2025 had no revenue."""
    facts = _facts(
        _fact('us-gaap:Revenues', 8_830_000.0, date(2025, 7, 1), date(2026, 6, 30), fp='FY'),
        _fact('us-gaap:Revenues', 7_500_000.0, date(2025, 7, 1), date(2026, 6, 30), unit='EUR', fp='FY'),
        _fact(REVENUE, 13_185_031.0, date(2025, 7, 1), date(2026, 6, 30), fp='FY'),
    )
    assert facts._revenue_growth_yoy() is None
    growth = facts.to_llm_context(focus_areas=["growth"])["focus_analysis"]["growth"]
    assert "revenue_growth_yoy" not in growth
    assert "not available" in growth["message"]


@pytest.mark.fast
def test_growth_from_nil_prior_revenue_is_not_available():
    facts = _facts(
        _fact(REVENUE, 500.0, date(2025, 7, 1), date(2026, 6, 30), fp='FY'),
        _fact(REVENUE, 0.0, date(2024, 7, 1), date(2025, 6, 30), fp='FY'),
    )
    assert facts._revenue_growth_yoy() is None


@pytest.mark.fast
@pytest.mark.asyncio
async def test_compare_tool_uses_aligned_growth(snowflake, monkeypatch):
    company = SimpleNamespace(name='Snowflake Inc.', cik=1640147, get_facts=lambda: snowflake)
    monkeypatch.setattr(compare_tool, "resolve_company", lambda identifier: company)

    annual = await compare_tool._compare_company('SNOW', ['growth'], 3, annual=True)
    assert annual["metrics"]["revenue_growth_yoy"] == "29.2%"     # FY2025 3,626,396 vs 2,806,489 thousand
    assert annual["metrics"]["revenue_growth_period"] == "2025-01-31 vs 2024-01-31"

    quarterly = await compare_tool._compare_company('SNOW', ['growth'], 3, annual=False)
    assert quarterly["metrics"]["revenue_growth_yoy"] == "25.8%"


@pytest.mark.fast
@pytest.mark.asyncio
async def test_compare_tool_says_not_available(monkeypatch):
    facts = _facts(_fact(REVENUE, 13_185_031.0, date(2025, 7, 1), date(2026, 6, 30), fp='FY'))
    company = SimpleNamespace(name='Test Corp', cik=1, get_facts=lambda: facts)
    monkeypatch.setattr(compare_tool, "resolve_company", lambda identifier: company)

    result = await compare_tool._compare_company('TEST', ['growth'], 3, annual=True)
    assert result["metrics"]["revenue_growth_yoy"] == "not available"
