"""
Test for Issue #438 Fix - Revenue Facts Classification

This test verifies that the fix for Issue #438 properly handles revenue fact classification
by ensuring "Revenues" is included in the STATEMENT_MAPPING fallback.
"""

import pytest
import sys
import os

# Add the project root to the path to ensure we import from source
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
sys.path.insert(0, project_root)

from edgar.entity.parser import EntityFactsParser


class TestIssue438Fix:
    """Test suite for Issue #438 revenue classification fix."""
    
    def test_revenues_in_statement_mapping(self):
        """Test that 'Revenues' is properly included in STATEMENT_MAPPING."""
        # Verify that both singular and plural forms are mapped
        assert 'Revenue' in EntityFactsParser.STATEMENT_MAPPING
        assert 'Revenues' in EntityFactsParser.STATEMENT_MAPPING
        
        # Verify they both map to IncomeStatement
        assert EntityFactsParser.STATEMENT_MAPPING['Revenue'] == 'IncomeStatement'
        assert EntityFactsParser.STATEMENT_MAPPING['Revenues'] == 'IncomeStatement'
    
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
    
    def test_no_duplicate_entries_created(self):
        """Verify that adding 'Revenues' doesn't create duplicate entries issue."""
        
        # Ensure that we have exactly one mapping for each concept
        mapping = EntityFactsParser.STATEMENT_MAPPING
        
        # Count occurrences of each value to ensure no weird duplications
        revenue_concepts = [k for k, v in mapping.items() if 'revenue' in k.lower()]
        
        # Should have at least 'Revenue' and 'Revenues' plus other revenue-related concepts
        assert len(revenue_concepts) >= 2
        assert 'Revenue' in revenue_concepts
        assert 'Revenues' in revenue_concepts
        
        # All revenue concepts should map to IncomeStatement
        for concept in revenue_concepts:
            assert mapping[concept] == 'IncomeStatement'


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
        # Debug: Print the actual mapping
        print("Debug - STATEMENT_MAPPING keys containing 'revenue':")
        for key in EntityFactsParser.STATEMENT_MAPPING.keys():
            if 'revenue' in key.lower():
                print(f"  {key}: {EntityFactsParser.STATEMENT_MAPPING[key]}")
        
        print(f"Debug - 'Revenues' in mapping: {'Revenues' in EntityFactsParser.STATEMENT_MAPPING}")
        
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