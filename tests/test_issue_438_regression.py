"""
Regression test for Issue #438 - Missing revenue facts in income statement

This test ensures that revenue facts are properly classified and prevents
future regressions of the us-gaap:Revenues classification issue.
"""

import pytest
import sys
import os

# Ensure we import from source
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from edgar.entity.parser import EntityFactsParser


class TestIssue438Regression:
    """Regression tests for Issue #438."""
    
    def test_revenues_concept_mapping(self):
        """Test that 'Revenues' concept is properly mapped to IncomeStatement."""
        # This was the core bug - 'Revenues' returned None from static mapping
        result = EntityFactsParser._determine_statement_type('Revenues')
        assert result == 'IncomeStatement', "Revenues should map to IncomeStatement"
    
    def test_us_gaap_revenues_mapping(self):
        """Test that 'us-gaap:Revenues' is properly handled."""
        # This is the exact scenario from the bug report
        result = EntityFactsParser._determine_statement_type('us-gaap:Revenues')
        assert result == 'IncomeStatement', "us-gaap:Revenues should map to IncomeStatement"
    
    def test_revenue_vs_revenues_consistency(self):
        """Test that both singular and plural revenue forms behave consistently."""
        singular = EntityFactsParser._determine_statement_type('Revenue')
        plural = EntityFactsParser._determine_statement_type('Revenues')
        
        assert singular == plural == 'IncomeStatement', \
            "Both Revenue and Revenues should map consistently"
    
    def test_namespace_handling(self):
        """Test that namespace prefixes are handled correctly for revenue concepts."""
        test_cases = [
            'us-gaap:Revenue',
            'us-gaap:Revenues',
            'ifrs:Revenue', 
            'ifrs:Revenues',
            'company:Revenue',
            'company:Revenues'
        ]
        
        for concept in test_cases:
            result = EntityFactsParser._determine_statement_type(concept)
            assert result == 'IncomeStatement', \
                f"Concept {concept} should map to IncomeStatement"
    
    def test_statement_mapping_completeness(self):
        """Test that STATEMENT_MAPPING includes both revenue forms."""
        mapping = EntityFactsParser.STATEMENT_MAPPING
        
        assert 'Revenue' in mapping, "Revenue should be in STATEMENT_MAPPING"
        assert 'Revenues' in mapping, "Revenues should be in STATEMENT_MAPPING"
        
        assert mapping['Revenue'] == 'IncomeStatement'
        assert mapping['Revenues'] == 'IncomeStatement'
    
    def test_no_none_return_for_common_revenue_concepts(self):
        """Ensure common revenue concepts don't return None."""
        common_revenue_concepts = [
            'Revenue',
            'Revenues',
            'us-gaap:Revenue',
            'us-gaap:Revenues',
            'RevenueFromContractWithCustomerExcludingAssessedTax',
            'SalesRevenueNet'
        ]
        
        for concept in common_revenue_concepts:
            result = EntityFactsParser._determine_statement_type(concept)
            assert result is not None, f"Concept {concept} should not return None"
            assert result == 'IncomeStatement', f"Concept {concept} should map to IncomeStatement"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])