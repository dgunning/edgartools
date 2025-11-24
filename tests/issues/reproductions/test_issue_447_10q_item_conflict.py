"""
Reproduction test for GitHub Issue #447: 10-Q item parsing conflict
https://github.com/dgunning/edgartools/issues/447

Issue: 10-Q filings have duplicate item numbers across PART I and PART II.
The parser incorrectly conflates these items or loses PART II items entirely.

Example structure:
- PART I, Item 1: Financial Statements
- PART II, Item 1: Legal Proceedings

Current behavior (BUG):
- tenQ['Item 1'] returns mixed content from both parts
- tenQ.items missing PART II items

Expected behavior (AFTER FIX):
- tenQ['PART I, Item 1'] returns only Financial Statements
- tenQ['PART II, Item 1'] returns only Legal Proceedings
- All items accessible
"""
import pytest
from edgar import Company


@pytest.mark.skip('This test will run once we cutover to the new HTML parser')
@pytest.mark.network
@pytest.mark.reproduction
def test_issue_447_aapl_10q_item_conflict():
    """
    Reproduce issue #447 with AAPL 10-Q filing.

    This test currently documents the BUG. After fix, it should PASS.
    """
    # Get AAPL's latest 10-Q
    company = Company("AAPL")
    tenq = company.latest_tenq

    assert tenq is not None, "Could not retrieve AAPL's latest 10-Q"

    # Get Item 1 content
    item_1_content = tenq['Item 1']

    if item_1_content:
        item_1_lower = item_1_content.lower()

        # Check if content is mixed (contains both financial statements AND legal proceedings)
        has_financial_keywords = any(kw in item_1_lower for kw in [
            'financial statements',
            'consolidated balance sheet',
            'consolidated statement',
            'unaudited'
        ])

        has_legal_keywords = any(kw in item_1_lower for kw in [
            'legal proceedings',
            'litigation',
            'lawsuits',
            'legal matters'
        ])

        # Document the bug: Item 1 contains BOTH financial and legal content
        if has_financial_keywords and has_legal_keywords:
            print("\n🐛 BUG CONFIRMED: Item 1 contains mixed PART I + PART II content")
            print(f"   - Contains financial keywords: {has_financial_keywords}")
            print(f"   - Contains legal keywords: {has_legal_keywords}")
            print(f"   - Content length: {len(item_1_content)} chars")

            # This is the bug - Item 1 should NOT contain both
            pytest.fail(
                "PART I Item 1 (Financial Statements) is mixed with "
                "PART II Item 1 (Legal Proceedings). Items should be part-qualified."
            )

    # Check if PART II items are accessible
    items_list = tenq.items
    print(f"\n📋 Items found: {items_list}")

    # Count how many items we have
    item_count = len(items_list) if items_list else 0
    print(f"   Total items: {item_count}")

    # 10-Q should have items from both PART I (4 items) and PART II (typically 5-6 items)
    # If we have fewer than 7 items, PART II items are likely missing
    if item_count < 7:
        print(f"\n🐛 BUG CONFIRMED: Only {item_count} items found (expected 9+)")
        print("   PART II items appear to be missing")
        pytest.fail(
            f"Only {item_count} items found in 10-Q. "
            "PART II items are likely missing or conflated."
        )


@pytest.mark.skip('This test will run once we cutover to the new HTML parser')
@pytest.mark.network
@pytest.mark.reproduction
def test_issue_447_structure_representation():
    """
    Test that get_structure() properly represents PART I and PART II hierarchy.

    This test documents what structure is returned (for debugging).
    """
    company = Company("AAPL")
    tenq = company.latest_tenq

    assert tenq is not None

    structure = tenq.get_structure()
    print(f"\n📊 10-Q Structure:")
    print(f"   {structure}")

    # Check if structure shows parts
    if structure:
        structure_str = str(structure)
        has_part_i = 'PART I' in structure_str or 'Part I' in structure_str
        has_part_ii = 'PART II' in structure_str or 'Part II' in structure_str

        print(f"   - Shows PART I: {has_part_i}")
        print(f"   - Shows PART II: {has_part_ii}")

        if not (has_part_i and has_part_ii):
            pytest.fail(
                "Structure does not properly represent PART I and PART II hierarchy"
            )


@pytest.mark.network
@pytest.mark.reproduction
@pytest.mark.parametrize("ticker", ["AAPL", "MSFT", "TSLA"])
def test_issue_447_multiple_companies(ticker):
    """
    Verify the bug exists across multiple companies' 10-Q filings.

    Tests AAPL, MSFT, and TSLA to ensure this is a systematic issue.
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

    # All 10-Q filings should have similar structure with 9+ items
    if item_count < 7:
        pytest.fail(
            f"{ticker} 10-Q has only {item_count} items. "
            "PART II items likely missing (bug confirmed)."
        )
