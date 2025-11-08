"""Unit tests for filing selector functionality."""

import pytest
from datetime import datetime

from tests.harness import FilingSelector


class TestFilingSelector:
    """Test filing selection methods."""

    @pytest.mark.network
    def test_by_random_sample(self):
        """Test random sampling of filings."""
        filings = FilingSelector.by_random_sample(
            form="8-K",
            year=2024,
            sample=5
        )

        assert len(filings) == 5
        assert all(f.form == "8-K" for f in filings)

    @pytest.mark.network
    def test_by_random_sample_with_seed(self):
        """Test random sampling is reproducible with seed."""
        filings1 = FilingSelector.by_random_sample(
            form="8-K",
            year=2024,
            sample=3,
            seed=42
        )

        filings2 = FilingSelector.by_random_sample(
            form="8-K",
            year=2024,
            sample=3,
            seed=42
        )

        # Same seed should give same filings
        assert len(filings1) == len(filings2) == 3
        assert [f.accession_no for f in filings1] == [f.accession_no for f in filings2]

    @pytest.mark.network
    def test_by_date_range(self):
        """Test selecting filings by date range."""
        filings = FilingSelector.by_date_range(
            form="10-K",
            start_date="2024-01-01",
            end_date="2024-01-31",
            sample=5
        )

        assert len(filings) <= 5  # May be fewer if not enough filings in range
        assert all(f.form == "10-K" for f in filings)
        # All filings should be in January 2024
        for filing in filings:
            assert "2024-01" in filing.filing_date

    @pytest.mark.network
    def test_by_date_range_no_sample(self):
        """Test selecting all filings in date range."""
        filings = FilingSelector.by_date_range(
            form="8-K",
            start_date="2024-01-02",
            end_date="2024-01-02"  # Single day
        )

        assert len(filings) > 0  # Should have some filings
        assert all(f.form == "8-K" for f in filings)

    @pytest.mark.network
    def test_by_company_list(self):
        """Test selecting filings from company list."""
        filings = FilingSelector.by_company_list(
            companies=["AAPL", "MSFT"],
            form="10-K",
            latest_n=1
        )

        assert len(filings) == 2  # One filing per company
        assert all(f.form == "10-K" for f in filings)
        companies = {f.company for f in filings}
        # Check we got filings from the right companies (name varies)
        assert len(companies) == 2

    @pytest.mark.network
    def test_by_company_list_latest_n(self):
        """Test selecting multiple latest filings per company."""
        filings = FilingSelector.by_company_list(
            companies=["AAPL"],
            form="10-Q",
            latest_n=2
        )

        assert len(filings) == 2  # Two latest 10-Qs
        assert all(f.form == "10-Q" for f in filings)

    @pytest.mark.network
    def test_by_company_subset(self):
        """Test selecting filings from company subset."""
        filings = FilingSelector.by_company_subset(
            form="10-K",
            subset_name="MEGA_CAP",
            sample=3,
            latest_n=1
        )

        assert len(filings) <= 3  # May be fewer if some companies fail
        assert all(f.form == "10-K" for f in filings)

    @pytest.mark.network
    def test_by_accession(self):
        """Test selecting specific filings by accession number."""
        # First get some filings to get valid accession numbers
        sample_filings = FilingSelector.by_random_sample("10-K", 2024, 2)
        accessions = [f.accession_no for f in sample_filings]

        # Now fetch by accession
        filings = FilingSelector.by_accession(accessions)

        assert len(filings) == 2
        assert {f.accession_no for f in filings} == set(accessions)

    @pytest.mark.network
    def test_by_accession_invalid(self):
        """Test handling of invalid accession numbers."""
        filings = FilingSelector.by_accession([
            "0000000000-00-000000",  # Invalid
            "9999999999-99-999999"   # Invalid
        ])

        assert len(filings) == 0  # Should skip invalid accessions

    @pytest.mark.network
    def test_by_recent(self):
        """Test selecting recent filings."""
        filings = FilingSelector.by_recent(
            form="8-K",
            days=7,
            sample=5
        )

        # Should get some recent filings
        assert len(filings) <= 5
        if filings:
            assert all(f.form == "8-K" for f in filings)

    @pytest.mark.network
    def test_count_available(self):
        """Test counting available filings."""
        count = FilingSelector.count_available("10-K", year=2024)

        assert count > 0
        assert isinstance(count, int)


class TestFromConfig:
    """Test config-based selection."""

    @pytest.mark.network
    def test_from_config_date_range(self):
        """Test config-based date range selection."""
        config = {
            'method': 'date_range',
            'params': {
                'form': '10-K',
                'start_date': '2024-01-01',
                'end_date': '2024-01-31',
                'sample': 3
            }
        }

        filings = FilingSelector.from_config(config)

        assert len(filings) <= 3
        assert all(f.form == "10-K" for f in filings)

    @pytest.mark.network
    def test_from_config_random_sample(self):
        """Test config-based random sample selection."""
        config = {
            'method': 'random_sample',
            'params': {
                'form': '8-K',
                'year': 2024,
                'sample': 5,
                'seed': 42
            }
        }

        filings = FilingSelector.from_config(config)

        assert len(filings) == 5
        assert all(f.form == "8-K" for f in filings)

    @pytest.mark.network
    def test_from_config_company_list(self):
        """Test config-based company list selection."""
        config = {
            'method': 'company_list',
            'params': {
                'companies': ['AAPL'],
                'form': '10-K',
                'latest_n': 1
            }
        }

        filings = FilingSelector.from_config(config)

        assert len(filings) == 1
        assert filings[0].form == "10-K"

    def test_from_config_unknown_method(self):
        """Test handling of unknown selection method."""
        config = {
            'method': 'nonexistent_method',
            'params': {}
        }

        with pytest.raises(ValueError, match="Unknown selection method"):
            FilingSelector.from_config(config)


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.network
    def test_empty_company_list(self):
        """Test handling of empty company list."""
        filings = FilingSelector.by_company_list(
            companies=[],
            form="10-K"
        )

        assert len(filings) == 0

    @pytest.mark.network
    def test_invalid_company_ticker(self):
        """Test handling of invalid company ticker."""
        filings = FilingSelector.by_company_list(
            companies=["INVALIDTICKER123"],
            form="10-K"
        )

        # Should gracefully handle invalid ticker and return empty list
        assert len(filings) == 0

    @pytest.mark.network
    def test_date_range_no_results(self):
        """Test date range with no filings."""
        # Use a future date range that shouldn't have filings
        filings = FilingSelector.by_date_range(
            form="10-K",
            start_date="2099-01-01",
            end_date="2099-01-31"
        )

        assert len(filings) == 0
