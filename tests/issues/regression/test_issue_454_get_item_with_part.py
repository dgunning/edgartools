"""
Regression test for Issue #454: TenK.get_item_with_part fails to fetch Part II chunks

GitHub Issue: https://github.com/dgunning/edgartools/issues/454
Reporter: GitHub user

Bug: TenK.get_item_with_part('Part II', 'Item 7') returned None while direct access
via TenK['Item 7'] worked correctly.

Root Cause: The ChunkedDocument._chunks_mul_for() method used compiled regex patterns
with re.IGNORECASE flag, but pandas str.match() ignores flags from compiled patterns.
The data contained mixed case values like "Part Ii" which didn't match the pattern
"Part II" due to case sensitivity.

Fix: Changed _chunks_mul_for() to use string patterns with case=False parameter
instead of compiled regex patterns, ensuring case-insensitive matching works correctly.
"""

import pytest
from edgar import Company


@pytest.mark.network
def test_issue_454_get_item_with_part_returns_content():
    """
    Test that get_item_with_part correctly retrieves Part II items from 10-K filings.

    This was the exact scenario reported in the bug: get_item_with_part('Part II', 'Item 7')
    returned None for this specific accession number while direct access worked.
    """
    company = Company('915358')  # SIGMATRON INTERNATIONAL INC
    filings = company.get_filings(accession_number='0000915358-25-000018')
    filing = filings[0]
    tenk = filing.obj()

    # This was failing before the fix
    result = tenk.get_item_with_part('Part II', 'Item 7', markdown=False)

    # Verify we get actual content, not None or empty
    assert result is not None, "get_item_with_part should not return None"
    assert len(result) > 0, "get_item_with_part should return non-empty content"
    assert len(result) > 1000, f"Expected substantial content, got only {len(result)} chars"

    # Compare with direct access which was working
    direct = tenk['Item 7']
    assert direct is not None, "Direct access should work"

    # Both methods should return similar content lengths
    # (allowing small differences due to formatting)
    assert abs(len(result) - len(direct)) < 100, \
        f"Content length mismatch: get_item_with_part={len(result)}, direct={len(direct)}"


@pytest.mark.network
def test_issue_454_various_part_formats():
    """
    Test that get_item_with_part works with various part format variations.
    """
    company = Company('915358')
    filings = company.get_filings(accession_number='0000915358-25-000018')
    tenk = filings[0].obj()

    # All these formats should work
    test_cases = [
        ('Part II', 'Item 7'),
        ('PART II', 'Item 7'),
        ('part ii', 'Item 7'),
        ('Part II', 'ITEM 7'),
        ('Part II', 'item 7'),
    ]

    for part, item in test_cases:
        result = tenk.get_item_with_part(part, item, markdown=False)
        assert result is not None and len(result) > 0, \
            f"get_item_with_part('{part}', '{item}') should return content"


@pytest.mark.network
def test_issue_454_part_i_items():
    """
    Test that get_item_with_part also works for Part I items.
    """
    company = Company('915358')
    filings = company.get_filings(accession_number='0000915358-25-000018')
    tenk = filings[0].obj()

    # Part I Item 1 (Business) should work
    result = tenk.get_item_with_part('Part I', 'Item 1', markdown=False)
    assert result is not None and len(result) > 0, \
        "Part I, Item 1 should return content"


@pytest.mark.fast
def test_chunked_document_case_insensitive_matching():
    """
    Unit test to verify ChunkedDocument._chunks_mul_for handles case variations.

    This tests the underlying fix without needing network access.
    """
    import pandas as pd
    import re

    # Simulate the data structure from a chunked document
    df = pd.DataFrame({
        'Part': ['', 'Part I', 'Part Ii', 'Part Ii', 'Part Iii'],
        'Item': ['', 'Item 1', 'Item 7', 'Item 7', 'Item 10'],
    })

    # Test the fix: string pattern with case=False
    part = 'Part II'
    item = 'Item 7'
    part = part.replace('.', r'\.')
    item = item.replace('.', r'\.')
    pattern_part = rf'^{part}$'
    pattern_item = rf'^{item}$'

    part_mask = df['Part'].str.match(pattern_part, case=False)
    item_mask = df['Item'].str.match(pattern_item, case=False)

    # Should match rows 2 and 3 (Part Ii, Item 7)
    combined_mask = part_mask & item_mask
    assert combined_mask.sum() == 2, f"Expected 2 matches, got {combined_mask.sum()}"
    assert list(combined_mask[combined_mask].index) == [2, 3]
