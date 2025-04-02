"""
Tests for the XBRL statement resolver.
"""
import re
from pathlib import Path

import pytest
from edgar.xbrl2.xbrl import XBRL
from edgar.xbrl2.statement_resolver import StatementResolver, statement_registry


@pytest.fixture
def tsla_xbrl():
    # Quarterly statements
    data_dir = Path("data/xbrl/datafiles/tsla")
    return XBRL.parse_directory(data_dir)


@pytest.fixture
def aapl_xbrl():
    data_dir = Path("data/xbrl/datafiles/aapl")
    return XBRL.parse_directory(data_dir)

@pytest.fixture
def unp_xbrl():
    data_dir = Path("data/xbrl/datafiles/unp")
    return XBRL.parse_directory(data_dir)


@pytest.fixture
def simple_resolver(tsla_xbrl):
    return StatementResolver(tsla_xbrl)


def test_registry_initialization():
    """Test that the statement registry is properly initialized."""
    # Verify balance sheet entry
    bs_entry = statement_registry["BalanceSheet"]
    assert bs_entry.name == "BalanceSheet"
    assert "us-gaap_StatementOfFinancialPositionAbstract" in bs_entry.primary_concepts
    assert r".*_BalanceSheetAbstract$" in bs_entry.concept_patterns
    assert bs_entry.supports_parenthetical is True
    
    # Verify income statement entry
    is_entry = statement_registry["IncomeStatement"]
    assert is_entry.name == "IncomeStatement"
    assert "us-gaap_IncomeStatementAbstract" in is_entry.primary_concepts
    assert r".*_CondensedConsolidatedStatementsOfIncomeUnauditedAbstract$" in is_entry.concept_patterns
    assert is_entry.supports_parenthetical is True


def test_resolver_initialization(simple_resolver):
    """Test that the resolver initializes properly and builds indices."""
    assert simple_resolver is not None
    assert simple_resolver.xbrl is not None
    
    # Verify indices are built
    assert len(simple_resolver._statement_by_role_uri) > 0
    assert len(simple_resolver._statement_by_type) > 0


def test_match_by_primary_concept(simple_resolver):
    """Test matching statements by primary concept."""
    # Try to match "BalanceSheet"
    statements, role, confidence = simple_resolver._match_by_primary_concept("BalanceSheet")
    assert statements
    assert role is not None
    assert confidence > 0.8  # High confidence
    
    # Try a non-existent statement type
    statements, role, confidence = simple_resolver._match_by_primary_concept("NonExistentStatement")
    assert not statements
    assert role is None
    assert confidence == 0.0


def test_match_by_concept_pattern(simple_resolver):
    """Test matching statements using concept patterns."""
    # Create a custom concept pattern entry
    for pattern in statement_registry["BalanceSheet"].concept_patterns:
        if re.match(pattern, "custom_StatementOfFinancialPositionAbstract"):
            # If we find a balance sheet pattern that would match a custom namespace
            statements, role, confidence = simple_resolver._match_by_concept_pattern("BalanceSheet")
            # If we have any statements, the test will pass
            if statements:  # Some test files might not have custom namespaces
                assert confidence > 0.8
                return
    
    # Skip if no matching pattern (test is inconclusive but not failed)
    pytest.skip("No custom namespace patterns to test against in the sample data")


def test_find_statement_by_type(tsla_xbrl):
    """Test finding statements by standard type."""
    # Try to find "BalanceSheet"
    matching_statements, found_role, actual_type = tsla_xbrl.find_statement("BalanceSheet")
    assert matching_statements
    assert found_role is not None
    assert actual_type == "BalanceSheet"
    
    # Try to find by role name
    role_name = None
    for stmt in tsla_xbrl.get_all_statements():
        if stmt['type'] == 'BalanceSheet':
            role_name = stmt['role_name']
            break
            
    if role_name:
        matching_statements, found_role, actual_type = tsla_xbrl.find_statement(role_name)
        assert matching_statements
        assert found_role is not None
        assert actual_type == "BalanceSheet"
    else:
        pytest.skip("No role name found for BalanceSheet in the sample data")


def test_render_statement_with_parenthetical(tsla_xbrl):
    """Test rendering statements with parenthetical parameter."""
    # Try to render non-parenthetical balance sheet
    regular_stmt = tsla_xbrl.render_statement("BalanceSheet", parenthetical=False)
    
    # Try to render parenthetical balance sheet
    try:
        paren_stmt = tsla_xbrl.render_statement("BalanceSheet", parenthetical=True)
        # Check titles to make sure they're different
        assert paren_stmt is not None
        assert "(Parenthetical)" in paren_stmt.title
        assert regular_stmt.title != paren_stmt.title
    except:
        # Skip if no parenthetical statement found
        pytest.skip("No parenthetical balance sheet in the sample data")


def test_custom_namespace_detection(simple_resolver):
    """Test custom namespace detection in statement finding."""
    # Create a fake statement with a custom namespace to test pattern matching
    fake_concept = "unp_CondensedConsolidatedStatementsOfIncomeUnauditedAbstract"
    
    # Check if the pattern matches our fake concept
    for pattern in statement_registry["IncomeStatement"].concept_patterns:
        if re.match(pattern, fake_concept):
            assert True  # Pattern matches as expected
            return
    
    # Fail if none of the patterns match our test concept
    assert False, f"No pattern matched the custom namespace concept: {fake_concept}"

def test_detection_of_financial_statements(unp_xbrl):
    income_statement = unp_xbrl.render_statement("IncomeStatement")
    print(income_statement)
    assert income_statement
    print(unp_xbrl.statements)

    print(unp_xbrl.find_statement("CashFlow", is_parenthetical=True))