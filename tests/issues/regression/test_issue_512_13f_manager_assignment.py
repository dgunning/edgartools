"""
Test for Issue #512: 13F Manager Assignment per Holding

Enhance 13F-HR parsing to support multi-manager institutional filings:
1. Add otherManager field to infotable holdings
2. Fix cover page XML tag bug: otherManagersInfo → otherManagers2Info

Performance: Uses session-scoped fixtures from conftest.py to avoid
parsing the same 13F filing multiple times (~10s savings per test).

GitHub Issue: https://github.com/dgunning/edgartools/issues/512
"""
import pandas as pd
import pytest


@pytest.mark.network
def test_13f_other_manager_column_exists(state_street_13f_infotable):
    """Test that OtherManager column is added to holdings DataFrame."""
    holdings_df = state_street_13f_infotable

    # Verify OtherManager column exists
    assert 'OtherManager' in holdings_df.columns, "OtherManager column should be present in holdings DataFrame"


@pytest.mark.network
def test_13f_other_manager_values(state_street_13f_infotable):
    """Test that otherManager values are correctly extracted from holdings."""
    holdings_df = state_street_13f_infotable

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
def test_13f_cover_page_other_managers_2(state_street_13f):
    """Test that cover page correctly parses otherManagers2Info section."""
    thirteenf = state_street_13f

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


@pytest.mark.network
def test_13f_manager_assignment_integration(state_street_13f, state_street_13f_infotable):
    """Test integration: holdings with manager assignments and cover page manager list."""
    thirteenf = state_street_13f

    # Get cover page managers
    cover_page_managers = thirteenf.primary_form_information.cover_page.other_managers

    # Get holdings with manager assignments
    holdings_df = state_street_13f_infotable
    holdings_with_managers = holdings_df[holdings_df['OtherManager'].notna()]

    # Verify data structure is correct
    assert isinstance(cover_page_managers, list), "cover_page_managers should be a list"
    assert isinstance(holdings_df, pd.DataFrame), "holdings should be a DataFrame"
    assert 'OtherManager' in holdings_df.columns, "OtherManager column should exist"

    # `has_data` used to be computed here and then PRINTED, never asserted, so
    # a build that assigned no manager to any holding passed this test with a
    # tidy "Has manager data: False" in output pytest hides by default.
    assert len(cover_page_managers) > 0 or len(holdings_with_managers) > 0, (
        f"neither the cover page ({len(cover_page_managers)} managers) nor the "
        f"holdings ({len(holdings_with_managers)} of {len(holdings_df)} "
        "assigned) carries manager data, which is the whole subject of #512"
    )

    # This filing assigns a manager to EVERY holding — the ids are the
    # summary-page sequence numbers, zero-padded, with '43,01' where two
    # managers share a position.
    assert len(holdings_with_managers) == len(holdings_df) == 26569
    assert set(holdings_df['OtherManager'].unique()) == \
        {'00', '01', '02', '03', '05', '06', '28', '43', '43,01', '88'}


@pytest.mark.network
def test_13f_backward_compatibility(state_street_13f):
    """A filing with no cover-page manager list still parses, and keeps its data.

    NAMING, because it will otherwise mislead: the shared fixture is called
    ``state_street_13f``, but CIK 70858 is Bank of America Corp. The accession
    is what determines the content, and 0001102113-24-000030 is BAC's Q3 2024
    13F-HR.

    WHAT IT ACTUALLY TESTS. Three chained `is not None` assertions could not
    tell this filing from any other, or a fully parsed cover page from an empty
    one. This filing's primary_doc.xml carries no ``otherManagersInfo`` block
    at all -- the old cover-page spelling -- and puts its eight managers in the
    summary page's ``otherManagers2Info`` instead. So an empty
    ``cover_page.other_managers`` is this filing's true shape, and the way to
    show the parser did not simply drop the section is that the rest of the
    cover page is populated and the eight managers are present on the summary
    page.
    """
    thirteenf = state_street_13f
    cover = thirteenf.primary_form_information.cover_page

    assert cover.report_calendar_or_quarter == '09-30-2024'
    assert cover.report_type == '13F HOLDINGS REPORT'
    assert cover.filing_manager.name == 'BANK OF AMERICA CORP /DE/'
    assert cover.is_amendment is False

    assert cover.other_managers == [], (
        f"cover page reports {len(cover.other_managers)} other managers; this "
        "filing has no otherManagersInfo block, so anything here came from "
        "somewhere else"
    )

    # ...and the managers the filing does declare survived, on the summary page.
    summary = thirteenf.primary_form_information.summary_page
    assert len(summary.other_managers) == 8
    assert summary.total_holdings == 26569
    assert summary.total_value == 1_204_606_558_843


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
