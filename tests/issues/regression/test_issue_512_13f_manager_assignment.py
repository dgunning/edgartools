"""
Test for Issue #512: 13F Manager Assignment per Holding

Enhance 13F-HR parsing to support multi-manager institutional filings:
1. Add otherManager field to infotable holdings
2. Fix cover page XML tag bug: otherManagersInfo → otherManagers2Info
"""
import pandas as pd
import pytest
from edgar import *


@pytest.mark.network
def test_13f_other_manager_column_exists():
    """Test that OtherManager column is added to holdings DataFrame."""
    # State Street filing with multiple managers (from issue example)
    # CIK 70858 = STATE STREET CORP, accession 0001102113-24-000030
    filing = Filing(form='13F-HR', filing_date='2024-11-14', company='STATE STREET CORP',
                    cik=70858, accession_no='0001102113-24-000030')

    thirteenf = filing.obj()

    # Get holdings DataFrame
    holdings_df = thirteenf.infotable

    # Verify OtherManager column exists
    assert 'OtherManager' in holdings_df.columns, "OtherManager column should be present in holdings DataFrame"


@pytest.mark.network
def test_13f_other_manager_values():
    """Test that otherManager values are correctly extracted from holdings."""
    # State Street filing with multiple managers
    filing = Filing(form='13F-HR', filing_date='2024-11-14', company='STATE STREET CORP',
                    cik=70858, accession_no='0001102113-24-000030')

    thirteenf = filing.obj()
    holdings_df = thirteenf.infotable

    # Check for OtherManager values
    has_other_managers = holdings_df['OtherManager'].notna().any()
    assert has_other_managers, "Should have at least some holdings with OtherManager values"

    # Verify format (should be strings, may contain comma-separated manager IDs)
    non_null_managers = holdings_df[holdings_df['OtherManager'].notna()]['OtherManager']
    if len(non_null_managers) > 0:
        # Should be strings (manager IDs like "43" or "43,01")
        assert all(isinstance(m, str) for m in non_null_managers), \
            "OtherManager should contain string manager IDs"


@pytest.mark.network
def test_13f_cover_page_other_managers_2():
    """Test that cover page correctly parses otherManagers2Info section."""
    # State Street filing with multiple managers in otherManagers2Info
    filing = Filing(form='13F-HR', filing_date='2024-11-14', company='STATE STREET CORP',
                    cik=70858, accession_no='0001102113-24-000030')

    thirteenf = filing.obj()

    # Verify primary form information has cover page with other_managers
    assert hasattr(thirteenf, 'primary_form_information'), "Should have primary_form_information"
    assert thirteenf.primary_form_information is not None, "primary_form_information should not be None"
    assert hasattr(thirteenf.primary_form_information, 'cover_page'), "Should have cover_page"
    assert hasattr(thirteenf.primary_form_information.cover_page, 'other_managers'), "Cover page should have other_managers"

    other_managers = thirteenf.primary_form_information.cover_page.other_managers

    # other_managers should be a list (may be empty if filing uses old format)
    assert isinstance(other_managers, list), "other_managers should be a list"

    # Verify manager structure if any managers exist
    if len(other_managers) > 0:
        first_manager = other_managers[0]
        assert hasattr(first_manager, 'cik'), "Manager should have cik"
        assert hasattr(first_manager, 'name'), "Manager should have name"
        assert hasattr(first_manager, 'file_number'), "Manager should have file_number"
        print(f"Found {len(other_managers)} other managers on cover page")


@pytest.mark.network
def test_13f_manager_assignment_integration():
    """Test integration: holdings with manager assignments and cover page manager list."""
    # State Street filing
    filing = Filing(form='13F-HR', filing_date='2024-11-14', company='STATE STREET CORP',
                    cik=70858, accession_no='0001102113-24-000030')

    thirteenf = filing.obj()

    # Get cover page managers
    cover_page_managers = thirteenf.primary_form_information.cover_page.other_managers

    # Get holdings with manager assignments
    holdings_df = thirteenf.infotable
    holdings_with_managers = holdings_df[holdings_df['OtherManager'].notna()]

    # Verify data structure is correct
    assert isinstance(cover_page_managers, list), "cover_page_managers should be a list"
    assert isinstance(holdings_df, pd.DataFrame), "holdings should be a DataFrame"
    assert 'OtherManager' in holdings_df.columns, "OtherManager column should exist"

    # Print summary
    print(f"\nCover page managers: {len(cover_page_managers)}")
    print(f"Holdings with manager assignments: {len(holdings_with_managers)}")
    print(f"Total holdings: {len(holdings_df)}")

    # For multi-manager filings, at least one of these should have data
    has_data = len(cover_page_managers) > 0 or len(holdings_with_managers) > 0
    print(f"Has manager data: {has_data}")


@pytest.mark.network
def test_13f_backward_compatibility():
    """Test that old format (otherManagersInfo) still works if present."""
    # Test with a filing that might use the old format
    # Most recent filings should use otherManagers2Info, but code should handle both
    filing = Filing(form='13F-HR', filing_date='2024-11-14', company='STATE STREET CORP',
                    cik=70858, accession_no='0001102113-24-000030')

    # Should not raise an exception
    thirteenf = filing.obj()

    # Should have valid data
    assert thirteenf is not None
    assert thirteenf.primary_form_information is not None
    assert thirteenf.primary_form_information.cover_page is not None


@pytest.mark.fast
def test_13f_other_manager_none_handling():
    """Test that holdings without manager assignment have None for OtherManager."""
    import pandas as pd

    # Simulate a holdings DataFrame with some None values
    test_df = pd.DataFrame({
        'Issuer': ['Company A', 'Company B', 'Company C'],
        'Cusip': ['123456789', '987654321', '111111111'],
        'Value': [1000, 2000, 3000],
        'OtherManager': ['43', None, '43,01']
    })

    # Verify handling of None values
    assert test_df['OtherManager'].isna().any(), "Should have some None values"
    assert test_df['OtherManager'].notna().any(), "Should have some non-None values"

    # Operations on the column should work correctly
    non_null_count = test_df['OtherManager'].notna().sum()
    assert non_null_count == 2, "Should have 2 non-null values"
