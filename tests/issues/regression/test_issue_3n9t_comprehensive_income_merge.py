"""
Regression test for edgartools-3n9t / gh:572: Merge same-label rows with complementary NaN values.

AAPL's Comprehensive Income statement has duplicate rows where the company switched
XBRL concepts between fiscal years. For example, "Change in fair value of derivative
instruments" uses us-gaap:...CashFlowHedge... in 2025 but aapl:...DerivativeInstrument...
in 2024/2023. This produces two rows with the same label but complementary NaN values
instead of one merged row.

Fix: _merge_sibling_concept_switches merges these during tree traversal, scoped to
direct siblings under the same parent node.  This uses XBRL structure (same parent,
same label, leaf concepts) rather than global label matching.
"""

import pytest


@pytest.mark.network
def test_aapl_comprehensive_income_no_unexpected_duplicate_labels():
    """AAPL comprehensive income should merge concept-switch duplicates while preserving
    legitimate same-label items that have different values.

    After merging, the only remaining "duplicate" label should be the
    "Adjustment for net (gains)/losses realized and included in net income" row
    which appears for both derivatives and securities — these are genuinely
    different line items with different values that correctly refuse to merge.
    """
    from edgar import Company

    company = Company('AAPL')
    filing = company.get_filings(form='10-K').latest()
    xbrl = filing.xbrl()
    stmt = xbrl.statements.comprehensive_income()
    assert stmt is not None, "AAPL should have a comprehensive income statement"

    df = stmt.to_dataframe()
    non_abstract = df[~df['abstract']]

    # Check for duplicate labels among non-abstract rows
    label_counts = non_abstract['label'].value_counts()
    duplicates = label_counts[label_counts > 1]

    # The only legitimate duplicate is the Adjustment row (derivatives vs securities)
    expected_duplicates = {'Adjustment for net (gains)/losses realized and included in net income'}
    actual_duplicates = set(duplicates.index)
    unexpected = actual_duplicates - expected_duplicates

    assert not unexpected, (
        f"Found unexpected duplicate labels in non-abstract rows: "
        f"{{k: duplicates[k] for k in unexpected}}"
    )


@pytest.mark.network
def test_aapl_comprehensive_income_merged_rows_have_all_periods():
    """After merging, rows that had complementary NaN values should have all period values."""
    from edgar import Company

    company = Company('AAPL')
    filing = company.get_filings(form='10-K').latest()
    xbrl = filing.xbrl()
    stmt = xbrl.statements.comprehensive_income()
    df = stmt.to_dataframe()

    value_cols = [c for c in df.columns if c.startswith('20')]
    non_abstract = df[~df['abstract']]

    # After merge, non-abstract value cells should have minimal NaN
    nan_count = non_abstract[value_cols].isna().sum().sum()
    assert nan_count == 0, (
        f"Found {nan_count} NaN values in non-abstract rows — merge may have failed"
    )
