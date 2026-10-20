"""Regression test for bead edgartools-jrqvs.

Financials.get_revenue() reads the filed total, us-gaap:Revenues, before
contract revenue (gh #1294). The EntityFacts side ranked contract revenue
(RevenueFromContractWithCustomerExcludingAssessedTax) first and only gave way
to a total at least 2x larger (edgartools-fdye). Contract revenue can be one
component of the total, or a note figure that is not on the face statement at
all, so the facts path under-reported every filer whose total was within 2x.
It disagreed with the XBRL path for the same filing.

Ground truth, us-gaap facts from each FY2025 10-K (SEC companyfacts), checked
against each face income statement, where the total is the Revenues fact:

  GM   0001467858-26-000013  Revenues 185,019M "Total net sales and revenue"
                             contract 167,971M "Automotive" (a face component)
  COP  0001163165-26-000009  Revenues  58,944M "Sales and other operating revenues"
                             contract  51,824M (note only)
  WMB  0000107263-26-000006  Revenues  11,950M "Revenues"
                             contract  14,899M (note only, and LARGER)

Williams rules out "take the larger figure": the rule is Revenues first.
Over 106 large filers, 15 tag both concepts for the same FY. 3 tag the same
value, MET and AMT were already caught by the 2x rule, and the other 10 move
to their face total.
"""
from datetime import date

import pytest

from edgar.entity.entity_facts import EntityFacts
from edgar.entity.models import DataQuality, FinancialFact


def _fy_fact(concept, value):
    return FinancialFact(
        concept=f'us-gaap:{concept}',
        taxonomy='us-gaap',
        label=concept,
        value=value,
        numeric_value=value,
        unit='USD',
        scale=1,
        period_start=date(2025, 1, 1),
        period_end=date(2025, 12, 31),
        period_type='duration',
        fiscal_year=2025,
        fiscal_period='FY',
        filing_date=date(2026, 2, 3),
        accession='0001467858-26-000013',
        form_type='10-K',
        statement_type='IncomeStatement',
        data_quality=DataQuality.HIGH,
    )


def _facts(**values):
    facts = [_fy_fact(concept, value) for concept, value in values.items()]
    return EntityFacts(cik=1467858, name='Test Co', facts=facts)


@pytest.mark.fast
@pytest.mark.parametrize("contract,total", [
    (167_971_000_000, 185_019_000_000),   # GM: contract revenue is a face component
    (14_899_000_000, 11_950_000_000),     # WMB: contract revenue exceeds the total
])
def test_revenues_wins_over_contract_revenue_in_the_same_period(contract, total):
    facts = _facts(RevenueFromContractWithCustomerExcludingAssessedTax=contract, Revenues=total)

    assert facts.get_revenue() == total
    assert facts.get_revenue_detailed().value == total


@pytest.mark.fast
def test_a_contract_only_filer_still_resolves():
    """Apple, Microsoft and most retailers tag only contract revenue."""
    facts = _facts(RevenueFromContractWithCustomerExcludingAssessedTax=416_161_000_000)

    assert facts.get_revenue() == 416_161_000_000


@pytest.mark.fast
def test_get_revenue_detailed_applies_the_consolidated_total_rule():
    """get_revenue_detailed() is the same lookup and must not drop the fdye rule."""
    import inspect

    assert 'prefer_consolidated_total=True' in inspect.getsource(EntityFacts.get_revenue_detailed)


@pytest.mark.fast
def test_every_revenue_priority_list_starts_with_the_filed_total():
    """The copies of the revenue order must agree, or the two paths disagree again."""
    from edgar.entity.enhanced_statement import _REVENUE_CONCEPTS
    from edgar.entity.entity_facts import _REVENUE_VARIANTS
    from edgar.standardization import get_synonym_groups

    assert _REVENUE_CONCEPTS[0] == 'Revenues'
    assert _REVENUE_VARIANTS[0] == 'Revenues'
    assert get_synonym_groups().get_group('revenue').synonyms[0] == 'Revenues'


@pytest.mark.network
@pytest.mark.regression
@pytest.mark.parametrize("ticker,expected", [
    ("GM", 185_019_000_000),    # was 167,971,000,000
    ("COP", 58_944_000_000),    # was 51,824,000,000
    ("WMB", 11_950_000_000),    # was 14,899,000,000
])
def test_facts_revenue_matches_the_face_total(ticker, expected):
    from edgar import Company

    company = Company(ticker)
    facts = company.get_facts()
    assert facts.get_revenue() == expected

    df = facts.income_statement(annual=True, periods=1).to_dataframe()
    period_column = [c for c in df.columns if c.startswith('FY ')][0]
    revenue_row = df[df['label'] == 'Total Revenue']
    assert revenue_row.iloc[0][period_column] == expected
