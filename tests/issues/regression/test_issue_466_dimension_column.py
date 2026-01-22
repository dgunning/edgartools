"""
Regression test for Issue #466: Dimension column always False

Ensures dimensional line items are correctly tagged with dimension=True
in XBRL statement DataFrames.

GitHub Issue: https://github.com/dgunning/edgartools/issues/466
Regression: Introduced in v4.21.0 Issue #463 refactoring
Fixed: v4.21.2
"""
import pytest
from edgar import Company


# Auto-marked as @pytest.mark.regression by conftest.py


@pytest.mark.network
def test_issue_466_dimension_column_tagging():
    """Test that dimension column correctly identifies dimensional line items

    Note: As of v5.7.0, include_dimensions defaults to False for cleaner output.
    This test explicitly enables dimensions to test dimension column tagging.
    """

    # Use AAPL 2024 10-K as reported in issue
    company = Company("AAPL")
    filing = company.get_filings(form="10-K", year=2024).latest()
    statement = filing.xbrl().statements.income_statement()
    df = statement.to_dataframe(include_dimensions=True)

    # Verify dimension column exists
    assert 'dimension' in df.columns, "dimension column should exist in DataFrame"

    # Verify we have both dimensional and non-dimensional rows
    dimension_values = df['dimension'].unique()
    assert True in dimension_values, f"Should have rows with dimension=True, found only: {dimension_values}"
    assert False in dimension_values, "Should have rows with dimension=False"

    # Count dimensional rows
    dimensional_rows = df[df['dimension'] == True]
    assert len(dimensional_rows) > 0, f"Should have dimensional rows, found {len(dimensional_rows)}"

    print(f"✓ Test passed: {len(dimensional_rows)} dimensional rows found")


@pytest.mark.network
def test_issue_466_msft_dimensional_data():
    """Test dimensional data with MSFT filing known to have segment data

    Note: As of v5.7.0, include_dimensions defaults to False for cleaner output.
    This test explicitly enables dimensions to test dimensional data extraction.
    """

    # Use Microsoft filing from Issue #416 which has extensive dimensional data
    filing = Company('MSFT').get_filings().filter(accession_number="0000950170-25-100235").latest()
    statement = filing.xbrl().statements.income_statement()
    df = statement.to_dataframe(include_dimensions=True)

    # Verify dimension column exists
    assert 'dimension' in df.columns, "dimension column should exist in DataFrame"

    # MSFT has dimensional revenue breakdowns
    dimensional_rows = df[df['dimension'] == True]
    assert len(dimensional_rows) > 10, f"MSFT should have many dimensional rows, found {len(dimensional_rows)}"

    # Verify dimensional revenue facts exist
    revenue_rows = df[
        (df['concept'] == 'us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax') &
        (df['dimension'] == True)
    ]
    assert len(revenue_rows) >= 4, f"Expected multiple dimensional revenue rows, found {len(revenue_rows)}"

    print(f"✓ Test passed: {len(dimensional_rows)} dimensional rows, {len(revenue_rows)} revenue segments")


@pytest.mark.network
def test_issue_466_dimension_filtering():
    """Test that dimensional filtering works correctly after fix

    Note: As of v5.7.0, include_dimensions defaults to False for cleaner output.
    This test explicitly enables dimensions to test dimensional filtering.
    """

    # Use MSFT filing with known dimensional data
    filing = Company('MSFT').get_filings().filter(accession_number="0000950170-25-100235").latest()
    statement = filing.xbrl().statements.income_statement()
    df = statement.to_dataframe(include_dimensions=True)

    # Filter for dimensional rows only
    dimensional_df = df[df['dimension'] == True]

    # Should have rows
    assert len(dimensional_df) > 0, "Dimensional filtering should return rows"

    # All rows should have dimension=True
    assert all(dimensional_df['dimension'] == True), "All filtered rows should have dimension=True"

    # Filter for non-dimensional rows only
    non_dimensional_df = df[df['dimension'] == False]

    # Should have rows
    assert len(non_dimensional_df) > 0, "Non-dimensional filtering should return rows"

    # All rows should have dimension=False
    assert all(non_dimensional_df['dimension'] == False), "All filtered rows should have dimension=False"

    # Together should equal total
    assert len(dimensional_df) + len(non_dimensional_df) == len(df), \
        "Dimensional + non-dimensional should equal total rows"

    print(f"✓ Test passed: Filtering works correctly ({len(dimensional_df)} dimensional, {len(non_dimensional_df)} non-dimensional)")


if __name__ == "__main__":
    # Run tests directly
    test_issue_466_dimension_column_tagging()
    test_issue_466_msft_dimensional_data()
    test_issue_466_dimension_filtering()
    print("All Issue #466 regression tests passed!")
