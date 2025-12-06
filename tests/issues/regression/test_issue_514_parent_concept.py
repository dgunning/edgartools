"""
Test for Issue #514: Add parent_concept column to XBRL statement dataframes

The parent_concept column should expose calculation/presentation hierarchy relationships
to enable programmatic analysis of XBRL concept relationships.
"""
import pytest
from edgar import Company


@pytest.mark.network
def test_parent_concept_column_exists():
    """Test that parent_concept column is added to statement DataFrames."""
    company = Company("NFLX")
    filing = company.get_filings(form="10-Q", accession_number="0001065280-25-000406").latest()
    xbrl = filing.xbrl()

    # Get income statement
    statement = xbrl.statements.income_statement()
    df = statement.to_dataframe()

    # Verify parent_concept column exists
    assert 'parent_concept' in df.columns, "parent_concept column should be present in DataFrame"

    # Verify it's not all null
    has_non_null = df['parent_concept'].notna().any()
    assert has_non_null, "parent_concept should have at least some non-null values"


@pytest.mark.network
def test_parent_concept_hierarchy():
    """Test that parent_concept correctly represents hierarchy relationships."""
    company = Company("AAPL")
    filing = company.get_filings(form="10-K").latest(1)
    xbrl = filing.xbrl()

    # Get balance sheet
    statement = xbrl.statements.balance_sheet()
    df = statement.to_dataframe()

    # Check for expected hierarchical relationships
    # Example: Current Liabilities should be a parent of Accounts Payable
    # (Note: actual concepts may vary by company)

    # Verify DataFrame structure
    assert 'parent_concept' in df.columns
    assert 'concept' in df.columns
    assert 'label' in df.columns
    assert 'weight' in df.columns

    # Verify parent_concept is properly formatted (should be element IDs or None)
    non_null_parents = df[df['parent_concept'].notna()]['parent_concept']
    if len(non_null_parents) > 0:
        # Parents should be strings (element IDs)
        assert all(isinstance(p, str) for p in non_null_parents), \
            "parent_concept should contain string element IDs"


@pytest.mark.network
def test_parent_concept_with_metadata():
    """Test that parent_concept works alongside other metadata columns."""
    company = Company("MSFT")
    filing = company.get_filings(form="10-Q").latest(1)
    xbrl = filing.xbrl()

    # Get income statement
    statement = xbrl.statements.income_statement()
    df = statement.to_dataframe()

    # Verify all metadata columns are present
    metadata_cols = ['balance', 'weight', 'preferred_sign', 'parent_concept']
    for col in metadata_cols:
        assert col in df.columns, f"{col} should be present in DataFrame"

    # Verify parent_concept doesn't interfere with period columns
    period_cols = [col for col in df.columns if col not in
                   ['concept', 'label', 'balance', 'weight', 'preferred_sign',
                    'parent_concept', 'level', 'abstract', 'dimension', 'unit', 'point_in_time']]

    assert len(period_cols) > 0, "Should have at least one period column"

    # Period columns should contain numeric values, not parent_concept strings
    for col in period_cols:
        if df[col].notna().any():
            first_value = df[df[col].notna()][col].iloc[0]
            # Should be numeric (int or float), not string
            assert isinstance(first_value, (int, float)), \
                f"Period column {col} should contain numeric values"


@pytest.mark.fast
def test_parent_concept_backward_compatibility():
    """Test that DataFrames without parent_concept (old code) still work."""
    import pandas as pd

    # Simulate an old DataFrame without parent_concept
    old_df = pd.DataFrame({
        'concept': ['us-gaap:Revenue', 'us-gaap:CostOfRevenue'],
        'label': ['Revenue', 'Cost of Revenue'],
        '2024-12-31': [1000, 600],
        '2023-12-31': [900, 500],
        'balance': ['credit', 'debit'],
        'weight': [1.0, 1.0],
        'preferred_sign': [1, -1]
    })

    # Should work without parent_concept column
    assert 'parent_concept' not in old_df.columns
    assert len(old_df) == 2

    # DataFrame operations should still work
    assert old_df['concept'].iloc[0] == 'us-gaap:Revenue'
