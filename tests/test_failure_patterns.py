"""
Regression tests for failure pattern handling in the concept mapping workflow.

Each test targets a specific FailurePattern that was identified and fixed.
When a new failure pattern is discovered and remediated, add a test here
to prevent regressions.

Test Structure:
1. Each test focuses on ONE failure pattern
2. Uses a known company/metric that had the issue
3. Verifies the fix is applied correctly
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd

from edgar.xbrl.standardization.models import FailurePattern
from edgar.xbrl.standardization.reference_validator import ReferenceValidator


class TestFailurePatternClassification:
    """Tests for _classify_failure() method."""
    
    def test_dimensional_only_pattern_detected(self):
        """
        PATTERN: DIMENSIONAL_ONLY
        DISCOVERED: JPM CommercialPaper - values only exist with VIE dimensions
        FIX: Extract sum of dimensional values
        """
        validator = ReferenceValidator()
        
        # Mock XBRL with dimensional-only data
        mock_xbrl = Mock()
        mock_facts = Mock()
        mock_df = pd.DataFrame({
            'concept': ['us-gaap:CommercialPaper', 'us-gaap:CommercialPaper'],
            'full_dimension_label': ['Consolidated VIE', 'Firm-administered conduits'],
            'numeric_value': [21800000000.0, 9800000000.0]
        })
        mock_facts.get_facts_by_concept.return_value = mock_df
        mock_xbrl.facts = mock_facts
        
        pattern = validator._classify_failure(mock_xbrl, 'us-gaap:CommercialPaper', 'JPM')
        
        assert pattern == FailurePattern.DIMENSIONAL_ONLY
    
    def test_concept_not_in_facts_pattern_detected(self):
        """
        PATTERN: CONCEPT_NOT_IN_FACTS
        DISCOVERED: Concept in calc tree but not in facts database
        FIX: Search company facts API as fallback
        """
        validator = ReferenceValidator()
        
        # Mock XBRL with no data for concept
        mock_xbrl = Mock()
        mock_facts = Mock()
        mock_facts.get_facts_by_concept.return_value = pd.DataFrame()
        mock_xbrl.facts = mock_facts
        
        pattern = validator._classify_failure(mock_xbrl, 'us-gaap:SomeMissingConcept', 'TEST')
        
        assert pattern == FailurePattern.CONCEPT_NOT_IN_FACTS


class TestFailurePatternAutoFix:
    """Tests for _apply_fix_for_pattern() method."""
    
    def test_dimensional_only_extracts_sum(self):
        """
        FIX: DIMENSIONAL_ONLY pattern should sum all dimensional values.
        """
        validator = ReferenceValidator()
        
        # Mock XBRL with dimensional data
        mock_xbrl = Mock()
        mock_facts = Mock()
        mock_df = pd.DataFrame({
            'concept': ['us-gaap:CommercialPaper', 'us-gaap:CommercialPaper'],
            'full_dimension_label': ['VIE A', 'VIE B'],
            'numeric_value': [10000000000.0, 11800000000.0],
            'period_key': ['instant_2024-12-31', 'instant_2024-12-31']
        })
        mock_facts.get_facts_by_concept.return_value = mock_df
        mock_xbrl.facts = mock_facts
        
        value = validator._extract_dimensional_sum(mock_xbrl, 'us-gaap:CommercialPaper')
        
        # Should sum both dimensional values
        assert value == 21800000000.0


class TestE2EPatternRegression:
    """End-to-end regression tests for known failure cases."""
    
    @pytest.mark.integration
    def test_jpm_commercial_paper_extraction(self):
        """
        REGRESSION TEST: JPM CommercialPaper
        
        Issue: CommercialPaper was returning None because all values
        were dimensional (VIE-related) and we filtered them out.
        
        Fix: dimensional_handling config + _extract_dimensional_sum()
        """
        from edgar import set_identity, Company
        from edgar.xbrl.standardization.config_loader import get_config
        
        set_identity('Test dev@test.com')
        get_config(reload=True)
        
        validator = ReferenceValidator()
        validator._current_metric = 'ShortTermDebt'
        
        # Get JPM's latest 10-K
        c = Company('JPM')
        filing = list(c.get_filings(form='10-K'))[0]
        xbrl = filing.xbrl()
        
        # Extract CommercialPaper - should NOT be None
        value = validator._extract_xbrl_value(xbrl, 'us-gaap:CommercialPaper')
        
        assert value is not None
        assert value > 0
        # Expected: ~$21B based on historical data
        assert value > 10e9, f"Expected > $10B, got ${value/1e9:.2f}B"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
