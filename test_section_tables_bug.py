"""
Test to reproduce and verify the section.tables() bug fix

BUG: TOC-based sections return 0 tables even when tables exist
"""

import pytest
from edgar import Company


def test_section_tables_bug_reproduction():
    """
    Reproduce the bug: Item 8 section has 0 tables

    Expected: Should find 85+ tables in Item 8
    Actual (BUGGY): Returns 0 tables
    """

    print("\n" + "=" * 80)
    print("TEST: Section.tables() Bug Reproduction")
    print("=" * 80)

    # Get PLTR 10-K
    company = Company("PLTR")
    filing = company.get_filings(form="10-K")[0]

    print(f"\nFiling: {filing.form} filed {filing.filing_date}")

    # Get document
    doc = filing.obj().document

    print(f"Total sections: {len(doc.sections)}")
    print(f"Total tables in document: {len(doc.tables)}")

    # Get Item 8 section
    item8 = doc.sections.get_item("8")

    print(f"\nItem 8 Section:")
    print(f"  Name: {item8.name}")
    print(f"  Title: {item8.title}")
    print(f"  Detection method: {item8.detection_method}")
    print(f"  Offsets: {item8.start_offset} - {item8.end_offset}")

    # Try to get tables
    tables = item8.tables()

    print(f"\nTables found: {len(tables)}")

    # BUG: This assertion FAILS
    # Expected: 85+ tables (as found by llm_extraction)
    # Actual: 0 tables
    assert len(tables) > 0, "BUG: Item 8 should have tables but returned 0"

    # Should find at least 50 tables (conservative estimate)
    assert len(tables) >= 50, f"BUG: Expected 50+ tables, got {len(tables)}"

    print("\n[OK] TEST PASSED - Bug is fixed!")


def test_section_node_structure():
    """
    Test that reveals WHY the bug occurs

    Shows that TOC sections have empty children lists
    """

    print("\n" + "=" * 80)
    print("TEST: Section Node Structure")
    print("=" * 80)

    company = Company("PLTR")
    filing = company.get_filings(form="10-K")[0]
    doc = filing.obj().document

    item8 = doc.sections.get_item("8")

    print(f"\nSection: {item8.name}")
    print(f"Detection: {item8.detection_method}")

    # Check node structure
    node = item8.node

    print(f"\nNode structure:")
    print(f"  Type: {node.type}")
    print(f"  Has children attribute: {hasattr(node, 'children')}")

    if hasattr(node, 'children'):
        print(f"  Children count: {len(node.children)}")

        # BUG: Children list is empty!
        assert len(node.children) == 0, "BUG: TOC section has empty children!"

        print("\n[X] BUG CONFIRMED: Section node has NO children")
        print("  This is why tables() returns 0")

    # Compare with document tables
    doc_tables = doc.tables
    print(f"\nDocument has {len(doc_tables)} tables")
    print(f"But section.tables() found {len(item8.tables())}")

    print("\n[X] BUG: Tables exist but aren't in section tree")


def test_table_parent_chain():
    """
    Test showing tables are NOT connected to section nodes
    """

    print("\n" + "=" * 80)
    print("TEST: Table Parent Chain Analysis")
    print("=" * 80)

    company = Company("PLTR")
    filing = company.get_filings(form="10-K")[0]
    doc = filing.obj().document

    # Check first 10 tables
    for i, table in enumerate(doc.tables[:10]):
        print(f"\nTable {i+1}:")

        # Walk up parent chain
        parent = getattr(table, 'parent', None)
        depth = 0

        parent_types = []
        while parent and depth < 10:
            parent_type = type(parent).__name__
            parent_types.append(parent_type)

            # Check if we find a SectionNode
            if parent_type == 'SectionNode':
                print(f"  [OK] Found SectionNode in parent chain!")
                break

            parent = getattr(parent, 'parent', None)
            depth += 1

        print(f"  Parent chain: {' -> '.join(parent_types)}")

        # BUG: No SectionNode in any parent chain
        assert 'SectionNode' not in parent_types, "BUG: Tables should have SectionNode parent"

    print("\n[X] BUG CONFIRMED: No tables have SectionNode in parent chain")


