"""
Reproduction test for Issue #251: 10K Returning None for Citigroup

GitHub Issue: https://github.com/dgunning/edgartools/issues/251
Reporter: GitHub user

Bug: TenK item extraction returns None for Citigroup filings.
Specifically, tenk['Item 1'] and tenk.business return None even though
the content exists in the SEC filing.

Test Case: CIK 831001 (CITIGROUP INC)

Expected: Item 1 (Business) and other items should extract content
Actual: Returns None

This test documents the bug for tracking purposes. It will be resolved
when TenK is migrated to the new HTMLParser.
"""

import pytest
from edgar import Company


@pytest.mark.network
@pytest.mark.reproduction
def test_issue_251_citigroup_item_extraction_fails():
    """
    Reproduce the bug where Citigroup 10-K items return None.

    This test is expected to fail until the TenK migration to new parser is complete.
    """
    company = Company("831001")  # CITIGROUP INC
    filing = company.get_filings(form="10-K").latest(1)

    assert filing is not None, "Should find latest 10-K filing"
    assert filing.company == "CITIGROUP INC"

    tenk = filing.obj()
    assert tenk is not None, "Should create TenK object"

    # These currently fail - documenting the bug
    item1 = tenk['Item 1']
    assert item1 is not None, "Item 1 (Business) should not be None"
    assert len(item1) > 100, f"Item 1 should have substantial content, got {len(item1) if item1 else 0} chars"

    # Test property access
    business = tenk.business
    assert business is not None, "business property should not be None"
    assert len(business) > 100, f"Business should have substantial content, got {len(business) if business else 0} chars"


@pytest.mark.network
@pytest.mark.reproduction
def test_issue_251_citigroup_multiple_items():
    """
    Test that multiple items fail for Citigroup (not just Item 1).
    """
    company = Company("831001")
    filing = company.get_filings(form="10-K").latest(1)
    tenk = filing.obj()

    # Test multiple items
    items_to_test = [
        ('Item 1', 'Business'),
        ('Item 1A', 'Risk Factors'),
        ('Item 7', "Management's Discussion"),
    ]

    for item_number, description in items_to_test:
        item = tenk[item_number]
        assert item is not None, f"{item_number} ({description}) should not be None"
        assert len(item) > 100, f"{item_number} should have substantial content"


@pytest.mark.network
@pytest.mark.reproduction
def test_issue_251_verify_filing_content_exists():
    """
    Verify that the filing HTML actually contains the content we're trying to extract.

    This confirms the bug is in extraction, not missing source data.
    """
    company = Company("831001")
    filing = company.get_filings(form="10-K").latest(1)

    # Get raw HTML
    html = filing.html()
    assert html is not None
    assert len(html) > 1000, "Filing HTML should have content"

    # Verify content exists in HTML
    assert "ITEM 1" in html.upper() or "Item 1" in html, "Item 1 heading should exist in HTML"
    assert "BUSINESS" in html.upper() or "Business" in html, "Business content should exist in HTML"

    # But extraction fails
    tenk = filing.obj()
    item1 = tenk['Item 1']

    # This is the bug: content exists in HTML but extraction returns None
    assert item1 is None, "Currently returns None - this is the bug we're documenting"
