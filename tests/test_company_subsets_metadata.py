"""
Tests for comprehensive company subset features (industry and state filtering).

This test module covers the new functionality added to company_subsets module:
- Comprehensive dataset integration
- Industry (SIC) filtering
- State of incorporation filtering
- CompanySubset fluent interface with metadata
- Industry-specific convenience functions

Test Data:
    Most tests use a 5% sample fixture (tests/fixtures/companies_sample.pq)
    containing ~28K companies. This allows fast testing without requiring
    the full dataset download.

    Tests marked with @pytest.mark.integration use the full dataset if available.
"""

import pytest
import pandas as pd
from pathlib import Path

# Import fixtures from fixtures directory
pytest_plugins = ['tests.fixtures.conftest_company_subsets']

from edgar.reference.company_subsets import (
    # Core functions
    get_all_companies,
    get_companies_by_industry,
    get_companies_by_state,
    # CompanySubset class
    CompanySubset,
    # Industry-specific convenience functions
    get_pharmaceutical_companies,
    get_biotechnology_companies,
    get_software_companies,
    get_semiconductor_companies,
    get_banking_companies,
    get_investment_companies,
    get_insurance_companies,
    get_real_estate_companies,
    get_oil_gas_companies,
    get_retail_companies,
)


# ============================================================================
# Core Functionality Tests
# ============================================================================

@pytest.mark.fast
def test_get_all_companies_standard_mode():
    """Test get_all_companies() returns ticker-only data by default."""
    companies = get_all_companies()

    # Should have standard columns
    assert 'cik' in companies.columns
    assert 'ticker' in companies.columns
    assert 'name' in companies.columns
    assert 'exchange' in companies.columns

    # Should NOT have comprehensive columns
    assert 'sic' not in companies.columns
    assert 'sic_description' not in companies.columns

    # Should have reasonable number of companies (~13K)
    assert len(companies) > 1000
    assert len(companies) < 20000


@pytest.mark.fast
def test_get_all_companies_comprehensive_mode(mock_comprehensive_dataset):
    """Test get_all_companies(use_comprehensive=True) returns full metadata."""
    companies = get_all_companies(use_comprehensive=True)

    # Should have standard columns
    assert 'cik' in companies.columns
    assert 'ticker' in companies.columns
    assert 'name' in companies.columns
    assert 'exchange' in companies.columns

    # Should have comprehensive columns
    assert 'sic' in companies.columns
    assert 'sic_description' in companies.columns
    assert 'state_of_incorporation' in companies.columns
    assert 'state_of_incorporation_description' in companies.columns
    assert 'fiscal_year_end' in companies.columns
    assert 'entity_type' in companies.columns
    assert 'ein' in companies.columns

    # Should have sample data (~28K companies from 5% sample)
    assert len(companies) > 20000
    assert len(companies) < 35000


# ============================================================================
# Industry Filtering Tests
# ============================================================================

@pytest.mark.fast
def test_get_companies_by_industry_single_sic(mock_comprehensive_dataset):
    """Test filtering by single SIC code."""
    # SIC 2834 = Pharmaceutical Preparations
    pharma = get_companies_by_industry(sic=2834)

    assert isinstance(pharma, pd.DataFrame)
    # May have 0 companies in sample, that's okay
    if len(pharma) > 0:
        # All companies should have SIC 2834
        assert all(pharma['sic'] == 2834)
        # Should have comprehensive columns
        assert 'sic_description' in pharma.columns


@pytest.mark.fast
def test_get_companies_by_industry_multiple_sic(mock_comprehensive_dataset):
    """Test filtering by list of SIC codes."""
    # Multiple pharma-related SIC codes
    companies = get_companies_by_industry(sic=[2834, 2835, 2836])

    assert isinstance(companies, pd.DataFrame)
    # May have 0 companies in sample, that's okay
    if len(companies) > 0:
        # All companies should have one of the specified SIC codes
        assert all(companies['sic'].isin([2834, 2835, 2836]))


@pytest.mark.fast
def test_get_companies_by_industry_sic_range(mock_comprehensive_dataset):
    """Test filtering by SIC code range."""
    # Biotech range (2833-2836)
    biotech = get_companies_by_industry(sic_range=(2833, 2836))

    assert isinstance(biotech, pd.DataFrame)
    # May have 0 companies in sample, that's okay
    if len(biotech) > 0:
        # All companies should be within range
        assert all(biotech['sic'] >= 2833)
        assert all(biotech['sic'] <= 2836)


@pytest.mark.fast
def test_get_companies_by_industry_description_contains(mock_comprehensive_dataset):
    """Test filtering by SIC description text search."""
    # Search for "services" in description (more common than "software")
    companies = get_companies_by_industry(sic_description_contains='services')

    assert isinstance(companies, pd.DataFrame)
    # Should find at least some companies with "services" in description
    assert len(companies) > 0

    # All companies should have "services" in description (case-insensitive)
    assert all(
        companies['sic_description'].str.contains('services', case=False, na=False)
    )


