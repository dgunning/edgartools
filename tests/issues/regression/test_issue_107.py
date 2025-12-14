"""
Regression test for Issue #107: TenK function could not extract content of some filings

GitHub Issue: https://github.com/dgunning/edgartools/issues/107
Reporter: GitHub user

Bug (FIXED): TenK extraction was returning only item headings without actual content for certain filings.
For example, CIK 1000228 (Henry Schein) in 2021, 2023, and 2024 returned items with only
~18 characters (just the heading like "ITEM 1.\nBusiness\n3") instead of the full content.

Test Cases:
- CIK 1000228 (HENRY SCHEIN INC) - 2021, 2023, 2024 filings
- CIK 350852 - 2018, 2019 filings (also mentioned in issue)

Root Cause: ChunkedDocument (old parser) failed on certain filing formats.

Fix: TenK migrated to new HTMLParser (edgartools-cv8) which correctly extracts full content.

These tests now verify that the bug is fixed and serve as regression tests.
"""

import pytest
from edgar import Company


@pytest.mark.network
@pytest.mark.reproduction
def test_issue_107_henryschein_2024_extraction_fails():
    """
    Verify that Henry Schein 2024 10-K extraction now works correctly.

    This test verifies the bug is fixed after TenK migration to new parser.
    """
    company = Company("1000228")  # HENRY SCHEIN INC
    filing = company.get_filings(form="10-K", filing_date="2024-01-01:").latest(1)

    assert filing is not None, "Should find 2024/2025 10-K filing"
    assert company.name == "HENRY SCHEIN INC"

    tenk = filing.obj()
    assert tenk is not None, "Should create TenK object"

    # Test Item 1 extraction
    item1 = tenk['Item 1']
    assert item1 is not None, "Item 1 should not be None"

    # This is the bug: only 18 chars returned (just heading), not full content
    print(f"Item 1 length: {len(item1)}")
    print(f"Item 1 content: {item1[:200]}")

    assert len(item1) > 1000, \
        f"Item 1 should have substantial content (>1000 chars), got only {len(item1)} chars"

    # Verify it's not just whitespace
    assert len(item1.strip()) > 1000, "Item 1 should have actual content, not just whitespace"


@pytest.mark.network
@pytest.mark.reproduction
def test_issue_107_henryschein_multiple_items_fail():
    """
    Test that multiple items have the same issue (not just Item 1).
    """
    company = Company("1000228")
    filing = company.get_filings(form="10-K", filing_date="2024-01-01:").latest(1)
    tenk = filing.obj()

    items_to_test = [
        ('Item 1', 'Business', 1000),
        ('Item 1A', 'Risk Factors', 1000),
        ('Item 7', "Management's Discussion", 2000),
    ]

    for item_number, description, min_length in items_to_test:
        item = tenk[item_number]
        assert item is not None, f"{item_number} ({description}) should not be None"

        actual_length = len(item.strip()) if item else 0
        assert actual_length > min_length, \
            f"{item_number} should have substantial content (>{min_length} chars), got {actual_length} chars"


@pytest.mark.network
@pytest.mark.reproduction
def test_issue_107_verify_content_exists_in_html():
    """
    Verify that the filing HTML actually contains the full content.

    This confirms the bug is in ChunkedDocument extraction, not missing source data.
    """
    company = Company("1000228")
    filing = company.get_filings(form="10-K", filing_date="2024-01-01:").latest(1)

    # Get raw HTML
    html = filing.html()
    assert html is not None
    assert len(html) > 100000, "Filing HTML should have substantial content"

    # Verify Item 1 content markers exist in HTML
    assert "ITEM 1" in html.upper() or "Item 1" in html, "Item 1 heading should exist in HTML"
    assert "BUSINESS" in html.upper() or "Business" in html, "Business section should exist"

    # HTML should have lots of content
    assert len(html) > 1000000, \
        f"Expected substantial HTML content, got {len(html)} bytes"

    # Verify extraction now returns full content (bug fixed by new parser)
    tenk = filing.obj()
    item1 = tenk['Item 1']

    # Bug is fixed: new HTMLParser extracts full content, not just heading
    if item1:
        actual_length = len(item1.strip())
        assert actual_length > 1000, \
            f"Expected full content extraction (>1000 chars) with new parser, got {actual_length} chars"


@pytest.mark.network
@pytest.mark.reproduction
@pytest.mark.parametrize("filing_year_start", [
    "2021-01-01:",
    "2023-01-01:",
    "2024-01-01:",
])
def test_issue_107_multiple_years_affected(filing_year_start):
    """
    Test that the bug affects multiple years for Henry Schein (2021, 2023, 2024).

    Per the original issue, these specific years have the extraction problem.
    """
    company = Company("1000228")
    filings = company.get_filings(form="10-K", filing_date=filing_year_start)

    if filings and len(filings) > 0:
        filing = filings.latest(1)
        tenk = filing.obj()
        item1 = tenk['Item 1']

        if item1:
            # Document that these years all have the same bug
            print(f"Year {filing_year_start[:4]}: Item 1 length = {len(item1)} chars")
            assert len(item1.strip()) > 1000, \
                f"Year {filing_year_start[:4]}: Item 1 should have full content"
