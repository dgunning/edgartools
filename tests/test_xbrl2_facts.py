from edgar.xbrl2 import XBRL, FactQuery, FactsView
from edgar import Company
import pytest

@pytest.fixture(scope='module')
def intc_xbrl():
    c = Company("INTC")
    filing = c.latest("10-K")
    xbrl = XBRL.from_filing(filing)
    return xbrl

def test_get_all_facts(intc_xbrl:XBRL):
    facts_view:FactsView = intc_xbrl.facts_view
    assert facts_view

    # Check that each fact has a concept, a label and a value
    print()
    facts = facts_view.get_facts()
    fact = facts[0]
    assert 'concept' in fact
    assert 'label' in fact
    assert 'value' in fact


def test_get_facts_by_concept(intc_xbrl:XBRL):
    facts:FactsView = intc_xbrl.facts_view
    print()
    results = facts.query().by_concept('Revenue').to_dataframe()
    print(results)
    print(results.columns)

def test_get_facts_by_statement_type(intc_xbrl:XBRL):
    facts:FactsView = intc_xbrl.facts_view
    print()
    results = facts.query().by_statement_type('IncomeStatement').to_dataframe()
    print(results)
    assert not results.empty


def test_get_facts_by_label(intc_xbrl:XBRL):
    facts:FactsView = intc_xbrl.facts_view
    print()
    print(intc_xbrl.statements.income_statement())
    results = facts.query().by_label('Revenue').to_dataframe()
    print(results)
    assert not results.empty