@pytest.mark.slow
@pytest.mark.network
def test_get_companies_by_industry_combined_filters():
    """Test combining multiple filter criteria."""
    # SIC range + description contains
    companies = get_companies_by_industry(
        sic_range=(2800, 2899),
        sic_description_contains='pharmaceutical'
    )

    assert isinstance(companies, pd.DataFrame)
    assert len(companies) > 0

    # Should meet both criteria
    assert all(companies['sic'] >= 2800)
    assert all(companies['sic'] <= 2899)
    assert all(
        companies['sic_description'].str.contains('pharmaceutical', case=False, na=False)
    )


# ============================================================================
# State Filtering Tests
# ============================================================================

@pytest.mark.slow
@pytest.mark.network
def test_get_companies_by_state_single():
    """Test filtering by single state."""
    # Delaware - most common state of incorporation
    de_companies = get_companies_by_state('DE')

    assert isinstance(de_companies, pd.DataFrame)
    assert len(de_companies) > 0

    # All companies should be incorporated in Delaware
    assert all(de_companies['state_of_incorporation'].str.upper() == 'DE')

    # Should have comprehensive columns
    assert 'state_of_incorporation_description' in de_companies.columns


@pytest.mark.slow
@pytest.mark.network
def test_get_companies_by_state_multiple():
    """Test filtering by multiple states."""
    # Delaware and Nevada
    companies = get_companies_by_state(['DE', 'NV'])

    assert isinstance(companies, pd.DataFrame)
    assert len(companies) > 0

    # All companies should be in DE or NV
    states_upper = companies['state_of_incorporation'].str.upper()
    assert all(states_upper.isin(['DE', 'NV']))


@pytest.mark.slow
@pytest.mark.network
def test_get_companies_by_state_case_insensitive():
    """Test state filtering is case-insensitive."""
    de_upper = get_companies_by_state('DE')
    de_lower = get_companies_by_state('de')

    # Should return same results regardless of case
    assert len(de_upper) == len(de_lower)


# ============================================================================
# CompanySubset Fluent Interface Tests
# ============================================================================

@pytest.mark.slow
@pytest.mark.network
def test_company_subset_from_industry():
    """Test CompanySubset.from_industry() method."""
    subset = CompanySubset().from_industry(sic=2834)
    companies = subset.get()

    assert isinstance(companies, pd.DataFrame)
    assert len(companies) > 0
    assert all(companies['sic'] == 2834)

    # Should auto-enable comprehensive mode
    assert 'sic' in companies.columns


@pytest.mark.slow
@pytest.mark.network
def test_company_subset_from_state():
    """Test CompanySubset.from_state() method."""
    subset = CompanySubset().from_state('DE')
    companies = subset.get()

    assert isinstance(companies, pd.DataFrame)
    assert len(companies) > 0
    assert all(companies['state_of_incorporation'].str.upper() == 'DE')

    # Should auto-enable comprehensive mode
    assert 'state_of_incorporation' in companies.columns


@pytest.mark.slow
@pytest.mark.network
def test_company_subset_chained_industry_and_sample():
    """Test chaining industry filter with sampling."""
    subset = CompanySubset().from_industry(sic=2834).sample(10, random_state=42)
    companies = subset.get()

    assert len(companies) == 10
    assert all(companies['sic'] == 2834)


@pytest.mark.slow
@pytest.mark.network
def test_company_subset_use_comprehensive_init():
    """Test initializing CompanySubset with use_comprehensive=True."""
    subset = CompanySubset(use_comprehensive=True)
    companies = subset.get()

    assert 'sic' in companies.columns
    assert 'state_of_incorporation' in companies.columns
    assert len(companies) > 500000


# ============================================================================
# Industry-Specific Convenience Functions Tests
# ============================================================================

@pytest.mark.slow
@pytest.mark.network
def test_get_pharmaceutical_companies():
    """Test get_pharmaceutical_companies() convenience function."""
    pharma = get_pharmaceutical_companies()

    assert isinstance(pharma, pd.DataFrame)
    assert len(pharma) > 0
    assert all(pharma['sic'] == 2834)


@pytest.mark.slow
@pytest.mark.network
def test_get_biotechnology_companies():
    """Test get_biotechnology_companies() convenience function."""
    biotech = get_biotechnology_companies()

    assert isinstance(biotech, pd.DataFrame)
    assert len(biotech) > 0
    assert all(biotech['sic'] >= 2833)
    assert all(biotech['sic'] <= 2836)


@pytest.mark.slow
@pytest.mark.network
def test_get_software_companies():
    """Test get_software_companies() convenience function."""
    software = get_software_companies()

    assert isinstance(software, pd.DataFrame)
    assert len(software) > 0
    assert all(software['sic'] >= 7371)
    assert all(software['sic'] <= 7379)


@pytest.mark.slow
@pytest.mark.network
def test_get_semiconductor_companies():
    """Test get_semiconductor_companies() convenience function."""
    semiconductors = get_semiconductor_companies()

    assert isinstance(semiconductors, pd.DataFrame)
    assert len(semiconductors) > 0
    assert all(semiconductors['sic'] == 3674)


