"""
Test for Issue #438 Fix - Revenue Deduplication

This test verifies that the deduplication fix for Issue #438 properly handles
duplicate revenue entries by removing less specific concepts when duplicates exist.
"""

import pytest
import sys
import os

# Add the project root to the path to ensure we import from source
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
sys.path.insert(0, project_root)

from edgar.xbrl.deduplication_strategy import RevenueDeduplicator


class TestIssue438DeduplicationFix:
    """Test suite for Issue #438 revenue deduplication fix."""
    
    def test_revenue_deduplicator_basic_functionality(self):
        """Test basic functionality of the RevenueDeduplicator."""
        # Test data with duplicate revenues
        statement_items = [
            {
                'concept': 'us-gaap:Revenues',
                'all_names': ['us-gaap:Revenues'],
                'label': 'Revenues',
                'values': {'2024': 10918000000.0}
            },
            {
                'concept': 'us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax',
                'all_names': ['us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax'],
                'label': 'Total Revenue',
                'values': {'2024': 10918000000.0}  # Same value
            },
            {
                'concept': 'us-gaap:CostOfRevenue',
                'all_names': ['us-gaap:CostOfRevenue'],
                'label': 'Cost of Revenue',
                'values': {'2024': -5000000000.0}
            }
        ]
        
        # Apply deduplication
        result = RevenueDeduplicator.deduplicate_statement_items(statement_items)
        
        # Should have 2 items (one revenue duplicate removed)
        assert len(result) == 2
        
        # The more specific revenue concept should be kept
        revenue_items = [item for item in result if RevenueDeduplicator._is_revenue_concept(item)]
        assert len(revenue_items) == 1
        
        # Should keep the more specific ASC 606 concept
        kept_concept = revenue_items[0]['concept']
        assert 'RevenueFromContractWithCustomerExcludingAssessedTax' in kept_concept
    
    def test_revenue_concept_precedence(self):
        """Test that revenue concept precedence works correctly."""
        # Test precedence scoring
        item_most_specific = {
            'concept': 'us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax',
            'all_names': ['us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax'],
            'label': 'Total Revenue'
        }
        
        item_standard = {
            'concept': 'us-gaap:Revenues',
            'all_names': ['us-gaap:Revenues'],
            'label': 'Revenues'
        }
        
        item_generic = {
            'concept': 'us-gaap:Revenue',
            'all_names': ['us-gaap:Revenue'], 
            'label': 'Revenue'
        }
        
        # Check precedence scores
        score_specific = RevenueDeduplicator._get_precedence_score(item_most_specific)
        score_standard = RevenueDeduplicator._get_precedence_score(item_standard)
        score_generic = RevenueDeduplicator._get_precedence_score(item_generic)
        
        # More specific concepts should have higher scores
        assert score_specific > score_standard
        assert score_standard > score_generic
    
    def test_is_revenue_concept_detection(self):
        """Test revenue concept detection."""
        revenue_item = {
            'concept': 'us-gaap:Revenues',
            'all_names': ['us-gaap:Revenues'],
            'label': 'Total Revenues'
        }
        
        non_revenue_item = {
            'concept': 'us-gaap:CostOfRevenue',
            'all_names': ['us-gaap:CostOfRevenue'],
            'label': 'Cost of Revenue'
        }
        
        expense_item = {
            'concept': 'us-gaap:OperatingExpenses',
            'all_names': ['us-gaap:OperatingExpenses'],
            'label': 'Operating Expenses'
        }
        
        assert RevenueDeduplicator._is_revenue_concept(revenue_item) == True
        assert RevenueDeduplicator._is_revenue_concept(non_revenue_item) == False  # Cost, not revenue
        assert RevenueDeduplicator._is_revenue_concept(expense_item) == False
    
    def test_no_duplicates_scenario(self):
        """Test that items with no duplicates are left unchanged."""
        statement_items = [
            {
                'concept': 'us-gaap:Revenues',
                'all_names': ['us-gaap:Revenues'],
                'label': 'Total Revenues',
                'values': {'2024': 10000000000.0}
            },
            {
                'concept': 'us-gaap:CostOfRevenue',
                'all_names': ['us-gaap:CostOfRevenue'],
                'label': 'Cost of Revenue',
                'values': {'2024': -5000000000.0}
            },
            {
                'concept': 'us-gaap:GrossProfit',
                'all_names': ['us-gaap:GrossProfit'],
                'label': 'Gross Profit',
                'values': {'2024': 5000000000.0}
            }
        ]
        
        # Apply deduplication
        result = RevenueDeduplicator.deduplicate_statement_items(statement_items)
        
        # Should have same number of items (no duplicates to remove)
        assert len(result) == len(statement_items)
        
        # All items should be preserved
        assert result == statement_items
    
    def test_different_period_same_value_no_deduplication(self):
        """Test that same values in different periods don't get deduplicated."""
        statement_items = [
            {
                'concept': 'us-gaap:Revenues',
                'all_names': ['us-gaap:Revenues'],
                'label': 'Revenues',
                'values': {'2024': 10000000000.0}
            },
            {
                'concept': 'us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax',
                'all_names': ['us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax'],
                'label': 'Total Revenue',
                'values': {'2023': 10000000000.0}  # Same value but different period
            }
        ]
        
        # Apply deduplication
        result = RevenueDeduplicator.deduplicate_statement_items(statement_items)
        
        # Should have both items (different periods)
        assert len(result) == 2
    
    def test_multiple_periods_with_duplicates(self):
        """Test deduplication with multiple periods where some have duplicates."""
        statement_items = [
            {
                'concept': 'us-gaap:Revenues',
                'all_names': ['us-gaap:Revenues'],
                'label': 'Revenues',
                'values': {
                    '2024': 12000000000.0,
                    '2023': 10000000000.0,
                    '2022': 8000000000.0
                }
            },
            {
                'concept': 'us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax',
                'all_names': ['us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax'], 
                'label': 'Total Revenue',
                'values': {
                    '2024': 12000000000.0,  # Duplicate for 2024
                    '2023': 9500000000.0,   # Different value for 2023 - no duplicate
                    '2022': 8000000000.0    # Duplicate for 2022
                }
            }
        ]
        
        # Apply deduplication
        result = RevenueDeduplicator.deduplicate_statement_items(statement_items)
        
        # Should have 1 item (the higher precedence concept kept)
        assert len(result) == 1
        
        # Should keep the more specific concept
        kept_item = result[0]
        assert 'RevenueFromContractWithCustomerExcludingAssessedTax' in kept_item['concept']
    
    def test_deduplication_stats(self):
        """Test that deduplication statistics are generated correctly."""
        original_items = [
            {
                'concept': 'us-gaap:Revenues',
                'all_names': ['us-gaap:Revenues'],
                'label': 'Revenues',
                'values': {'2024': 10918000000.0}
            },
            {
                'concept': 'us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax',
                'all_names': ['us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax'],
                'label': 'Total Revenue',
                'values': {'2024': 10918000000.0}
            },
            {
                'concept': 'us-gaap:CostOfRevenue',
                'all_names': ['us-gaap:CostOfRevenue'],
                'label': 'Cost of Revenue',
                'values': {'2024': -5000000000.0}
            }
        ]
        
        deduplicated_items = RevenueDeduplicator.deduplicate_statement_items(original_items)
        
        stats = RevenueDeduplicator.get_deduplication_stats(original_items, deduplicated_items)
        
        assert stats['original_total_items'] == 3
        assert stats['deduplicated_total_items'] == 2
        assert stats['removed_items'] == 1
        assert stats['original_revenue_items'] == 2
        assert stats['deduplicated_revenue_items'] == 1
        assert stats['removed_revenue_items'] == 1
        assert stats['deduplication_performed'] == True
    
    def test_complex_revenue_scenario(self):
        """Test a complex scenario with multiple revenue types and segments."""
        statement_items = [
            # Main revenue concepts (duplicates)
            {
                'concept': 'us-gaap:Revenues',
                'all_names': ['us-gaap:Revenues'],
                'label': 'Revenues',
                'values': {'2024': 50000000000.0}
            },
            {
                'concept': 'us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax',
                'all_names': ['us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax'],
                'label': 'Total Revenue',
                'values': {'2024': 50000000000.0}  # Same value - duplicate
            },
            # Segment revenues (different values - not duplicates)
            {
                'concept': 'us-gaap:Revenues',
                'all_names': ['us-gaap:Revenues'],
                'label': 'Product Revenue',
                'values': {'2024': 30000000000.0}
            },
            {
                'concept': 'us-gaap:Revenues',
                'all_names': ['us-gaap:Revenues'],
                'label': 'Service Revenue', 
                'values': {'2024': 20000000000.0}
            },
            # Other items
            {
                'concept': 'us-gaap:CostOfRevenue',
                'all_names': ['us-gaap:CostOfRevenue'],
                'label': 'Cost of Revenue',
                'values': {'2024': -25000000000.0}
            }
        ]
        
        result = RevenueDeduplicator.deduplicate_statement_items(statement_items)
        
        # Should have 4 items (1 duplicate removed)
        assert len(result) == 4
        
        # Check that we have the right mix of revenue items
        revenue_items = [item for item in result if RevenueDeduplicator._is_revenue_concept(item)]
        assert len(revenue_items) == 3  # Total, Product, Service (duplicate Total removed)
        
        # The main revenue concept should be the more specific one
        total_revenue_items = [item for item in revenue_items if item['values'].get('2024') == 50000000000.0]
        assert len(total_revenue_items) == 1
        assert 'RevenueFromContractWithCustomerExcludingAssessedTax' in total_revenue_items[0]['concept']


if __name__ == "__main__":
    # Run the tests directly
    test_instance = TestIssue438DeduplicationFix()
    
    print("Running Issue #438 Deduplication Fix Tests...")
    
    try:
        test_instance.test_revenue_deduplicator_basic_functionality()
        print("✓ test_revenue_deduplicator_basic_functionality passed")
        
        test_instance.test_revenue_concept_precedence()
        print("✓ test_revenue_concept_precedence passed")
        
        test_instance.test_is_revenue_concept_detection()
        print("✓ test_is_revenue_concept_detection passed")
        
        test_instance.test_no_duplicates_scenario()
        print("✓ test_no_duplicates_scenario passed")
        
        test_instance.test_different_period_same_value_no_deduplication()
        print("✓ test_different_period_same_value_no_deduplication passed")
        
        test_instance.test_multiple_periods_with_duplicates()
        print("✓ test_multiple_periods_with_duplicates passed")
        
        test_instance.test_deduplication_stats()
        print("✓ test_deduplication_stats passed")
        
        test_instance.test_complex_revenue_scenario()
        print("✓ test_complex_revenue_scenario passed")
        
        print("\n🎉 ALL TESTS PASSED - Issue #438 deduplication fix verified!")
        
    except Exception as e:
        print(f"❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()