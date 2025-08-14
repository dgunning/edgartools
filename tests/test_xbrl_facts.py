import pytest
from edgar import *
from unittest.mock import MagicMock

from edgar import Company, Filing
from edgar.xbrl import XBRL, FactsView
from edgar.xbrl.facts import FactQuery
from rich import print
import pandas as pd

pd.options.display.max_rows = 1000


@pytest.fixture(scope='module')
def intc_xbrl():
    filing = Filing(company='INTEL CORP', cik=50863, form='10-K', filing_date='2025-01-31', accession_no='0000050863-25-000009')
    xbrl = XBRL.from_filing(filing)
    return xbrl

@pytest.fixture(scope='module')
def aapl_xbrl():
    f = Filing(company='Apple Inc.', cik=320193, form='10-K', filing_date='2024-11-01',
               accession_no='0000320193-24-000123')
    return f.xbrl()


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
    assert len(results) == 51

    # Test with full concept name
    results_full = facts.query().by_concept('us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax').to_dataframe()
    assert len(results_full) == 48
    assert results_full.concept.drop_duplicates().to_list()[0] == 'us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax'

    # Test with a concept with '_' in the name instead of ':'
    results_underscore = facts.query().by_concept('us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax').to_dataframe()
    assert len(results_underscore) == 48
    assert results_underscore.concept.drop_duplicates().to_list()[0] == 'us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax'



def test_get_facts_by_statement_type(intc_xbrl: XBRL):
    facts: FactsView = intc_xbrl.facts
    print()
    results = facts.query().by_statement_type('IncomeStatement').to_dataframe()
    #print(results)
    print(results.columns)
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


def test_xbrl_facts_repr(intc_xbrl):
    query = intc_xbrl.query().by_concept("us-gaap:Assets")
    print()
    query_repr = repr(query)
    print(query_repr)
    #assert "us-gaap:Assets" in query_repr

def test_facts_to_dataframe_has_correct_columns(aapl_xbrl):
    revenue_query = aapl_xbrl.query().by_concept("us-gaap:Revenues")
    df = revenue_query.to_dataframe()
    columns = df.columns.tolist()
    # Assert that the columns are unique and not duplicated
    assert len(columns) == len(set(columns)), "Columns are duplicated in the DataFrame"


def test_query_by_dimension(aapl_xbrl):
    # Test querying by dimension
    facts = (aapl_xbrl
             .query()
             .by_text("Revenue")
             .by_dimension(dimension='us-gaap_StatementBusinessSegmentsAxis', value='aapl:AmericasSegmentMember')
             )
    df = facts.to_dataframe('concept', 'label', 'value', 'dim_us-gaap_StatementBusinessSegmentsAxis')
    print(df)
    assert len(df) == 3

def test_query_by_dimension_none(aapl_xbrl):
    # Test querying by dimension
    facts = (aapl_xbrl
             .query()
             .by_text("Revenue")
             )
    assert any('dim' in col for col in facts.to_dataframe().columns)
    facts = (aapl_xbrl
             .query()
             .by_text("Revenue")
             .by_dimension(None)
             )
    print(facts.to_dataframe().columns.tolist())
    assert not any('dim' in col for col in facts.to_dataframe().columns)