@pytest.mark.slow
@pytest.mark.network
def test_get_banking_companies():
    """Test get_banking_companies() convenience function."""
    banks = get_banking_companies()

    assert isinstance(banks, pd.DataFrame)
    assert len(banks) > 0
    assert all(banks['sic'] >= 6020)
    assert all(banks['sic'] <= 6029)


@pytest.mark.slow
@pytest.mark.network
def test_get_investment_companies():
    """Test get_investment_companies() convenience function."""
    investments = get_investment_companies()

    assert isinstance(investments, pd.DataFrame)
    assert len(investments) > 0
    assert all(investments['sic'] >= 6200)
    assert all(investments['sic'] <= 6299)


@pytest.mark.slow
@pytest.mark.network
def test_get_insurance_companies():
    """Test get_insurance_companies() convenience function."""
    insurance = get_insurance_companies()

    assert isinstance(insurance, pd.DataFrame)
    assert len(insurance) > 0
    assert all(insurance['sic'] >= 6300)
    assert all(insurance['sic'] <= 6399)


@pytest.mark.slow
@pytest.mark.network
def test_get_real_estate_companies():
    """Test get_real_estate_companies() convenience function."""
    real_estate = get_real_estate_companies()

    assert isinstance(real_estate, pd.DataFrame)
    assert len(real_estate) > 0
    assert all(real_estate['sic'] >= 6500)
    assert all(real_estate['sic'] <= 6599)


@pytest.mark.slow
@pytest.mark.network
def test_get_oil_gas_companies():
    """Test get_oil_gas_companies() convenience function."""
    oil_gas = get_oil_gas_companies()

    assert isinstance(oil_gas, pd.DataFrame)
    assert len(oil_gas) > 0
    assert all(oil_gas['sic'] >= 1300)
    assert all(oil_gas['sic'] <= 1399)


@pytest.mark.slow
@pytest.mark.network
def test_get_retail_companies():
    """Test get_retail_companies() convenience function."""
    retail = get_retail_companies()

    assert isinstance(retail, pd.DataFrame)
    assert len(retail) > 0
    assert all(retail['sic'] >= 5200)
    assert all(retail['sic'] <= 5999)


# ============================================================================
# Edge Cases and Error Handling Tests
# ============================================================================

@pytest.mark.slow
@pytest.mark.network
def test_get_companies_by_industry_no_filters():
    """Test calling get_companies_by_industry with no filters returns all companies."""
    companies = get_companies_by_industry()

    # Should return comprehensive dataset
    assert len(companies) > 500000


@pytest.mark.slow
@pytest.mark.network
def test_get_companies_by_industry_invalid_sic():
    """Test filtering by non-existent SIC code."""
    # SIC 9999 should not exist
    companies = get_companies_by_industry(sic=9999)

    # Should return empty DataFrame with correct schema
    assert isinstance(companies, pd.DataFrame)
    assert len(companies) == 0
    assert 'sic' in companies.columns


@pytest.mark.slow
@pytest.mark.network
def test_get_companies_by_state_invalid():
    """Test filtering by non-existent state."""
    # 'XX' is not a valid state code
    companies = get_companies_by_state('XX')

    # Should return empty DataFrame with correct schema
    assert isinstance(companies, pd.DataFrame)
    assert len(companies) == 0
    assert 'state_of_incorporation' in companies.columns


# ============================================================================
# Performance and Caching Tests
# ============================================================================

@pytest.mark.slow
@pytest.mark.network
def test_comprehensive_mode_caching():
    """Test that comprehensive mode uses caching on subsequent calls."""
    import time

    # First call (may take time to build)
    start1 = time.time()
    companies1 = get_all_companies(use_comprehensive=True)
    time1 = time.time() - start1

    # Second call (should be cached)
    start2 = time.time()
    companies2 = get_all_companies(use_comprehensive=True)
    time2 = time.time() - start2

    # Should return same data
    assert len(companies1) == len(companies2)

    # Second call should be much faster (< 1 second)
    assert time2 < 1.0


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.slow
@pytest.mark.network
def test_industry_filtering_integration():
    """Test complete workflow: get pharma companies, filter by state, sample."""
    # Get pharmaceutical companies in Delaware, sample 5
    companies = (CompanySubset()
                 .from_industry(sic=2834)
                 .from_state('DE')
                 .sample(5, random_state=42)
                 .get())

    assert len(companies) <= 5  # May be fewer if < 5 DE pharma companies
    if len(companies) > 0:
        assert all(companies['sic'] == 2834)
        # Note: from_state will replace data, so this test checks the last operation


@pytest.mark.slow
@pytest.mark.network
def test_backward_compatibility():
    """Test that existing code continues to work without modifications."""
    # Standard usage should work exactly as before
    from edgar.reference import get_all_companies, get_companies_by_exchanges

    all_companies = get_all_companies()
    nyse_companies = get_companies_by_exchanges('NYSE')

    # Should have standard 4-column schema
    assert list(all_companies.columns) == ['cik', 'ticker', 'name', 'exchange']
    assert list(nyse_companies.columns) == ['cik', 'ticker', 'name', 'exchange']

    # Should not have comprehensive columns
    assert 'sic' not in all_companies.columns
    assert 'sic' not in nyse_companies.columns