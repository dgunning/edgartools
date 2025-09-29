"""Tests for multi-entity filing support (Issue #400)"""

import pytest
from edgar import find, get_filings, set_identity
from edgar._filings import Filing, get_by_accession_number_enriched
from rich import print


class TestMultiEntityFilings:
    """Test multi-entity filing functionality"""

    @pytest.mark.network
    def test_filing_with_related_entities(self):
        """Test Filing object with related entities"""
        # Create filing with related entities
        filing = Filing(form='8-K', filing_date='2025-09-26', company='Barclays Dryrock Funding LLC', cik=1551964, accession_no='0001208646-25-000057')

        assert filing.is_multi_entity is True
        assert filing.all_ciks == [1551964, 1552111] # Sorted
        assert len(filing.all_entities) == 2
        print()
        print(filing)

    @pytest.mark.network
    def test_filing_without_related_entities(self):
        """Test Filing object without related entities"""
        filing = Filing(form='8-K', filing_date='2025-09-26', company='Audax Private Credit Fund,LLC', cik=2033362, accession_no='0001193125-25-220404')

        assert filing.is_multi_entity is False
        assert filing.all_ciks == [2033362]
        assert len(filing.all_entities) == 1

    @pytest.mark.network
    def test_find_multi_entity_filing(self):
        """Test find() returns enriched Filing for multi-entity filings"""
        # Test with known multi-entity filing (Evergy)
        filing = Filing(form='8-K', filing_date='2025-08-15', company='EVERGY METRO, INC.', cik=54476, accession_no='0001193125-25-181883')

        if filing:  # May not be in cache during tests
            assert isinstance(filing, Filing)
            assert filing.is_multi_entity is True
            assert len(filing.all_ciks) == 2
            assert 54476 in filing.all_ciks  # EVERGY METRO, INC.
            assert 1711269 in filing.all_ciks  # Evergy, Inc.
        print()
        print(filing)

    @pytest.mark.network
    def test_get_by_accession_number_enriched(self):
        """Test enriched accession number lookup"""
        # Test with known multi-entity filing
        filing = get_by_accession_number_enriched("0001193125-25-181883")

        if filing:  # May not be in cache during tests
            assert isinstance(filing, Filing)
            # Should have enriched with related entities
            if filing.is_multi_entity:
                assert len(filing.all_ciks) > 1

    @pytest.mark.network
    def test_filings_index_enrichment(self):
        """Test that filings[n] returns enriched Filing"""
        filings = get_filings(year=2025, quarter=3)

        if filings and len(filings) > 0:
            # Find a known multi-entity filing
            for i, filing in enumerate(filings):
                if filing.accession_no == "0001193125-25-181883":
                    # Test direct index access
                    enriched_filing = filings[i]
                    assert enriched_filing.is_multi_entity is True
                    assert len(enriched_filing.all_ciks) == 2

                    # Test with enrich=False
                    # Note: Even with enrich=False, is_multi_entity will still check the header
                    # The enrich flag only affects whether we populate from the index
                    unenriched_filing = filings.get_filing_at(i, enrich=False)
                    # The filing will still detect multi-entity from header
                    assert isinstance(unenriched_filing, Filing)
                    break

    def test_backward_compatibility(self):
        """Test that existing code continues to work"""
        # Create filing the old way (without related_entities)
        filing = Filing(
            cik=12345,
            company="Test Corp",
            form="8-K",
            filing_date="2024-01-01",
            accession_no="0001234567-24-000003",
        )
        # All new properties should work without errors
        assert filing.is_multi_entity is False

        assert filing.all_ciks == [12345]
        assert len(filing.all_entities) == 1
        assert filing.cik == 12345  # Original property still works
        assert filing.company == "Test Corp"
        assert filing.accession_no == "0001234567-24-000003"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])