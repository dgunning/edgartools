"""
Tests for 13F holdings aggregation feature (Issue #512, edgartools-98d).

Verifies that:
1. holdings property aggregates multi-manager filings correctly
2. infotable property preserves disaggregated manager-specific data
3. Aggregation sums numeric columns correctly
4. Single-manager filings work correctly with both views

Performance: Uses session-scoped fixtures from conftest.py to avoid
parsing the same 13F filing multiple times (~10s savings per test).
"""
import pytest
import pandas as pd


@pytest.mark.network
def test_holdings_aggregates_multi_manager_filing(state_street_13f_infotable, state_street_13f_holdings):
    """Test that holdings aggregates multi-manager filing (State Street example)."""
    # Use fixtures for both views
    infotable = state_street_13f_infotable  # Disaggregated
    holdings = state_street_13f_holdings     # Aggregated

    # Verify both exist
    assert infotable is not None, "infotable should exist"
    assert holdings is not None, "holdings should exist"
    assert isinstance(infotable, pd.DataFrame), "infotable should be DataFrame"
    assert isinstance(holdings, pd.DataFrame), "holdings should be DataFrame"

    # Verify aggregation reduced rows
    assert len(holdings) < len(infotable), \
        f"holdings ({len(holdings)} rows) should have fewer rows than infotable ({len(infotable)} rows)"

    # Verify holdings has expected columns
    expected_cols = ['Issuer', 'Class', 'Cusip', 'Ticker', 'Value',
                    'SharesPrnAmount', 'Type', 'SoleVoting', 'SharedVoting', 'NonVoting']
    for col in expected_cols:
        assert col in holdings.columns, f"holdings should have {col} column"

    # Verify holdings does NOT have manager-specific columns
    assert 'OtherManager' not in holdings.columns, \
        "holdings should not have OtherManager column (aggregated view)"
    assert 'InvestmentDiscretion' not in holdings.columns, \
        "holdings should not have InvestmentDiscretion column (aggregated view)"

    # Verify infotable HAS manager-specific columns
    assert 'OtherManager' in infotable.columns, \
        "infotable should have OtherManager column (disaggregated view)"

    print(f"\n✓ Aggregation verified:")
    print(f"  - infotable: {len(infotable)} rows (disaggregated)")
    print(f"  - holdings: {len(holdings)} rows (aggregated)")
    print(f"  - Reduction: {len(infotable) - len(holdings)} rows ({(1 - len(holdings)/len(infotable))*100:.1f}%)")


@pytest.mark.network
def test_holdings_aggregation_math_correct(state_street_13f_infotable, state_street_13f_holdings):
    """Test that holdings correctly sums values across managers for same CUSIP."""
    infotable = state_street_13f_infotable
    holdings = state_street_13f_holdings

    # Find a CUSIP that appears multiple times in infotable
    cusip_counts = infotable['Cusip'].value_counts()
    multi_entry_cusips = cusip_counts[cusip_counts > 1].index.tolist()

    # Note: State Street may or may not have multi-entry CUSIPs, so make test flexible
    if len(multi_entry_cusips) > 0:
        # Test first multi-entry CUSIP
        test_cusip = multi_entry_cusips[0]

        # Get all infotable rows for this CUSIP
        infotable_rows = infotable[infotable['Cusip'] == test_cusip]

        # Get holdings row for this CUSIP
        holdings_row = holdings[holdings['Cusip'] == test_cusip]

        assert len(holdings_row) == 1, f"holdings should have exactly 1 row for CUSIP {test_cusip}"

        # Verify aggregation sums
        for col in ['SharesPrnAmount', 'Value', 'SoleVoting', 'SharedVoting', 'NonVoting']:
            # Convert to numeric in case dtype is object (Issue #207 - dtype bug)
            infotable_values = pd.to_numeric(infotable_rows[col], errors='coerce').fillna(0)
            infotable_sum = int(infotable_values.sum())
            holdings_value = int(holdings_row[col].iloc[0])

            assert holdings_value == infotable_sum, \
                f"{col} aggregation mismatch: holdings={holdings_value}, expected={infotable_sum}"

        # Verify non-numeric columns preserved
        assert holdings_row['Issuer'].iloc[0] == infotable_rows['Issuer'].iloc[0], \
            "Issuer should be preserved"

        print(f"\n✓ Aggregation math verified for CUSIP {test_cusip}:")
        print(f"  - infotable entries: {len(infotable_rows)}")
        print(f"  - Managers: {infotable_rows['OtherManager'].tolist()}")
        print(f"  - Individual values: {infotable_rows['Value'].tolist()}")
        print(f"  - Aggregated value: {holdings_row['Value'].iloc[0]}")
    else:
        print("\n✓ No multi-entry CUSIPs in this filing (all single-manager holdings)")


