"""
Entity filings-specific functionality tests.

Focus: Filing retrieval, filtering, equality, hashing, and filing-specific operations.
"""

import pytest
from edgar.entity import Company


class TestEntityFilings:
    """Test filing-related functionality for entities"""

    @pytest.mark.network
    def test_filings_equality_and_filtering(self):
        """Test filings equality after filtering operations"""
        company = Company("AAPL")
        filings = company.get_filings()
        assert filings is not None
        assert len(filings) > 1500

        # Filter to 10-K forms
        filings_10k = filings.filter(form="10-K")
        filings_10k_copy = filings.filter(form="10-K")

        # Same filters should produce equal results
        assert filings_10k == filings_10k_copy
        
        # Different date filters should produce different results
        filings_filtered_by_date = filings_10k.filter(filing_date="2023-01-01:2024-12-31")
        assert filings_10k != filings_filtered_by_date

        # Different form filters should produce different results
        filings_10q = filings.filter(form="10-Q")
        assert filings_10k != filings_10q

    @pytest.mark.network
    def test_filings_hash(self):
        """Test that filings objects are hashable"""
        company = Company("AAPL")
        filings = company.get_filings()
        filings_hash = hash(filings)
        assert isinstance(filings_hash, int)
        
        # Same filings should have same hash
        filings2 = company.get_filings()
        assert hash(filings) == hash(filings2)

    @pytest.mark.network
    def test_filings_consistency(self):
        """Test that multiple calls return consistent results"""
        company = Company("AAPL")
        
        # Multiple calls should return equal filings
        filings1 = company.get_filings()
        filings2 = company.get_filings()
        
        assert filings1 == filings2
        assert len(filings1) == len(filings2)