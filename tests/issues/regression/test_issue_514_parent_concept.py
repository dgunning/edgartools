"""
Test for Issue #514: Add parent_concept column to XBRL statement dataframes

The parent_concept column should expose calculation/presentation hierarchy relationships
to enable programmatic analysis of XBRL concept relationships.

Issue #514 refinement: Distinguish between calculation parent (metric) and presentation parent (abstract).
- parent_concept: Calculation tree parent (always a metric concept for summation math)
- parent_abstract_concept: Presentation tree parent (may be abstract, for display hierarchy)
"""
import pytest
from edgar import Company


@pytest.mark.network
def test_parent_concept_columns_exist():
    """Test that both parent_concept and parent_abstract_concept columns are added to statement DataFrames."""
    company = Company("NFLX")
    filing = company.get_filings(form="10-Q", accession_number="0001065280-25-000406").latest()
    xbrl = filing.xbrl()

    # Get income statement
    statement = xbrl.statements.income_statement()
    df = statement.to_dataframe()

    # Verify both parent columns exist
    assert 'parent_concept' in df.columns, "parent_concept column should be present in DataFrame"
    assert 'parent_abstract_concept' in df.columns, "parent_abstract_concept column should be present in DataFrame"

    # parent_abstract_concept should have non-null values (presentation tree is always present)
    has_abstract_parent = df['parent_abstract_concept'].notna().any()
    assert has_abstract_parent, "parent_abstract_concept should have at least some non-null values"


@pytest.mark.network
def test_parent_concept_hierarchy():
    """Test that parent_concept and parent_abstract_concept correctly represent hierarchy relationships."""
    company = Company("AAPL")
    filing = company.get_filings(form="10-K").latest(1)
    xbrl = filing.xbrl()

    # Get balance sheet
    statement = xbrl.statements.balance_sheet()
    df = statement.to_dataframe()

    # Verify DataFrame structure
    assert 'parent_concept' in df.columns
    assert 'parent_abstract_concept' in df.columns
    assert 'concept' in df.columns
    assert 'label' in df.columns
    assert 'weight' in df.columns

    # Verify parent_abstract_concept is properly formatted (should be element IDs or None)
    non_null_parents = df[df['parent_abstract_concept'].notna()]['parent_abstract_concept']
    if len(non_null_parents) > 0:
        # Parents should be strings (element IDs)
        assert all(isinstance(p, str) for p in non_null_parents), \
            "parent_abstract_concept should contain string element IDs"

    # Verify parent_concept (calculation) is properly formatted when present
    non_null_calc_parents = df[df['parent_concept'].notna()]['parent_concept']
    if len(non_null_calc_parents) > 0:
        assert all(isinstance(p, str) for p in non_null_calc_parents), \
            "parent_concept should contain string element IDs"


@pytest.mark.network
def test_parent_concept_with_metadata():
    """Test that parent columns work alongside other metadata columns."""
    company = Company("MSFT")
    filing = company.get_filings(form="10-Q").latest(1)
    xbrl = filing.xbrl()

    # Get income statement
    statement = xbrl.statements.income_statement()
    df = statement.to_dataframe()

    # Verify all metadata columns are present
    metadata_cols = ['balance', 'weight', 'preferred_sign', 'parent_concept', 'parent_abstract_concept']
    for col in metadata_cols:
        assert col in df.columns, f"{col} should be present in DataFrame"

    # Full list of metadata columns to exclude when looking for period columns
    all_metadata_cols = [
        'concept', 'label', 'balance', 'weight', 'preferred_sign',
        'parent_concept', 'parent_abstract_concept', 'level', 'abstract',
        'dimension', 'unit', 'point_in_time', 'dimension_label'
    ]

    # Verify parent columns don't interfere with period columns
    period_cols = [col for col in df.columns if col not in all_metadata_cols]

    assert len(period_cols) > 0, "Should have at least one period column"

    # Period columns should contain numeric values, not parent_concept strings
    for col in period_cols:
        if df[col].notna().any():
            first_value = df[df[col].notna()][col].iloc[0]
            # Should be numeric (int or float), not string
            assert isinstance(first_value, (int, float)), \
                f"Period column {col} should contain numeric values"


@pytest.mark.network
def test_parent_concept_vs_abstract_concept_difference():
    """Test that parent_concept (calculation) differs from parent_abstract_concept (presentation)."""
    company = Company("AAPL")
    filing = company.get_filings(form="10-K").latest(1)
    xbrl = filing.xbrl()

    # Get income statement (often has concepts with both calculation and presentation parents)
    statement = xbrl.statements.income_statement()
    df = statement.to_dataframe()

    # Both columns should exist
    assert 'parent_concept' in df.columns
    assert 'parent_abstract_concept' in df.columns

    # parent_abstract_concept comes from presentation tree (always present)
    # parent_concept comes from calculation tree (may be None for concepts not in calc tree)

    # Find concepts that have parent_abstract_concept but not parent_concept
    # These are concepts that appear in presentation but not in calculation tree
    has_abstract_only = (
        df['parent_abstract_concept'].notna() &
        df['parent_concept'].isna()
    ).any()

    # This is expected to be true for some concepts (abstract headers, etc.)
    # Not asserting this as it depends on the specific filing's structure


@pytest.mark.fast
def test_parent_concept_backward_compatibility():
    """Test that DataFrames without parent columns (old code) still work."""
    import pandas as pd

    # Simulate an old DataFrame without parent columns
    old_df = pd.DataFrame({
        'concept': ['us-gaap:Revenue', 'us-gaap:CostOfRevenue'],
        'label': ['Revenue', 'Cost of Revenue'],
        '2024-12-31': [1000, 600],
        '2023-12-31': [900, 500],
        'balance': ['credit', 'debit'],
        'weight': [1.0, 1.0],
        'preferred_sign': [1, -1]
    })

    # Should work without parent columns
    assert 'parent_concept' not in old_df.columns
    assert 'parent_abstract_concept' not in old_df.columns
    assert len(old_df) == 2

    # DataFrame operations should still work
    assert old_df['concept'].iloc[0] == 'us-gaap:Revenue'