def test_workaround_using_document_tables():
    """
    Workaround: Get tables from document level instead of section

    This is what llm_extraction.py does (and why it works)

    Also converts tables to DataFrames for data analysis
    """

    print("\n" + "=" * 80)
    print("TEST: Workaround Using Document-Level Tables")
    print("=" * 80)

    company = Company("PLTR")
    filing = company.get_filings(form="10-K")[0]
    doc = filing.obj().document

    # Get all document tables (works!)
    all_tables = doc.tables

    print(f"\nDocument-level extraction:")
    print(f"  Total tables: {len(all_tables)}")

    # Count by type
    from collections import Counter
    type_counts = Counter(t.table_type.name for t in all_tables)

    print(f"\nTable types:")
    for table_type, count in type_counts.most_common():
        print(f"  {table_type}: {count}")

    # This works!
    assert len(all_tables) > 0, "Document.tables() works"
    assert len(all_tables) >= 50, f"Found {len(all_tables)} tables"

    # Convert tables to DataFrames
    print("\n" + "-" * 80)
    print("Converting tables to DataFrames:")
    print("-" * 80)

    dataframes = []
    successful = 0
    failed = 0

    for i, table in enumerate(all_tables):
        try:
            # Convert table to DataFrame
            df = table.to_dataframe()

            # Store in list
            dataframes.append({
                'index': i + 1,
                'caption': table.caption or f'Table {i+1}',
                'type': table.table_type.name,
                'dataframe': df,
                'shape': df.shape
            })

            successful += 1

            # Show first few conversions
            if i < 5:
                print(f"\n  Table {i+1}:")
                print(f"    Caption: {table.caption or 'N/A'}")
                print(f"    Type: {table.table_type.name}")
                print(f"    DataFrame shape: {df.shape}")
                print(f"    Preview:")
                print(df.head(3).to_string(max_colwidth=30, max_rows=3))

        except Exception as e:
            failed += 1
            if i < 5:
                print(f"\n  Table {i+1}: Failed - {e}")

    # Summary
    print(f"\n" + "=" * 80)
    print(f"DataFrame Conversion Summary:")
    print(f"  Total tables: {len(all_tables)}")
    print(f"  Successfully converted: {successful}")
    print(f"  Failed: {failed}")
    print(f"  Success rate: {successful/len(all_tables)*100:.1f}%")

    # Verify we have DataFrames
    assert len(dataframes) > 0, "Should have at least some DataFrames"
    assert successful >= 30, f"Expected 30+ successful conversions, got {successful}"

    # Filter financial tables only
    financial_dfs = [
        item for item in dataframes
        if item['type'] == 'FINANCIAL'
    ]

    print(f"\n  Financial tables: {len(financial_dfs)}")

    # Show financial table details
    if financial_dfs:
        print(f"\n  Financial table shapes:")
        for item in financial_dfs[:10]:
            print(f"    {item['caption'][:50]:50} {item['shape']}")

    print("\n[OK] WORKAROUND: Document.tables() returns all tables")
    print(f"[OK] Created {len(dataframes)} DataFrames")
    print("  Use this until section.tables() is fixed")

    # Return dataframes for further use
    return dataframes


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("SECTION.TABLES() BUG TEST SUITE")
    print("=" * 80)

    try:
        test_section_tables_bug_reproduction()
    except AssertionError as e:
        print(f"\n[X] BUG CONFIRMED: {e}")

    try:
        test_section_node_structure()
    except AssertionError as e:
        print(f"\n[X] Expected assertion (demonstrates bug): {e}")

    try:
        test_table_parent_chain()
    except AssertionError as e:
        print(f"\n[X] Expected assertion (demonstrates bug): {e}")

    # Run workaround test and get DataFrames
    dataframes = test_workaround_using_document_tables()

    # Optional: Save DataFrames to files
    print("\n" + "=" * 80)
    print("SAVING DATAFRAMES")
    print("=" * 80)

    import os
    os.makedirs("output_dataframes", exist_ok=True)

    # Save first 10 financial tables as CSV
    financial_dfs = [df for df in dataframes if df['type'] == 'FINANCIAL']

    for i, item in enumerate(financial_dfs[:10]):
        filename = f"output_dataframes/table_{item['index']:03d}_{item['type']}.csv"
        try:
            item['dataframe'].to_csv(filename, index=True)
            print(f"  Saved: {filename} ({item['shape']})")
        except Exception as e:
            print(f"  Failed to save {filename}: {e}")

    print(f"\n[OK] Saved {min(10, len(financial_dfs))} financial tables to output_dataframes/")

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"""
BUG CONFIRMED:
  - section.tables() returns 0 tables (should be 85+)
  - TOC sections have empty children lists
  - Tables are NOT in section node tree
  - Tables only accessible via document.tables()

WORKAROUND TESTED:
  - Use doc.tables instead of section.tables() [OK]
  - Successfully converted {len(dataframes)} tables to DataFrames
  - {len(financial_dfs)} financial tables found
  - Saved sample tables to output_dataframes/

FIX NEEDED:
  - Implement offset-based table filtering in Section.tables()
  - See BUG_REPORT_SECTION_TABLES.md for details
    """)
