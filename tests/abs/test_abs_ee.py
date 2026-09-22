"""
Tests for Form ABS-EE Asset Data Parser.
"""
import pytest

from edgar.abs.abs_ee import AutoLeaseAssetData, AutoLeaseSummary


class TestAutoLeaseAssetDataBasic:
    """Basic tests for AutoLeaseAssetData class."""

    def test_empty_xml(self):
        """Test handling of empty XML."""
        parser = AutoLeaseAssetData("<assetData></assetData>")
        assert len(parser) == 0
        assert parser.assets.empty

    def test_invalid_xml(self):
        """Test handling of invalid XML."""
        parser = AutoLeaseAssetData("not xml at all")
        assert len(parser) == 0

    def test_str_representation(self):
        """Test string representation."""
        parser = AutoLeaseAssetData("<assetData></assetData>")
        assert "AutoLeaseAssetData" in str(parser)
        assert "0" in str(parser)

    def test_summary_empty(self):
        """Test summary for empty data."""
        parser = AutoLeaseAssetData("<assetData></assetData>")
        summary = parser.summary()
        assert isinstance(summary, AutoLeaseSummary)
        assert summary.num_assets == 0
        assert summary.total_acquisition_cost == 0.0


@pytest.fixture(scope="module")
def bmw_abs_ee():
    """Get a BMW ABS-EE filing for testing."""
    from edgar import find
    # BMW Vehicle Lease Trust 2023-2
    filing = find('0000929638-25-004537')
    return AutoLeaseAssetData.from_filing(filing)


class TestAutoLeaseAssetDataIntegration:
    """Integration tests with real ABS-EE filings."""

    def test_from_filing(self, bmw_abs_ee):
        """Test loading from filing."""
        assert bmw_abs_ee is not None
        assert len(bmw_abs_ee) > 0

    def test_assets_dataframe(self, bmw_abs_ee):
        """Test assets property returns DataFrame."""
        import pandas as pd

        df = bmw_abs_ee.assets
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 1000  # BMW trust should have many assets

    def test_key_columns_present(self, bmw_abs_ee):
        """Test key columns are present in assets DataFrame."""
        df = bmw_abs_ee.assets
        expected_columns = [
            'asset_id',
            'vehicle_manufacturer',
            'vehicle_model',
            'vehicle_year',
            'credit_score',
            'acquisition_cost',
            'lessee_state',
        ]
        for col in expected_columns:
            assert col in df.columns, f"Missing column: {col}"

    def test_data_types(self, bmw_abs_ee):
        """Test data types are correctly parsed."""
        import numpy as np

        df = bmw_abs_ee.assets
        first_row = df.iloc[0]

        # Check numeric types (allow numpy types)
        assert isinstance(first_row['acquisition_cost'], (float, np.floating))
        assert isinstance(first_row['vehicle_year'], (int, np.integer))
        assert isinstance(first_row['credit_score'], (int, np.integer))

        # Check string types
        assert isinstance(first_row['vehicle_manufacturer'], str)
        assert isinstance(first_row['lessee_state'], str)

    def test_summary_calculations(self, bmw_abs_ee):
        """Test summary statistics are calculated correctly."""
        summary = bmw_abs_ee.summary()

        assert summary.num_assets == len(bmw_abs_ee)
        assert summary.total_acquisition_cost > 0
        assert summary.avg_credit_score is not None
        assert summary.avg_credit_score > 600  # Reasonable credit scores
        assert summary.avg_lease_term is not None

    def test_summary_distributions(self, bmw_abs_ee):
        """Test summary distribution fields."""
        summary = bmw_abs_ee.summary()

        # Should have BMW vehicles
        assert 'BMW' in str(summary.vehicle_makes) or len(summary.vehicle_makes) > 0

        # Should have state distribution
        assert len(summary.states) > 0

    def test_rich_representation(self, bmw_abs_ee):
        """Test rich console representation."""
        rich_output = bmw_abs_ee.__rich__()
        assert rich_output is not None


class TestAutoLeaseAssetDataFromNonAbsEe:
    """Test behavior when used with non-ABS-EE filings."""

    def test_from_filing_non_abs_ee(self):
        """Test from_filing returns None for non-ABS-EE filings."""
        from edgar import find

        # 10-K filing - no EX-102 exhibit
        filing = find('0000320193-24-000123')  # Apple 10-K
        result = AutoLeaseAssetData.from_filing(filing)
        assert result is None
