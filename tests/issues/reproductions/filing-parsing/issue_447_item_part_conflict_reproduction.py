"""
Issue #447 Reproduction: Item parsing issue in filing obj (conflict of items having same index from different parts)

Problem:
In 10-Q filings, items are numbered separately in PART I and PART II:
- PART I: Item 1 (Financial Statements), Item 2 (MD&A), Item 3 (Quantitative/Qualitative), Item 4 (Controls)
- PART II: Item 1 (Legal Proceedings), Item 2 (Risk Factors), Item 3 (Defaults), Item 4 (Mine Safety), Item 5 (Other), Item 6 (Exhibits)

Current Bug:
1. Items from PART II are missing from `tenQ.items` and `tenQ.doc`
2. "Item 1" from PART I and "Item 1" from PART II get combined when accessing `tenQ['Item 1']`
3. The data model doesn't distinguish between items from different parts

Expected Behavior:
Items should be namespaced by their part (e.g., "Part I - Item 1" vs "Part II - Item 1") or accessible separately.

Reporter: Jason-AI-lab
Date: 2025-09-24
"""

from edgar import Company


def main():
    """Reproduce the issue with Apple's latest 10-Q filing."""

    print("=" * 80)
    print("Issue #447: Item Parsing Conflict Between Parts")
    print("=" * 80)

    # Get Apple's latest 10-Q
    company = Company("AAPL")
    tenQ = company.latest_tenq

    print(f"\nFiling: {tenQ.form}")
    print(f"Company: {tenQ.company}")
    print(f"Filing Date: {tenQ.filing_date}")

    # Check what items are available
    print("\n--- Available Items ---")
    print(f"Items from tenQ.items: {tenQ.items}")
    print(f"Number of items: {len(tenQ.items)}")

    # Expected structure for 10-Q
    print("\n--- Expected 10-Q Structure ---")
    print("PART I:")
    print("  Item 1 - Financial Statements")
    print("  Item 2 - Management's Discussion and Analysis (MD&A)")
    print("  Item 3 - Quantitative and Qualitative Disclosures About Market Risk")
    print("  Item 4 - Controls and Procedures")
    print("\nPART II:")
    print("  Item 1 - Legal Proceedings")
    print("  Item 1A - Risk Factors")
    print("  Item 2 - Unregistered Sales of Equity Securities and Use of Proceeds")
    print("  Item 3 - Defaults Upon Senior Securities")
    print("  Item 4 - Mine Safety Disclosures")
    print("  Item 5 - Other Information")
    print("  Item 6 - Exhibits")

    # Test accessing items
    print("\n--- Testing Item Access ---")

    # Test Item 1
    print("\n1. Accessing 'Item 1' (should be PART I - Financial Statements):")
    try:
        item1_text = tenQ['Item 1']
        if item1_text:
            # Check if it contains content from both parts
            has_financial_statements = 'financial statement' in item1_text.lower()
            has_legal_proceedings = 'legal proceeding' in item1_text.lower()

            print(f"   Text length: {len(item1_text)} characters")
            print(f"   Contains 'financial statement': {has_financial_statements}")
            print(f"   Contains 'legal proceeding': {has_legal_proceedings}")

            if has_financial_statements and has_legal_proceedings:
                print("\n   ⚠️  BUG CONFIRMED: Item 1 contains content from BOTH parts!")
                print("   This indicates PART I Item 1 and PART II Item 1 are being combined.")

            # Show first 500 characters
            print(f"\n   First 500 characters:")
            print(f"   {item1_text[:500]}...")
    except Exception as e:
        print(f"   Error accessing Item 1: {e}")

    # Test Item 2
    print("\n2. Accessing 'Item 2' (should be PART I - MD&A):")
    try:
        item2_text = tenQ['Item 2']
        if item2_text:
            print(f"   Text length: {len(item2_text)} characters")
            print(f"   First 200 characters:")
            print(f"   {item2_text[:200]}...")
    except Exception as e:
        print(f"   Error accessing Item 2: {e}")

    # Test with get_item_with_part method (new API)
    print("\n3. Testing get_item_with_part method:")
    try:
        part1_item1 = tenQ.get_item_with_part('PART I', 'Item 1', markdown=False)
        print(f"   PART I, Item 1: {len(part1_item1) if part1_item1 else 0} characters")

        part2_item1 = tenQ.get_item_with_part('PART II', 'Item 1', markdown=False)
        print(f"   PART II, Item 1: {len(part2_item1) if part2_item1 else 0} characters")

        if part1_item1 and part2_item1:
            print("\n   ✓ get_item_with_part() correctly distinguishes between parts")
        else:
            print("\n   ⚠️  get_item_with_part() may have issues")
    except Exception as e:
        print(f"   Error using get_item_with_part: {e}")

    # Check the structure
    print("\n4. Checking get_structure():")
    try:
        structure = tenQ.get_structure()
        print(structure)
    except Exception as e:
        print(f"   Error getting structure: {e}")

    # Verify chunked_document internals
    print("\n--- Analyzing Chunked Document Internals ---")
    try:
        chunk_df = tenQ.chunked_document._chunked_data

        # Show unique Part/Item combinations
        print("\nUnique Part/Item combinations found:")
        part_item_combos = chunk_df[chunk_df['Item'] != ''][['Part', 'Item']].drop_duplicates()
        for _, row in part_item_combos.iterrows():
            print(f"   {row['Part']:<12} {row['Item']}")

        # Count items by part
        print("\nItem counts by Part:")
        part_item_counts = chunk_df[chunk_df['Item'] != ''].groupby(['Part', 'Item']).size()
        for (part, item), count in part_item_counts.items():
            print(f"   {part:<12} {item:<10} ({count} chunks)")
    except Exception as e:
        print(f"   Error analyzing chunked document: {e}")

    print("\n" + "=" * 80)
    print("Summary:")
    print("=" * 80)
    print(f"Total items found: {len(tenQ.items)}")
    print(f"Expected for 10-Q: At least 10 items (4 in PART I + 6 in PART II)")

    if len(tenQ.items) < 10:
        print("\n⚠️  ISSUE CONFIRMED: Missing items from PART II")

    print("\nRoot Cause Analysis:")
    print("The ChunkedDocument.list_items() method returns deduplicated items")
    print("without considering the Part. This causes:")
    print("1. 'Item 1' from both parts to be merged into single entry")
    print("2. Loss of distinction between PART I and PART II items")
    print("3. Inability to access PART II items independently")

    print("\nRecommended Fix:")
    print("1. Update list_items() to return namespaced items (e.g., 'Part I - Item 1')")
    print("2. Update __getitem__ to handle both namespaced and legacy access patterns")
    print("3. Ensure backward compatibility for existing code")


if __name__ == '__main__':
    main()
