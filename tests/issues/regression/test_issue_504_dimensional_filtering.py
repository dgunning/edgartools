"""
Regression tests for Issue #504: Balance sheet line items missing due to dimensional filtering

Issue: https://github.com/dgunning/edgartools/issues/504

Problem: Dimensional facts (related party debt, preferred stock values, class shares, etc.) were being
filtered out of balance sheets even when include_dimensions=True, because _is_dimension_display_statement()
returned False for balance sheets.

Examples:
- APD 2023: Missing "Long-term debt – related party" ($150.7M)
- BBY 2021+: Missing unredeemed gift card liabilities
- HEI 2015+: Missing Class A Common Stock value
- PG 2021: PreferredStockValue showing zero instead of $870M
- HSY 2015: Missing Class B shares value

Fix: Honor include_dimensions parameter - default to True to show all data, let users filter if needed.
"""

import pytest
from edgar import Company


@pytest.mark.network
@pytest.mark.regression
def test_apd_2023_related_party_debt_appears():
    """
    Test that APD 2023 balance sheet includes $150.7M related party debt.

    Before fix: Value was filtered out (0 dimensional rows)
    After fix: Value appears as dimensional row
    """
    apd = Company("APD")
    filings = apd.get_filings(form="10-K")

    # Find 2023 filing
    filing_2023 = None
    for filing in filings:
        if filing.filing_date.year == 2023:
            filing_2023 = filing
            break

    assert filing_2023 is not None, "Could not find APD 2023 10-K filing"

    xbrl = filing_2023.xbrl()
    balance_sheet = xbrl.statements.balance_sheet()

    assert balance_sheet is not None, "Could not load APD balance sheet"

    # Convert to dataframe
    df = balance_sheet.to_dataframe()

    # Verify dimensional column exists
    assert 'dimension' in df.columns, "Dimensional column missing from balance sheet"

    # Verify dimensional rows are present
    dimensional_count = df['dimension'].sum()
    assert dimensional_count > 0, f"Expected dimensional rows but found {dimensional_count}"

    # Find the $150.7M related party debt
    # It should appear in the 2023-09-30 column
    value_col = '2023-09-30'
    assert value_col in df.columns, f"Expected column {value_col} not found"

    # Search for the 150.7M value (150700000)
    found_150_7m = False
    for _, row in df.iterrows():
        value = row[value_col]

        # Check if value matches (within $1000)
        if value and isinstance(value, (int, float)):
            if abs(value - 150700000) < 1000:
                # Verify it's dimensional and related to long-term debt
                assert row['dimension'] == True, "Found 150.7M but it's not marked as dimensional"
                assert 'LongTermDebt' in row['concept'], f"Found 150.7M but wrong concept: {row['concept']}"
                found_150_7m = True
                break

    assert found_150_7m, (
        "Did not find $150.7M related party debt in APD balance sheet. "
        "This suggests dimensional filtering is broken again."
    )


@pytest.mark.network
@pytest.mark.regression
def test_balance_sheet_includes_dimensional_data_by_default():
    """
    Test that balance sheets include dimensional data by default (include_dimensions=True).

    This is a general test to ensure dimensional data isn't being filtered out.
    """
    # Use Apple as a reference company
    aapl = Company("AAPL")
    filing = aapl.get_filings(form="10-K").latest(1)

    xbrl = filing.xbrl()
    balance_sheet = xbrl.statements.balance_sheet()

    assert balance_sheet is not None, "Could not load AAPL balance sheet"

    df = balance_sheet.to_dataframe()

    # Verify dimensional column exists
    assert 'dimension' in df.columns, "Dimensional column missing"

    # The presence of dimensional rows depends on the company's filing
    # So we just verify the infrastructure is in place
    print(f"Balance sheet has {df['dimension'].sum()} dimensional rows out of {len(df)} total rows")


# TODO: Add test for include_dimensions=False after implementing that filtering
# Currently the parameter exists but filtering happens at statement_data level,
# not at the xbrl.get_statement() level. This is a separate enhancement.
