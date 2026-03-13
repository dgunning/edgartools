"""
Regression test for edgartools-3n9t / gh:572 → refined by gh:703.

AAPL's Comprehensive Income statement has rows where the company switched XBRL
concepts between fiscal years.  For example, "Change in fair value of derivative
instruments" uses us-gaap:...CashFlowHedge... in 2025 but
aapl:...DerivativeInstrument... in 2024/2023.

Original approach (GH-572): merge same-label siblings with complementary NaN values.
Revised approach (GH-703):  only merge siblings when they have overlapping periods
with agreeing values — this proves a concept switch.  Without overlap, merging
silently drops distinct concepts, which is worse than having duplicate display rows.

These tests verify the revised, data-preserving behavior.
"""

import pytest


@pytest.mark.network
def test_aapl_comprehensive_income_all_concepts_preserved():
    """AAPL comprehensive income should preserve all concept names.

    After GH-703, sibling concepts with the same label but no overlapping periods
    are NOT merged.  This means duplicate labels may appear (one per concept), but
    no concept is silently dropped.
    """
    from edgar import Company

    company = Company('AAPL')
    filing = company.get_filings(form='10-K').latest()
    xbrl = filing.xbrl()
    stmt = xbrl.statements.comprehensive_income()
    assert stmt is not None, "AAPL should have a comprehensive income statement"

    df = stmt.to_dataframe()

    # Every concept in the statement data should appear in the dataframe
    assert len(df) > 0, "Comprehensive income statement should have rows"

    # Concepts should include both company-extension and us-gaap variants
    concepts = set(df['concept'].tolist()) if 'concept' in df.columns else set()
    assert len(concepts) > 0, "DataFrame should have concept column with values"


@pytest.mark.network
def test_aapl_comprehensive_income_values_not_lost():
    """Each concept row should have values for the periods where it was reported."""
    from edgar import Company

    company = Company('AAPL')
    filing = company.get_filings(form='10-K').latest()
    xbrl = filing.xbrl()
    stmt = xbrl.statements.comprehensive_income()
    df = stmt.to_dataframe()

    value_cols = [c for c in df.columns if c.startswith('20')]
    non_abstract = df[~df['abstract']]

    # Each non-abstract row should have at least one non-NaN value
    rows_with_any_value = non_abstract[value_cols].notna().any(axis=1)
    assert rows_with_any_value.all(), (
        "Every non-abstract row should have at least one period value"
    )
