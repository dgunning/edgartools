"""
Regression tests for Issue #503: Balance sheet statement selection returning fragments

Issue: https://github.com/dgunning/edgartools/issues/503

Problem: Statement resolver was selecting fragment/detail statements instead of complete
financial statements, particularly for pre-2020 filings. Role pattern matching was too
broad, matching both "ConsolidatedBalanceSheets" and "BenefitPlansAmountsRecognizedInBalanceSheetDetails".

Examples:
- WST 2015: Selected pension benefits fragment (16 rows) instead of complete balance sheet
- BSX 2015-2019: Selected equity detail fragment instead of full balance sheet

Fix: Add statement quality scoring to prefer complete statements over fragments. Fragment
indicators: "details", "tables", "schedule", "disclosure", etc. Prioritize "Consolidated"
and exact matches for primary statement names.
"""

import pytest
from edgar import Company


@pytest.mark.network
@pytest.mark.regression
def test_wst_2015_selects_complete_balance_sheet():
    """
    Test that WST 2015 selects complete balance sheet, not pension benefits fragment.

    Before fix: 16 rows, only "Compensation and Retirement Disclosure" items
    After fix: 70+ rows, complete balance sheet with Assets, Liabilities, Equity
    """
    wst = Company("WST")
    filings = wst.get_filings(form="10-K")

    # Find 2015 filing
    filing_2015 = None
    for filing in filings:
        if filing.filing_date.year == 2015:
            filing_2015 = filing
            break

    assert filing_2015 is not None, "Could not find WST 2015 10-K filing"

    xbrl = filing_2015.xbrl()
    balance_sheet = xbrl.statements.balance_sheet()

    assert balance_sheet is not None, "Could not load WST balance sheet"

    # Convert to dataframe
    df = balance_sheet.to_dataframe()

    # Verify we have a complete balance sheet, not a fragment
    assert len(df) > 50, f"Expected >50 rows for complete balance sheet, got {len(df)}"

    # Check for essential balance sheet concepts
    labels = df['label'].str.lower().tolist()
    essential_concepts = ['assets', 'liabilities', 'equity', 'cash', 'inventory']

    found_concepts = []
    for concept in essential_concepts:
        if any(concept in label for label in labels):
            found_concepts.append(concept)

    assert len(found_concepts) >= 4, (
        f"Expected at least 4 essential balance sheet concepts, found {len(found_concepts)}: {found_concepts}. "
        "This suggests a fragment was selected instead of the complete balance sheet."
    )


@pytest.mark.network
@pytest.mark.regression
def test_balance_sheet_not_pension_fragment():
    """
    General test to ensure balance sheets are not pension benefit fragments.

    Checks that the first concept is not pension/retirement related,
    which would indicate a fragment was selected.
    """
    wst = Company("WST")
    filing = wst.get_filings(form="10-K").latest(1)

    xbrl = filing.xbrl()
    balance_sheet = xbrl.statements.balance_sheet()

    assert balance_sheet is not None

    df = balance_sheet.to_dataframe()

    # First non-abstract row should not be pension-related
    non_abstract_rows = df[df['abstract'] == False]
    assert len(non_abstract_rows) > 0, "No non-abstract rows found"

    first_concept = non_abstract_rows.iloc[0]['concept']
    first_label = non_abstract_rows.iloc[0]['label']

    # Fragment indicators that should NOT appear in first concept
    fragment_indicators = ['pension', 'retirement', 'postretirement', 'benefit']

    is_fragment = any(
        indicator in first_concept.lower() or indicator in first_label.lower()
        for indicator in fragment_indicators
    )

    assert not is_fragment, (
        f"First concept appears to be from a fragment: {first_label} ({first_concept}). "
        "Expected a complete balance sheet starting with Assets or similar."
    )
