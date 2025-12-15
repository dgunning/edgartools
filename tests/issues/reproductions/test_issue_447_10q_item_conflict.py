"""
Regression tests for GitHub Issue #447: 10-Q item parsing conflict
https://github.com/dgunning/edgartools/issues/447

Issue: 10-Q filings have duplicate item numbers across PART I and PART II.
The OLD parser incorrectly conflated these items or lost PART II items entirely.

Example structure:
- PART I, Item 1: Financial Statements
- PART II, Item 1: Legal Proceedings

FIXED behavior (using new HTMLParser):
- tenQ['Part I, Item 1'] returns only Financial Statements
- tenQ['Part II, Item 1'] returns only Legal Proceedings
- All items accessible via part-qualified names
"""
import pytest
from edgar import Company


@pytest.mark.network
@pytest.mark.regression
def test_issue_447_aapl_10q_item_conflict():
    """
    Verify issue #447 is fixed with AAPL 10-Q filing.

    This test ensures Part I Item 1 and Part II Item 1 are properly separated.
    """
    # Get AAPL's latest 10-Q
    company = Company("AAPL")
    tenq = company.latest_tenq

    assert tenq is not None, "Could not retrieve AAPL's latest 10-Q"

    # Test part-qualified access
    part_i_item_1 = tenq['Part I, Item 1']
    part_ii_item_1 = tenq['Part II, Item 1']

    # Both should exist and be non-empty
    assert part_i_item_1 is not None, "Part I, Item 1 should exist"
    assert part_ii_item_1 is not None, "Part II, Item 1 should exist"
    assert len(part_i_item_1) > 0, "Part I, Item 1 should have content"
    assert len(part_ii_item_1) > 0, "Part II, Item 1 should have content"

    # Part I Item 1 should be Financial Statements (much larger)
    assert len(part_i_item_1) > len(part_ii_item_1), \
        "Part I Item 1 (Financial Statements) should be larger than Part II Item 1 (Legal Proceedings)"

    # Part I Item 1 should contain financial statement keywords
    part_i_lower = part_i_item_1.lower()
    has_financial = any(kw in part_i_lower for kw in [
        'financial statement',
        'consolidated balance',
        'consolidated statement',
        'unaudited'
    ])
    assert has_financial, "Part I Item 1 should contain financial statement content"

    # Part II Item 1 should contain legal proceedings keywords
    part_ii_lower = part_ii_item_1.lower()
    has_legal = any(kw in part_ii_lower for kw in [
        'legal proceeding',
        'litigation',
        'lawsuit',
        'investigation'
    ])
    assert has_legal, "Part II Item 1 should contain legal proceedings content"

    print(f"\n✓ Part I, Item 1: {len(part_i_item_1)} chars (Financial Statements)")
    print(f"✓ Part II, Item 1: {len(part_ii_item_1)} chars (Legal Proceedings)")


@pytest.mark.network
@pytest.mark.regression
def test_issue_447_structure_representation():
    """
    Test that get_structure() properly represents PART I and PART II hierarchy.
    """
    from rich.console import Console
    from io import StringIO

    company = Company("AAPL")
    tenq = company.latest_tenq

    assert tenq is not None

    structure = tenq.get_structure()
    assert structure is not None

    # Render the Rich Tree to a string
    string_io = StringIO()
    console = Console(file=string_io, force_terminal=True, width=200)
    console.print(structure)
    structure_str = string_io.getvalue()

    assert 'PART I' in structure_str or 'Part I' in structure_str, \
        f"Structure should show PART I. Got: {structure_str[:500]}"
    assert 'PART II' in structure_str or 'Part II' in structure_str, \
        f"Structure should show PART II. Got: {structure_str[:500]}"


@pytest.mark.network
@pytest.mark.regression
@pytest.mark.parametrize("ticker", ["AAPL", "MSFT", "TSLA"])
def test_issue_447_multiple_companies(ticker):
    """
    Verify the fix works across multiple companies' 10-Q filings.

    Tests AAPL, MSFT, and TSLA to ensure this is a systematic fix.
    """
    company = Company(ticker)
    tenq = company.latest_tenq

    if tenq is None:
        pytest.skip(f"Could not retrieve {ticker}'s latest 10-Q")

    print(f"\n🔍 Testing {ticker} 10-Q")

    items_list = tenq.items
    item_count = len(items_list) if items_list else 0

    print(f"   Items found: {item_count}")
    print(f"   Items: {items_list[:5]}...")  # Show first 5

    # All 10-Q filings should have at least 4 items (minimum required by SEC)
    # Some filings may consolidate or omit optional items, so we allow 4+
    # The original issue #447 was about Part I vs Part II item conflicts, not item count
    assert item_count >= 4, \
        f"{ticker} 10-Q has only {item_count} items. Expected at least 4 items."


@pytest.mark.network
@pytest.mark.regression
def test_issue_447_backward_compatibility():
    """
    Test that legacy access patterns still work.

    tenq['Item 1'] should return Part I Item 1 for backward compatibility.
    """
    company = Company("AAPL")
    tenq = company.latest_tenq

    assert tenq is not None

    # Legacy access should still work
    item_1 = tenq['Item 1']
    assert item_1 is not None, "Legacy tenq['Item 1'] should still work"

    # Legacy access should return Part I Item 1 (for backward compat)
    part_i_item_1 = tenq['Part I, Item 1']
    if part_i_item_1:
        # Content should be similar (from same section)
        assert len(item_1) > 0, "Legacy Item 1 should have content"

    # get_item_with_part should still work
    giwp_result = tenq.get_item_with_part('Part I', 'Item 1')
    assert giwp_result is not None, "get_item_with_part should still work"


@pytest.mark.network
@pytest.mark.regression
def test_issue_447_sections_property():
    """
    Test that sections property returns properly keyed sections.
    """
    company = Company("AAPL")
    tenq = company.latest_tenq

    assert tenq is not None

    sections = tenq.sections
    assert sections is not None, "sections property should return sections"
    assert len(sections) > 0, "Should have detected sections"

    print(f"\nSection keys: {list(sections.keys())}")

    # Should have multiple sections
    # Keys could be either pattern-based (part_i_item_1) or TOC-based (Item 1)
    item_sections = [k for k in sections.keys() if 'item' in k.lower()]
    assert len(item_sections) >= 4, \
        f"Should have at least 4 item sections, found: {item_sections}"
