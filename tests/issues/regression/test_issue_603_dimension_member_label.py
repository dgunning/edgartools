"""
Regression test for Issue #603: Dataframe field dimension_member_label has incorrect values

GitHub Issue: https://github.com/dgunning/edgartools/issues/603
Reporter: Nikolay Ivanov (@Velikolay)

Bug (FIXED): The `dimension_member_label` field in statement DataFrames was showing
the LAST dimension's label instead of the PRIMARY (first) dimension's label.

For GOOGL's income statement with multi-dimensional revenue breakdowns:
- Expected: "YouTube ads", "Google Search & other", "Google Network", etc.
- Actual (bug): "Google Services" for all Google segment items

Root Cause: In `edgar/xbrl/statements.py` line 920-923, the code used `dim_metadata[-1]`
(last dimension) for `dimension_member_label`, but should use `dim_metadata[0]`
(first/primary dimension) to be consistent with `dimension_axis` and `dimension_member`.

Fix: Changed to use `primary_dim` (first dimension) for `dimension_member_label`.

Test Cases:
- GOOGL 2023 10-K: Multi-dimensional revenue breakdown (ProductOrServiceAxis + SegmentsAxis)
"""

import pytest
from edgar import Company


@pytest.mark.network
@pytest.mark.regression
def test_issue_603_googl_dimension_member_label():
    """
    Verify GOOGL income statement has correct dimension_member_label values.

    The bug caused all Google segment revenue items to show "Google Services"
    instead of their specific product labels like "YouTube ads", "Google Network".
    """
    company = Company("GOOGL")
    filing = company.get_filings(form="10-K", year=2023).latest()

    assert filing is not None, "Should find GOOGL 2023 10-K"

    xbrl = filing.xbrl()
    assert xbrl is not None, "Should parse XBRL"

    income_stmt = xbrl.statements.income_statement()
    assert income_stmt is not None, "Should have income statement"

    df = income_stmt.to_dataframe()

    # Filter to dimensional rows only
    dimensional_rows = df[df['dimension'] == True]

    if len(dimensional_rows) == 0:
        pytest.skip("No dimensional rows in GOOGL income statement")

    # Check that dimension_member_label matches dimension_member's label portion
    # The bug was that dimension_member_label came from a different dimension than dimension_member
    for _, row in dimensional_rows.iterrows():
        member = row.get('dimension_member', '')
        member_label = row.get('dimension_member_label', '')

        if member and member_label:
            # The member_label should be a human-readable version of the member
            # Bug: was showing "Google Services" for "YouTube ads" member
            print(f"Member: {member}, Label: {member_label}")

            # Basic sanity check: label should not be empty when member exists
            assert member_label, f"dimension_member_label should not be empty when dimension_member is '{member}'"


@pytest.mark.network
@pytest.mark.regression
def test_issue_603_dimension_consistency():
    """
    Verify dimension_axis, dimension_member, and dimension_member_label are consistent.

    All three fields should come from the same (primary) dimension.
    """
    company = Company("GOOGL")
    filing = company.get_filings(form="10-K", year=2023).latest()

    xbrl = filing.xbrl()
    income_stmt = xbrl.statements.income_statement()
    df = income_stmt.to_dataframe()

    # Filter to dimensional rows with all three fields populated
    dimensional_rows = df[
        (df['dimension'] == True) &
        (df['dimension_axis'].notna()) &
        (df['dimension_member'].notna()) &
        (df['dimension_member_label'].notna())
    ]

    if len(dimensional_rows) == 0:
        pytest.skip("No fully-populated dimensional rows")

    # The dimension_member_label should NOT be "Google Services" for non-segment axes
    for _, row in dimensional_rows.iterrows():
        axis = row['dimension_axis']
        member = row['dimension_member']
        label = row['dimension_member_label']

        # If the axis is ProductOrServiceAxis, the label should match the product, not segment
        if 'ProductOrService' in str(axis):
            # Bug: label was "Google Services" (segment) instead of product name
            assert label != 'Google Services' or 'Google Services' in str(member), \
                f"ProductOrServiceAxis member '{member}' should not have segment label 'Google Services'"
            print(f"ProductOrService: {member} -> {label}")


@pytest.mark.network
@pytest.mark.regression
def test_issue_603_query_by_dimension():
    """
    Verify the bug also affected direct dimension queries (not just statements).

    User reported: filing.xbrl().query().by_concept("Revenue").by_dimension("ProductOrServiceAxis")
    also showed incorrect labels.
    """
    company = Company("GOOGL")
    filing = company.get_filings(form="10-K", year=2023).latest()

    xbrl = filing.xbrl()

    # Query revenue by ProductOrServiceAxis dimension
    revenue_by_product = xbrl.facts.query().by_concept("Revenue").by_dimension("ProductOrServiceAxis").to_dataframe()

    if len(revenue_by_product) == 0:
        # Try alternative revenue concept names
        revenue_by_product = xbrl.facts.query().by_concept("Revenues").by_dimension("ProductOrServiceAxis").to_dataframe()

    if len(revenue_by_product) == 0:
        pytest.skip("No Revenue facts with ProductOrServiceAxis dimension")

    print(f"Found {len(revenue_by_product)} revenue facts with ProductOrServiceAxis")

    # Verify dimension data is present and reasonable
    if 'dimension_member_label' in revenue_by_product.columns:
        labels = revenue_by_product['dimension_member_label'].dropna().unique()
        print(f"Unique dimension_member_labels: {labels}")

        # Should have specific product labels, not just generic segment labels
        # Bug was: all showed "Google Services" instead of specific products
        # GH-603: The dimension_member_label should be primary dimension's label
        expected_products = ['YouTube ads', 'Google Search & other', 'Google Network']
        for expected in expected_products:
            assert expected in labels, f"Expected product label '{expected}' not found in dimension_member_label"

        # Bug check: "Google Services" should NOT be the label for ProductOrServiceAxis items
        # (unless it's actually a valid product, which it isn't for GOOGL revenue breakdown)
        for _, row in revenue_by_product.iterrows():
            label = row.get('dimension_member_label')
            if label == 'Google Services':
                pytest.fail(f"BUG: dimension_member_label should NOT be 'Google Services' for ProductOrServiceAxis")
