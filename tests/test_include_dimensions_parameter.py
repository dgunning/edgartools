"""
Tests for include_dimensions parameter functionality

Verifies that users can opt-out of dimensional data using include_dimensions=False
"""

import pytest
from edgar import Company


@pytest.mark.network
def test_include_dimensions_true_shows_dimensional_data():
    """
    Test that include_dimensions=True (default) includes dimensional data
    """
    apd = Company("APD")
    filing = apd.get_filings(form="10-K").latest(1)
    xbrl = filing.xbrl()
    bs = xbrl.statements.balance_sheet()

    df_with = bs.to_dataframe(include_dimensions=True)

    # Should have dimensional column
    assert 'dimension' in df_with.columns

    # Should have some dimensional rows
    dimensional_count = df_with['dimension'].sum()
    assert dimensional_count > 0, "Expected dimensional rows but found none"


@pytest.mark.network
def test_include_dimensions_false_filters_dimensional_data():
    """
    Test that include_dimensions=False filters out dimensional data
    """
    apd = Company("APD")
    filing = apd.get_filings(form="10-K").latest(1)
    xbrl = filing.xbrl()
    bs = xbrl.statements.balance_sheet()

    df_without = bs.to_dataframe(include_dimensions=False)

    # Should have dimensional column
    assert 'dimension' in df_without.columns

    # Should have NO dimensional rows
    dimensional_count = df_without['dimension'].sum()
    assert dimensional_count == 0, f"Expected no dimensional rows but found {dimensional_count}"


@pytest.mark.network
def test_include_dimensions_filtering_reduces_row_count():
    """
    Test that filtering dimensional data reduces the total row count
    """
    apd = Company("APD")
    filing = apd.get_filings(form="10-K").latest(1)
    xbrl = filing.xbrl()
    bs = xbrl.statements.balance_sheet()

    df_with = bs.to_dataframe(include_dimensions=True)
    df_without = bs.to_dataframe(include_dimensions=False)

    # Filtered version should have fewer rows
    assert len(df_without) < len(df_with), \
        f"Expected fewer rows without dimensions, got {len(df_without)} vs {len(df_with)}"

    # The difference should be the number of dimensional rows
    dimensional_rows = df_with['dimension'].sum()
    row_difference = len(df_with) - len(df_without)

    assert row_difference == dimensional_rows, \
        f"Row difference ({row_difference}) doesn't match dimensional count ({dimensional_rows})"


@pytest.mark.network
def test_include_dimensions_parameter_compatibility():
    """
    Test that include_dimensions parameter works with other parameters
    """
    apd = Company("APD")
    filing = apd.get_filings(form="10-K").latest(1)
    xbrl = filing.xbrl()
    bs = xbrl.statements.balance_sheet()

    # Test with standard=False
    df1 = bs.to_dataframe(include_dimensions=False, standard=False)
    assert len(df1) > 0
    assert df1['dimension'].sum() == 0

    # Test with include_unit=True
    df2 = bs.to_dataframe(include_dimensions=False, include_unit=True)
    assert 'unit' in df2.columns
    assert df2['dimension'].sum() == 0


@pytest.mark.network
def test_include_dimensions_when_include_dimensions_is_true():
    """
    Test that the default behavior is to include dimensional data
    """
    apd = Company("APD")
    filing = apd.get_filings(form="10-K").latest(1)
    xbrl = filing.xbrl()
    bs = xbrl.statements.balance_sheet(include_dimensions=True)

    # Call without specifying include_dimensions (should default to True)
    df_default = bs.to_dataframe()

    # Should have dimensional rows
    dimensional_count = df_default['dimension'].sum()
    assert dimensional_count > 0, \
        "Default behavior should include dimensional data"