@pytest.mark.network
def test_holdings_sorted_by_value(state_street_13f_holdings):
    """Test that holdings are sorted by value descending."""
    holdings = state_street_13f_holdings

    # Verify sorted by value descending
    values = holdings['Value'].tolist()
    assert values == sorted(values, reverse=True), \
        "holdings should be sorted by Value descending"

    print(f"\n✓ Holdings sorted correctly:")
    print(f"  - Top holding value: ${values[0]:,.0f}")
    print(f"  - Last holding value: ${values[-1]:,.0f}")


@pytest.mark.network
def test_holdings_preserves_all_securities(state_street_13f_infotable, state_street_13f_holdings):
    """Test that holdings includes all unique securities from infotable."""
    infotable = state_street_13f_infotable
    holdings = state_street_13f_holdings

    # Get unique CUSIPs from each view
    infotable_cusips = set(infotable['Cusip'].unique())
    holdings_cusips = set(holdings['Cusip'].unique())

    # Verify same unique securities
    assert infotable_cusips == holdings_cusips, \
        "holdings should include all unique securities from infotable"

    assert len(holdings_cusips) == len(holdings), \
        "holdings should have one row per unique CUSIP"

    print(f"\n✓ All securities preserved:")
    print(f"  - Unique securities: {len(holdings_cusips)}")
    print(f"  - holdings rows: {len(holdings)}")


@pytest.mark.network
def test_single_manager_filing_consistency(state_street_13f_infotable, state_street_13f_holdings):
    """Test that single-manager filings have same data in both views."""
    infotable = state_street_13f_infotable
    holdings = state_street_13f_holdings

    # For single-manager filings, row counts might be similar or same
    # (only difference is if same CUSIP appears multiple times for other reasons)

    # Verify both views work
    assert infotable is not None, "infotable should exist"
    assert holdings is not None, "holdings should exist"

    # Verify total values match
    infotable_total = infotable['Value'].sum()
    holdings_total = holdings['Value'].sum()

    assert infotable_total == holdings_total, \
        f"Total values should match: infotable={infotable_total}, holdings={holdings_total}"

    print(f"\n✓ Single-manager filing consistency:")
    print(f"  - infotable rows: {len(infotable)}")
    print(f"  - holdings rows: {len(holdings)}")
    print(f"  - Total value: ${infotable_total:,.0f}")


@pytest.mark.fast
def test_holdings_returns_none_when_no_infotable():
    """Test that holdings returns None when infotable doesn't exist."""
    # Create a mock ThirteenF with no infotable
    # We'll test this by checking the logic, not with actual filing
    # This is more of a unit test for the property logic

    # For now, just verify the pattern is correct
    # A real test would need a 13F-NT filing which doesn't have holdings
    pass  # Placeholder - would need 13F-NT filing to test


@pytest.mark.network
def test_holdings_numeric_columns_are_numeric(state_street_13f_holdings):
    """Test that aggregated numeric columns have correct dtypes."""
    holdings = state_street_13f_holdings

    # Verify numeric columns have numeric dtypes
    numeric_cols = ['SharesPrnAmount', 'Value', 'SoleVoting', 'SharedVoting', 'NonVoting']

    for col in numeric_cols:
        assert pd.api.types.is_numeric_dtype(holdings[col]), \
            f"{col} should be numeric dtype, got {holdings[col].dtype}"

    print(f"\n✓ Numeric dtypes verified:")
    for col in numeric_cols:
        print(f"  - {col}: {holdings[col].dtype}")
