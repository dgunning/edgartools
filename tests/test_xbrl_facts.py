import pytest
from edgar import *
from unittest.mock import MagicMock

from edgar import Company, Filing
from edgar.xbrl import XBRL, FactsView
from edgar.xbrl.facts import FactQuery
from rich import print



@pytest.fixture(scope='module')
def intc_xbrl():
    filing = Filing(company='INTEL CORP', cik=50863, form='10-K', filing_date='2025-01-31', accession_no='0000050863-25-000009')
    filing.home.open()
    xbrl = XBRL.from_filing(filing)
    return xbrl


def test_total_number_of_facts():
    filing = find("0001756125-25-000627")
    xb = XBRL.from_filing(filing)


def test_get_all_facts(intc_xbrl: XBRL):
    facts_view: FactsView = intc_xbrl.facts
    assert facts_view

    # Check that each fact has a concept, a label and a value
    print()
    facts = facts_view.get_facts()
    fact = facts[0]
    assert 'concept' in fact
    assert 'label' in fact
    assert 'value' in fact


def test_get_facts_by_concept(intc_xbrl: XBRL):
    facts: FactsView = intc_xbrl.facts
    print()
    results = facts.query().by_concept('Revenue').to_dataframe()
    print(results)
    print(results.columns)


def test_get_facts_by_statement_type(intc_xbrl: XBRL):
    facts: FactsView = intc_xbrl.facts
    print()
    results = facts.query().by_statement_type('IncomeStatement').to_dataframe()
    print(results)
    assert not results.empty


def test_get_facts_by_label(intc_xbrl: XBRL):
    facts: FactsView = intc_xbrl.facts
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


def test_xbrl_query(intc_xbrl: XBRL):

    query = intc_xbrl.query(include_element_info=True)
    assert query._include_element_info

    query = intc_xbrl.query(include_element_info=False)
    assert query._include_element_info is False

    df = (intc_xbrl.query(include_element_info=False)
          .by_concept("Revenue").to_dataframe())

    assert not any(col in df.columns for col in ['element_id', 'element_name', 'element_type'])

    df = (intc_xbrl.query(include_dimensions=False)
          .by_concept("Revenue").to_dataframe())

    assert not any('dim' in col for col in df.columns)


def test_query_by_label_with_standardization():
    """Test querying facts by label when standardization is applied."""
    # Create a mock FactsView
    mock_facts_view = MagicMock(spec=FactsView)
    
    # Test facts including both standardized and original labels
    mock_facts = [
        {
            'concept': 'us-gaap_Revenue',
            'label': 'Revenue',  # Standardized label
            'original_label': 'Sales Revenue',  # Original company-specific label
            'numeric_value': 1000
        },
        {
            'concept': 'us-gaap_NetIncome',
            'label': 'Net Income',  # Standardized label
            'original_label': 'Net Profit',  # Original company-specific label
            'numeric_value': 500
        }
    ]
    
    # Set up the mock to return our test facts
    mock_facts_view.get_facts.return_value = mock_facts
    
    # Create a query using by_label to search for original label
    query = FactQuery(mock_facts_view).by_label("Sales Revenue", exact=True)
    results = query.execute()
    
    # Verify we find the fact by its original label
    assert len(results) == 1
    assert results[0]['concept'] == 'us-gaap_Revenue'
    assert results[0]['original_label'] == 'Sales Revenue'
    
    # Create a query using by_label to search for standardized label
    query = FactQuery(mock_facts_view).by_label("Revenue", exact=True)
    results = query.execute()
    
    # Verify we find the fact by its standardized label
    assert len(results) == 1
    assert results[0]['concept'] == 'us-gaap_Revenue'
    assert results[0]['label'] == 'Revenue'
    
    # Create a query using by_label with regex pattern matching
    query = FactQuery(mock_facts_view).by_label("profi", exact=False)
    results = query.execute()
    
    # Verify we find the fact by partial match on original label
    assert len(results) == 1
    assert results[0]['concept'] == 'us-gaap_NetIncome'
    assert results[0]['original_label'] == 'Net Profit'

def test_integration_standardization_and_facts_query(intc_xbrl):
    """Integration test for standardization and facts query working together."""
    # Save the count of facts before standardization
    initial_facts_count = len(intc_xbrl.facts)
    
    # First, capture some of the original labels before standardization
    # Get "Revenue" related facts with the original label
    revenue_facts_before = intc_xbrl.query().by_concept("Revenue", exact=False).execute()
    
    # Store original labels for later comparison
    original_revenue_labels = []
    for fact in revenue_facts_before:
        if 'label' in fact and fact['label']:
            original_revenue_labels.append(fact['label'])
    
    # Now render a standardized statement
    statement = intc_xbrl.render_statement("IncomeStatement", standard=True)
    print()
    print(statement)
    
    # Extract standardized labels from the rendered statement
    import re
    statement_str = str(statement)
    # Look for lines that might contain standardized labels (like "Revenue")
    statement_lines = statement_str.split('\n')
    possible_labels = []
    for line in statement_lines:
        # Skip lines with table formatting characters or headers
        if '─' in line or 'INCOME STATEMENT' in line or '(Standardized)' in line:
            continue
        # Extract the potential label text (content before any pipe character)
        if '│' in line:
            label_text = line.split('│')[0].strip()
            if label_text and any(c.isalpha() for c in label_text):
                possible_labels.append(label_text)
    
    # Verify facts count is the same after standardization (no duplication)
    assert len(intc_xbrl.facts) == initial_facts_count, "Facts count changed after standardization"
    
    # Now query the facts both by standardized label and original label
    # Example: Search for "Revenue" which is standardized from labels like "Net Sales" or "Total Revenue"
    results_standard = intc_xbrl.query().by_label("Revenue", exact=True).execute()
    
    # If we have results, there should be at least one fact that matches
    if results_standard:
        # Check each revenue fact found by standardized label
        for fact in results_standard:
            # Verify it has both the standardized label and the original label
            assert fact['label'] == "Revenue", "Label was not properly standardized"
            assert 'original_label' in fact, "Original label not preserved"
            
            # Get the original label of the fact
            original_label = fact['original_label']
            
            # Now query by the original label and verify we find the same fact
            results_original = intc_xbrl.facts.query().by_label(original_label, exact=True).execute()
            
            # Should find at least one fact by original label
            assert len(results_original) > 0, f"Failed to find facts by original label: {original_label}"
            
            # The concept should match between the two queries
            # Find the matching fact by concept
            matching_facts = [f for f in results_original if f['concept'] == fact['concept']]
            assert len(matching_facts) > 0, f"Could not find matching fact for concept {fact['concept']}"
    
    # Test that we can query using labels seen in the rendered statement
    # Try at least 2 labels from the statement if possible
    import random
    test_labels = []
    if len(possible_labels) >= 2:
        test_labels = random.sample(possible_labels, 2)
    elif possible_labels:
        test_labels = [possible_labels[0]]
    
    for test_label in test_labels:
        # Try to query by this label
        results = intc_xbrl.facts.query().by_label(test_label, exact=True).execute()
        print(f"Testing displayed label: {test_label}, found {len(results)} facts")
        
        # We should find at least one fact with this label
        assert len(results) > 0, f"Failed to find facts by statement label: {test_label}"