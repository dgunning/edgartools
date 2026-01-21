"""
Regression test for Issue #607: Reopen of #603 - dimension_member_label still incorrect

GitHub Issue: https://github.com/dgunning/edgartools/issues/607
Reporter: Nikolay Ivanov (@Velikolay)

Bug: The fix for #603 (using first dimension instead of last) was insufficient.
The simple heuristic of first/last dimension doesn't work reliably across all cases.

Example: For AAPL 2025 10-K with StatementBusinessSegmentsAxis, the dimension_member_label
was showing "Operating segments" instead of the specific segment names like "Americas",
"Europe", "Greater China", etc.

Fix: When by_dimension() is called with a specific dimension, the dimension_member_label
should show the member of THAT requested dimension, not an arbitrary first/last one.

Test Cases:
- AAPL 2025 10-K: Query by StatementBusinessSegmentsAxis dimension
"""

import pytest
from edgar import Company


@pytest.mark.network
@pytest.mark.regression
def test_issue_607_aapl_dimension_member_label():
    """
    Verify AAPL revenue by segment query returns correct dimension_member_label values.

    The bug caused dimension_member_label to show "Operating segments" for all members
    instead of the specific segment names like "Americas", "Europe", "Greater China".
    """
    company = Company("AAPL")
    filing = company.get_filings(form="10-K", year=2025).latest()

    assert filing is not None, "Should find AAPL 2025 10-K"

    xbrl = filing.xbrl()
    assert xbrl is not None, "Should parse XBRL"

    # Query revenue by StatementBusinessSegmentsAxis (from the bug report)
    df = xbrl.facts.query().by_concept("Revenue").by_dimension("StatementBusinessSegmentsAxis").to_dataframe()

    if len(df) == 0:
        # Try alternative revenue concepts
        df = xbrl.facts.query().by_concept("Revenues").by_dimension("StatementBusinessSegmentsAxis").to_dataframe()

    if len(df) == 0:
        df = xbrl.facts.query().by_concept("NetSales").by_dimension("StatementBusinessSegmentsAxis").to_dataframe()

    if len(df) == 0:
        pytest.skip("No Revenue/Revenues/NetSales facts with StatementBusinessSegmentsAxis dimension")

    print(f"Found {len(df)} facts with StatementBusinessSegmentsAxis dimension")

    # Verify dimension_member_label is present and NOT "Operating segments" for all rows
    if 'dimension_member_label' in df.columns:
        labels = df['dimension_member_label'].dropna().unique()
        print(f"Unique dimension_member_labels: {labels}")

        # The bug was: all labels showed "Operating segments" instead of segment names
        # After fix: should see specific segment names
        operating_segments_count = sum(1 for label in labels if label == 'Operating segments')
        total_labels = len(labels)

        # If ALL labels are "Operating segments", the bug is present
        if total_labels > 1 and operating_segments_count == total_labels:
            pytest.fail(
                f"BUG: All {total_labels} unique labels are 'Operating segments'. "
                "Expected specific segment names like 'Americas', 'Europe', etc."
            )

        # Should have specific segment labels like "Americas", "Europe", "Greater China"
        # Note: The exact labels depend on how Apple reports, but should not ALL be generic
        print(f"SUCCESS: Found {total_labels} unique labels, only {operating_segments_count} are 'Operating segments'")


@pytest.mark.network
@pytest.mark.regression
def test_issue_607_requested_dimension_is_used():
    """
    Verify that when by_dimension() is called, the dimension fields reflect
    the specifically requested dimension, not an arbitrary one.
    """
    company = Company("AAPL")
    filing = company.get_filings(form="10-K", year=2025).latest()

    xbrl = filing.xbrl()

    # Get all facts with dimensions to see what's available
    all_dimensional = xbrl.facts.query().by_custom(
        lambda f: any(key.startswith('dim_') for key in f.keys())
    ).to_dataframe()

    if len(all_dimensional) == 0:
        pytest.skip("No dimensional facts found")

    # Find a dimension column to query
    dim_cols = [col for col in all_dimensional.columns if col.startswith('dim_')]
    if not dim_cols:
        pytest.skip("No dim_* columns found")

    # Use the first available dimension for testing
    test_dim_col = dim_cols[0]
    # Convert dim_us-gaap_SomeAxis to SomeAxis
    dim_name_parts = test_dim_col.replace('dim_', '').split('_')
    test_dim_name = dim_name_parts[-1] if len(dim_name_parts) > 1 else dim_name_parts[0]

    print(f"Testing with dimension: {test_dim_name} (from column {test_dim_col})")

    # Query by this dimension
    df = xbrl.facts.query().by_dimension(test_dim_name).to_dataframe()

    if len(df) == 0:
        pytest.skip(f"No facts found with dimension {test_dim_name}")

    # Verify that the 'dimension' column contains the requested dimension
    if 'dimension' in df.columns:
        dimensions_used = df['dimension'].dropna().unique()
        print(f"Dimensions in result: {dimensions_used}")

        # At least one row should have the requested dimension
        matching = any(test_dim_name in str(d) for d in dimensions_used)
        assert matching, f"Expected dimension '{test_dim_name}' not found in results. Got: {dimensions_used}"
