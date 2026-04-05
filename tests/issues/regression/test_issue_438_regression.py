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
from edgar.entity.mappings_loader import get_primary_statement
from edgar.xbrl.deduplication_strategy import RevenueDeduplicator


@pytest.mark.regression
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
        """Test that revenue concepts are properly mapped via unified mapper."""
        # Test via the new unified get_primary_statement API
        assert get_primary_statement('Revenue') == 'IncomeStatement', \
            "Revenue should map to IncomeStatement"
        assert get_primary_statement('Revenues') == 'IncomeStatement', \
            "Revenues should map to IncomeStatement"
    
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
    
    def test_revenue_deduplication_prevents_duplicates(self):
        """Test that revenue deduplication prevents duplicate entries - the fix for Issue #438."""
        # Create test data that represents the duplicate scenario
        statement_items = [
            {
                'concept': 'us-gaap:Revenues',
                'all_names': ['us-gaap:Revenues'],
                'label': 'Revenues',
                'values': {'2020': 10918000000.0}  # The exact value from the bug report
            },
            {
                'concept': 'us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax',
                'all_names': ['us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax'],
                'label': 'Total Revenue',
                'values': {'2020': 10918000000.0}  # Same value - should be deduplicated
            },
            {
                'concept': 'us-gaap:CostOfRevenue',
                'all_names': ['us-gaap:CostOfRevenue'],
                'label': 'Cost of Revenue',
                'values': {'2020': -5000000000.0}
            }
        ]
        
        # Apply deduplication
        result = RevenueDeduplicator.deduplicate_statement_items(statement_items)
        
        # Should have removed one duplicate revenue item
        assert len(result) == 2, "Should have removed one duplicate revenue item"
        
        # Should keep only one revenue concept
        revenue_items = [item for item in result if RevenueDeduplicator._is_revenue_concept(item)]
        assert len(revenue_items) == 1, "Should have exactly one revenue item after deduplication"
        
        # Should keep the more specific ASC 606 concept
        kept_revenue = revenue_items[0]
        assert 'RevenueFromContractWithCustomerExcludingAssessedTax' in kept_revenue['concept'], \
            "Should keep the more specific revenue concept"
    
    def test_deduplication_preserves_different_values(self):
        """Test that deduplication only removes items with the same value."""
        statement_items = [
            {
                'concept': 'us-gaap:Revenues',
                'all_names': ['us-gaap:Revenues'],
                'label': 'Total Revenues',
                'values': {'2020': 10000000000.0}
            },
            {
                'concept': 'us-gaap:Revenues',
                'all_names': ['us-gaap:Revenues'],
                'label': 'Product Revenues',
                'values': {'2020': 6000000000.0}  # Different value - should not be deduplicated
            },
            {
                'concept': 'us-gaap:Revenues',
                'all_names': ['us-gaap:Revenues'],
                'label': 'Service Revenues',
                'values': {'2020': 4000000000.0}  # Different value - should not be deduplicated
            }
        ]
        
        result = RevenueDeduplicator.deduplicate_statement_items(statement_items)
        
        # All items should be preserved since they have different values
        assert len(result) == 3, "All items with different values should be preserved"
        
        revenue_items = [item for item in result if RevenueDeduplicator._is_revenue_concept(item)]
        assert len(revenue_items) == 3, "All revenue items with different values should be preserved"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])