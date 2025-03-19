import pytest

from edgar import Company, Filing
from edgar.xbrl2 import XBRL, FactsView


@pytest.fixture(scope='module')
def intc_xbrl():
    c = Company("INTC")
    filing = c.latest("10-K")
    xbrl = XBRL.from_filing(filing)
    return xbrl


def test_get_all_facts(intc_xbrl: XBRL):
    facts_view: FactsView = intc_xbrl.facts_view
    assert facts_view

    # Check that each fact has a concept, a label and a value
    print()
    facts = facts_view.get_facts()
    fact = facts[0]
    assert 'concept' in fact
    assert 'label' in fact
    assert 'value' in fact


def test_get_facts_by_concept(intc_xbrl: XBRL):
    facts: FactsView = intc_xbrl.facts_view
    print()
    results = facts.query().by_concept('Revenue').to_dataframe()
    print(results)
    print(results.columns)


def test_get_facts_by_statement_type(intc_xbrl: XBRL):
    facts: FactsView = intc_xbrl.facts_view
    print()
    results = facts.query().by_statement_type('IncomeStatement').to_dataframe()
    print(results)
    assert not results.empty


def test_get_facts_by_label(intc_xbrl: XBRL):
    facts: FactsView = intc_xbrl.facts_view
    print()
    print(intc_xbrl.statements.income_statement())
    results = facts.query().by_label('Revenue').to_dataframe()
    print(results)
    assert not results.empty


def test_numeric_sign_for_cashflow_values():
    filing = Filing(company='Corsair Gaming, Inc.', cik=1743759, form='10-K', filing_date='2025-02-26',
                    accession_no='0000950170-25-027856')
    xbrl: XBRL = XBRL.from_filing(filing)

    inventory_facts = (xbrl
                       .facts_view
                       .query()
                       .by_concept("us-gaap:IncreaseDecreaseInInventories").to_dataframe()
                       .filter(['concept',  'period_end',  'value', 'numeric_value'])
                       )
    print(inventory_facts)
    assert inventory_facts[inventory_facts.period_end=='2024-12-31']['value'].values[0] == '18315000'
    assert inventory_facts[inventory_facts.period_end == '2024-12-31']['numeric_value'].values[0] == 18315000

    assert inventory_facts[inventory_facts.period_end == '2023-12-31']['value'].values[0] == '-39470000'
    assert inventory_facts[inventory_facts.period_end == '2023-12-31']['numeric_value'].values[0] == -39470000

    assert inventory_facts[inventory_facts.period_end == '2022-12-31']['value'].values[0] == '111288000'
    assert inventory_facts[inventory_facts.period_end == '2022-12-31']['numeric_value'].values[0] == 111288000