def test_flexible_dimension_matching(aapl_xbrl):
    """Test the improved flexible dimension matching functionality."""
    
    # First, find available dimensions in the data
    sample_facts = aapl_xbrl.query().limit(100).execute()
    dimensions = {}
    
    for fact in sample_facts:
        for key, value in fact.items():
            if key.startswith('dim_'):
                dim_name = key[4:]  # Remove 'dim_' prefix
                if dim_name not in dimensions:
                    dimensions[dim_name] = set()
                if value:
                    dimensions[dim_name].add(value)
    
    # Skip test if no dimensions are available
    if not dimensions:
        pytest.skip("No dimensions found in test data")
    
    # Pick the first dimension with values for testing
    test_dim = None
    test_values = []
    for dim_name, values in dimensions.items():
        if values:
            test_dim = dim_name
            test_values = list(values)
            break
    
    if not test_dim or not test_values:
        pytest.skip("No suitable dimensions with values found for testing")
    
    test_value = test_values[0]
    
    print(f"\nTesting with dimension: {test_dim}")
    print(f"Testing with value: {test_value}")
    
    # Test 1: Original format (exact match)
    results_exact = aapl_xbrl.query().by_dimension(test_dim, test_value).limit(10).execute()
    original_count = len(results_exact)
    
    assert original_count > 0, f"No results for exact dimension match: {test_dim} = {test_value}"
    
    # Test 2: Dimension name with colon instead of underscore
    dim_with_colon = test_dim.replace('_', ':')
    if dim_with_colon != test_dim:
        results_colon_dim = aapl_xbrl.query().by_dimension(dim_with_colon, test_value).limit(10).execute()
        assert len(results_colon_dim) == original_count, \
            f"Different results for dimension format variation: {dim_with_colon}"
    
    # Test 3: Value with underscore instead of colon (and vice versa)
    if ':' in test_value:
        value_with_underscore = test_value.replace(':', '_')
        results_underscore_val = aapl_xbrl.query().by_dimension(test_dim, value_with_underscore).limit(10).execute()
        assert len(results_underscore_val) == original_count, \
            f"Different results for value format variation: {value_with_underscore}"
    elif '_' in test_value:
        value_with_colon = test_value.replace('_', ':')
        results_colon_val = aapl_xbrl.query().by_dimension(test_dim, value_with_colon).limit(10).execute()
        assert len(results_colon_val) == original_count, \
            f"Different results for value format variation: {value_with_colon}"
    
    # Test 4: Local dimension name (without namespace prefix)
    if '_' in test_dim:
        local_dim = test_dim.split('_')[-1]
        results_local_dim = aapl_xbrl.query().by_dimension(local_dim, test_value).limit(10).execute()
        assert len(results_local_dim) == original_count, \
            f"Different results for local dimension name: {local_dim}"
    
    # Test 5: Local value name (without namespace prefix)  
    if ':' in test_value:
        local_value = test_value.split(':')[-1]
        results_local_val = aapl_xbrl.query().by_dimension(test_dim, local_value).limit(10).execute()
        assert len(results_local_val) == original_count, \
            f"Different results for local value name: {local_value}"
    
    # Test 6: Dimension existence (without specifying value)
    results_exists = aapl_xbrl.query().by_dimension(test_dim).limit(20).execute()
    assert len(results_exists) >= original_count, \
        "Dimension existence filter should return at least as many results as specific value filter"
    
    # Test 7: Verify that all returned facts actually have the expected dimension
    for fact in results_exact:
        found_dim = False
        for key, value in fact.items():
            if key.startswith('dim_') and key == f'dim_{test_dim}':
                assert value == test_value, \
                    f"Fact has wrong dimension value. Expected: {test_value}, Got: {value}"
                found_dim = True
                break
        assert found_dim, f"Fact missing expected dimension: dim_{test_dim}"
    
    print(f"✅ All flexible dimension matching tests passed!")
    print(f"   Original exact match: {original_count} results")
    print(f"   All format variations returned same count")


def test_dimension_format_normalization():
    """Test the dimension format normalization helper methods."""
    from edgar.xbrl.facts import FactQuery
    from unittest.mock import MagicMock
    
    # Create a mock FactsView for testing
    mock_facts_view = MagicMock()
    query = FactQuery(mock_facts_view)
    
    # Test dimension key normalization
    assert query._normalize_dimension_key("us-gaap:ProductAxis") == "us-gaap_ProductAxis"
    assert query._normalize_dimension_key("us-gaap_ProductAxis") == "us-gaap_ProductAxis"
    assert query._normalize_dimension_key("ProductAxis") == "ProductAxis"
    
    # Test dimension value normalization  
    assert query._normalize_dimension_value("us-gaap_ServiceMember") == "us-gaap:ServiceMember"
    assert query._normalize_dimension_value("us-gaap:ServiceMember") == "us-gaap:ServiceMember"
    assert query._normalize_dimension_value("ServiceMember") == "ServiceMember"
    
    # Test dimension key matching
    assert query._dimension_key_matches("dim_us-gaap_ProductAxis", "us-gaap:ProductAxis")
    assert query._dimension_key_matches("dim_us-gaap_ProductAxis", "us-gaap_ProductAxis") 
    assert query._dimension_key_matches("dim_us-gaap_ProductAxis", "ProductAxis")
    assert not query._dimension_key_matches("dim_us-gaap_ProductAxis", "ServiceAxis")
    
    # Test dimension value matching
    assert query._dimension_value_matches("us-gaap:ServiceMember", "us-gaap_ServiceMember")
    assert query._dimension_value_matches("us-gaap:ServiceMember", "us-gaap:ServiceMember")
    assert query._dimension_value_matches("us-gaap:ServiceMember", "ServiceMember")
    assert not query._dimension_value_matches("us-gaap:ServiceMember", "ProductMember")
    
    print("✅ All dimension normalization tests passed!")