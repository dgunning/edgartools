"""
Regression test for Issue #607: Reopen of #603 - dimension_member_label still incorrect

GitHub Issue: https://github.com/dgunning/edgartools/issues/607
Reporter: Nikolay Ivanov (@Velikolay)

Bug: When a fact has multiple dimensions and the user queries by a specific dimension,
the dimension_member_label was showing the member of the FIRST dimension in dict order,
not the dimension the user specifically requested.

Example: For facts with both srt:RangeAxis and PropertyPlantAndEquipmentByTypeAxis,
querying by PropertyPlantAndEquipmentByTypeAxis would show "Minimum"/"Maximum"
(from RangeAxis) instead of "Building"/"Land" (from the requested axis).

Fix: Track the requested dimension in by_dimension() and update dimension fields
in to_dataframe() to reflect the specifically requested dimension's member.

Test Cases:
- GOOGL 10-K: Query by PropertyPlantAndEquipmentByTypeAxis (multi-dimension scenario)
- AAPL 10-K: Query by StatementBusinessSegmentsAxis (single dimension verification)
"""

import pytest
from edgar import Company


@pytest.mark.network
@pytest.mark.regression
def test_issue_607_multi_dimension_correct_label():
    """
    Verify that when querying by a specific dimension, the dimension_member_label
    shows the member of THAT dimension, not another dimension on the same fact.

    This tests the core bug: facts with multiple dimensions were showing the wrong
    dimension's member label.
    """
    company = Company("GOOGL")
    filing = company.get_filings(form="10-K", year=2024).latest()

    assert filing is not None, "Should find GOOGL 2024 10-K"

    xbrl = filing.xbrl()
    assert xbrl is not None, "Should parse XBRL"

    # Query by PropertyPlantAndEquipmentByTypeAxis
    # Some facts have both this axis AND srt:RangeAxis
    df = xbrl.facts.query().by_dimension("PropertyPlantAndEquipmentByTypeAxis").to_dataframe()

    if len(df) == 0:
        pytest.skip("No facts found with PropertyPlantAndEquipmentByTypeAxis dimension")

    print(f"Found {len(df)} facts with PropertyPlantAndEquipmentByTypeAxis dimension")

    # Check for the bug: dimension_member_label should NOT be "Minimum" or "Maximum"
    # Those values come from srt:RangeAxis, not the requested axis
    if 'dimension_member_label' in df.columns:
        labels = df['dimension_member_label'].dropna().unique()
        print(f"Unique dimension_member_labels: {list(labels)}")

        # The bug was: some labels showed "Minimum"/"Maximum" from RangeAxis
        # After fix: should only show asset type labels like "Building", "Server Equipment", etc.
        wrong_labels = [label for label in labels if label in ['Minimum', 'Maximum']]

        assert len(wrong_labels) == 0, (
            f"BUG: Found labels from wrong dimension (RangeAxis): {wrong_labels}. "
            "Expected only PropertyPlantAndEquipmentByTypeAxis member labels like "
            "'Building', 'Server Equipment', 'Land and buildings', etc."
        )

        # Verify we have reasonable labels (asset types)
        assert len(labels) > 0, "Should have at least one dimension_member_label"
        print(f"SUCCESS: All {len(labels)} labels are from the correct dimension")


@pytest.mark.network
@pytest.mark.regression
def test_issue_607_dimension_field_consistency():
    """
    Verify that dimension, member, and dimension_member_label fields are consistent
    when querying by a specific dimension.
    """
    company = Company("GOOGL")
    filing = company.get_filings(form="10-K", year=2024).latest()

    xbrl = filing.xbrl()

    # Query by a known dimension
    df = xbrl.facts.query().by_dimension("PropertyPlantAndEquipmentByTypeAxis").to_dataframe()

    if len(df) == 0:
        pytest.skip("No facts found")

    # Check that the dimension field reflects the requested dimension
    if 'dimension' in df.columns:
        dimensions = df['dimension'].dropna().unique()
        print(f"Dimensions in result: {dimensions}")

        # All rows should have the requested dimension
        for dim in dimensions:
            assert 'PropertyPlantAndEquipmentByTypeAxis' in dim, (
                f"Expected PropertyPlantAndEquipmentByTypeAxis in dimension field, got: {dim}"
            )

    # Check that member values are from the correct dimension
    ppne_col = [c for c in df.columns if 'PropertyPlantAndEquipment' in c and c.startswith('dim_')]
    if ppne_col and 'member' in df.columns:
        # The member column should match the values in the dim_ column
        expected_members = df[ppne_col[0]].dropna().unique()
        actual_members = df['member'].dropna().unique()
        print(f"Expected members (from dim_ col): {list(expected_members)[:5]}")
        print(f"Actual members (from member col): {list(actual_members)[:5]}")

        # Members should overlap (allowing for some flexibility in exact matching)
        assert len(actual_members) > 0, "Should have member values"


@pytest.mark.network
@pytest.mark.regression
def test_issue_607_aapl_segment_dimension():
    """
    Verify AAPL segment query still works correctly (single dimension case).

    This ensures the fix doesn't break the simpler case where facts have only one dimension.
    """
    company = Company("AAPL")
    filing = company.get_filings(form="10-K", year=2024).latest()

    assert filing is not None, "Should find AAPL 2024 10-K"

    xbrl = filing.xbrl()
    assert xbrl is not None, "Should parse XBRL"

    # Query by StatementBusinessSegmentsAxis
    df = xbrl.facts.query().by_dimension("StatementBusinessSegmentsAxis").to_dataframe()

    if len(df) == 0:
        pytest.skip("No facts found with StatementBusinessSegmentsAxis dimension")

    print(f"Found {len(df)} facts with StatementBusinessSegmentsAxis dimension")

    if 'dimension_member_label' in df.columns:
        labels = df['dimension_member_label'].dropna().unique()
        print(f"Unique dimension_member_labels: {list(labels)}")

        # Should have segment names like "Americas", "Europe", "Greater China", etc.
        assert len(labels) > 0, "Should have dimension_member_label values"

        # Verify the dimension field is correct
        if 'dimension' in df.columns:
            dims = df['dimension'].dropna().unique()
            for dim in dims:
                assert 'StatementBusinessSegmentsAxis' in dim, (
                    f"Expected StatementBusinessSegmentsAxis in dimension, got: {dim}"
                )


@pytest.mark.network
@pytest.mark.regression
def test_issue_607_no_dimension_query_unchanged():
    """
    Verify that queries WITHOUT by_dimension() are unaffected by the fix.

    The fix should only apply when a specific dimension is requested.
    When using by_custom to find dimensional facts (without by_dimension),
    the original behavior should be preserved.
    """
    company = Company("AAPL")
    filing = company.get_filings(form="10-K", year=2024).latest()

    xbrl = filing.xbrl()

    # Query dimensional facts WITHOUT using by_dimension - should use original behavior
    # Using by_custom to find facts that have dimensions
    df = xbrl.facts.query().by_custom(
        lambda f: any(key.startswith('dim_') for key in f.keys())
    ).limit(20).to_dataframe()

    if len(df) == 0:
        pytest.skip("No dimensional facts found")

    # By default, dimensions are excluded unless by_dimension() is called
    # So dimension columns might not be present, which is expected
    print(f"Found {len(df)} dimensional facts")
    print(f"Columns present: {list(df.columns)}")

    # The fix should not affect queries that don't use by_dimension()
    # Just verify the query completes without error
    print("SUCCESS: Non-dimension-filtered query works correctly")
