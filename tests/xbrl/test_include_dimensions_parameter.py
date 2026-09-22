"""
Tests for include_dimensions parameter functionality

Verifies that users can control dimensional data using include_dimensions parameter.

NOTE: As of Issue #569, include_dimensions=False now uses smart filtering:
- "Face" dimensions (like RelatedPartyTransactionsByRelatedPartyAxis) are preserved
  because they appear on the face of the statement
- "Breakdown" dimensions (like StatementGeographicalAxis, FairValueByHierarchyLevelAxis)
  are filtered out because they are notes disclosure detail

This is more accurate to how the SEC presents financial statements.
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
def test_include_dimensions_false_filters_breakdown_dimensions():
    """
    Test that include_dimensions=False filters out BREAKDOWN dimensions
    but preserves FACE dimensions (like RelatedParty).

    This is the smart filtering behavior from Issue #569.
    """
    apd = Company("APD")
    filing = apd.get_filings(form="10-K").latest(1)
    xbrl = filing.xbrl()
    bs = xbrl.statements.balance_sheet()

    df_without = bs.to_dataframe(include_dimensions=False)

    # Should have dimensional column
    assert 'dimension' in df_without.columns

    # Should have NO breakdown dimensional rows (is_breakdown=True)
    if 'is_breakdown' in df_without.columns:
        breakdown_count = df_without['is_breakdown'].sum()
        assert breakdown_count == 0, f"Expected no breakdown rows but found {breakdown_count}"

    # Face dimensions (like RelatedParty) may still be present
    # This is correct behavior - they appear on the face of the statement


@pytest.mark.network
def test_include_dimensions_filtering_reduces_row_count():
    """
    Test that filtering dimensional data reduces the total row count.

    With smart filtering, breakdown dimensions are removed but face dimensions
    are preserved, so the reduction may not equal total dimensional rows.
    """
    apd = Company("APD")
    filing = apd.get_filings(form="10-K").latest(1)
    xbrl = filing.xbrl()
    bs = xbrl.statements.balance_sheet()

    df_with = bs.to_dataframe(include_dimensions=True)
    df_without = bs.to_dataframe(include_dimensions=False)

    # Filtered version should have fewer or equal rows
    # (fewer if there are breakdown dimensions, equal if none)
    assert len(df_without) <= len(df_with), \
        f"Expected fewer or equal rows without breakdown dimensions, got {len(df_without)} vs {len(df_with)}"

    # The difference should be the number of BREAKDOWN dimensional rows
    if 'is_breakdown' in df_with.columns:
        breakdown_rows = df_with['is_breakdown'].sum()
        row_difference = len(df_with) - len(df_without)
        assert row_difference == breakdown_rows, \
            f"Row difference ({row_difference}) doesn't match breakdown count ({breakdown_rows})"


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
    # Should have no breakdown dimensions
    if 'is_breakdown' in df1.columns:
        assert df1['is_breakdown'].sum() == 0

    # Test with include_unit=True
    df2 = bs.to_dataframe(include_dimensions=False, include_unit=True)
    assert 'unit' in df2.columns
    # Should have no breakdown dimensions
    if 'is_breakdown' in df2.columns:
        assert df2['is_breakdown'].sum() == 0


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
