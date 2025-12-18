"""
Test for Issue #438 Fix - Revenue Facts Classification

This test verifies that the fix for Issue #438 properly handles revenue fact classification
by ensuring "Revenues" is properly mapped to IncomeStatement via the unified concept mapper.
"""

import pytest
import sys
import os

# Add the project root to the path to ensure we import from source
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
sys.path.insert(0, project_root)

from edgar.entity.parser import EntityFactsParser
from edgar.entity.mappings_loader import get_primary_statement


class TestIssue438Fix:
    """Test suite for Issue #438 revenue classification fix."""

    @pytest.mark.regression
    def test_revenues_in_statement_mapping(self):
        """Test that 'Revenues' is properly mapped to IncomeStatement."""
        # Verify that both singular and plural forms are mapped
        assert get_primary_statement('Revenue') == 'IncomeStatement'
        assert get_primary_statement('Revenues') == 'IncomeStatement'

    @pytest.mark.regression
    def test_determine_statement_type_with_revenues(self):
        """Test that _determine_statement_type properly handles 'Revenues' concept."""
        # Test the exact scenarios identified in Issue #438
        
        # Test singular form
        result_revenue = EntityFactsParser._determine_statement_type('Revenue')
        assert result_revenue == 'IncomeStatement'
        
        # Test plural form (this was the bug)
        result_revenues = EntityFactsParser._determine_statement_type('Revenues') 
        assert result_revenues == 'IncomeStatement'
        
        # Test with namespace prefix (how it would appear in XBRL)
        result_us_gaap_revenue = EntityFactsParser._determine_statement_type('us-gaap:Revenue')
        assert result_us_gaap_revenue == 'IncomeStatement'
        
        result_us_gaap_revenues = EntityFactsParser._determine_statement_type('us-gaap:Revenues')
        assert result_us_gaap_revenues == 'IncomeStatement'

    @pytest.mark.regression
    def test_edge_case_scenarios(self):
        """Test edge case scenarios that could trigger the static mapping fallback."""
        
        # Test various forms that should all resolve to IncomeStatement
        test_cases = [
            'Revenue',
            'Revenues', 
            'us-gaap:Revenue',
            'us-gaap:Revenues',
            'ifrs:Revenue',
            'ifrs:Revenues',
            'dei:Revenue',  # Different namespace
            'dei:Revenues'
        ]
        
        for concept in test_cases:
            result = EntityFactsParser._determine_statement_type(concept)
            assert result == 'IncomeStatement', f"Failed for concept: {concept}"

    @pytest.mark.regression
    def test_no_duplicate_entries_created(self):
        """Verify that revenue concepts are properly mapped to IncomeStatement."""
        # Test that key revenue concepts all map to IncomeStatement
        revenue_concepts = ['Revenue', 'Revenues', 'SalesRevenueNet',
                          'RevenueFromContractWithCustomerExcludingAssessedTax']

        # All revenue concepts should map to IncomeStatement
        for concept in revenue_concepts:
            result = get_primary_statement(concept)
            assert result == 'IncomeStatement', f"{concept} should map to IncomeStatement"

@pytest.mark.regression
def test_regression_no_statement_type_none():
    """Regression test to ensure revenue facts don't get statement_type=None."""
    
    # This test simulates the scenario described in Issue #438
    # where us-gaap:Revenues facts would have statement_type=None
    
    # Test the exact method that was failing
    parser = EntityFactsParser
    
    # These should NOT return None anymore
    assert parser._determine_statement_type('Revenues') is not None
    assert parser._determine_statement_type('us-gaap:Revenues') is not None
    
    # They should specifically return 'IncomeStatement'
    assert parser._determine_statement_type('Revenues') == 'IncomeStatement'
    assert parser._determine_statement_type('us-gaap:Revenues') == 'IncomeStatement'


if __name__ == "__main__":
    # Run the tests directly
    test_instance = TestIssue438Fix()

    print("Running Issue #438 Fix Verification Tests...")

    try:
        # Debug: Test primary statement mapping
        print("Debug - Testing revenue concept mappings:")
        for concept in ['Revenue', 'Revenues', 'SalesRevenueNet']:
            result = get_primary_statement(concept)
            print(f"  {concept}: {result}")

        test_instance.test_revenues_in_statement_mapping()
        print("✓ test_revenues_in_statement_mapping passed")

        test_instance.test_determine_statement_type_with_revenues()
        print("✓ test_determine_statement_type_with_revenues passed")

        test_instance.test_edge_case_scenarios()
        print("✓ test_edge_case_scenarios passed")

        test_instance.test_no_duplicate_entries_created()
        print("✓ test_no_duplicate_entries_created passed")

        test_regression_no_statement_type_none()
        print("✓ test_regression_no_statement_type_none passed")

        print("\n🎉 ALL TESTS PASSED - Issue #438 fix verified!")

    except Exception as e:
        print(f"❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()