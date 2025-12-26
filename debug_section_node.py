"""
Debug script to investigate section node structure and table linkage
"""

from edgar import Company


def debug_section_node_tree():
    """Debug the node tree structure for Item 8"""

    print("=" * 80)
    print("DEBUGGING SECTION NODE TREE")
    print("=" * 80)

    # Get PLTR 10-K
    company = Company("PLTR")
    filing = company.get_filings(form="10-K")[0]

    doc = filing.obj().document

    # Get Item 8 section
    item8 = doc.sections.get_item("8")

    print(f"\nSection: {item8.name}")
    print(f"Title: {item8.title}")
    print(f"Start offset: {item8.start_offset}")
    print(f"End offset: {item8.end_offset}")
    print(f"Detection method: {item8.detection_method}")
    print()

    # Investigate the node
    node = item8.node

    print(f"Node ID: {node.id}")
    print(f"Node type: {node.type}")
    print(f"Node tag: {node.tag_name}")
    print(f"Node content: {node.content}")
    print()

    # Check if node has children
    print("Checking node structure:")

    if hasattr(node, 'children'):
        print(f"  Has children: {hasattr(node, 'children')}")
        if node.children:
            print(f"  Number of children: {len(node.children)}")
            print(f"  First 5 children:")
            for i, child in enumerate(node.children[:5]):
                print(f"    Child {i+1}: {type(child).__name__} - {getattr(child, 'tag_name', 'N/A')}")
        else:
            print(f"  Children list is empty!")
    else:
        print(f"  No children attribute")

    # Check node.find() method
    print("\nTesting node.find() method:")

    try:
        from edgar.documents.table_nodes import TableNode

        # Find tables in node
        tables = node.find(lambda n: isinstance(n, TableNode))
        print(f"  Tables found via node.find(): {len(tables)}")

        if not tables:
            print("  No tables found in node tree!")

    except Exception as e:
        print(f"  Error: {e}")
        import traceback
        traceback.print_exc()

    # Compare with document-level tables
    print("\nComparing with document-level tables:")
    doc_tables = doc.tables
    print(f"  Total tables in document: {len(doc_tables)}")

    # Check if any tables have positions within Item 8 range
    print(f"\nChecking which tables fall within Item 8 range ({item8.start_offset}-{item8.end_offset}):")

    tables_in_range = []
    for i, table in enumerate(doc_tables):
        # Check if table has position info
        if hasattr(table, 'node'):
            table_node = table.node

            # Try to get position
            if hasattr(table_node, 'metadata'):
                metadata = table_node.metadata
                print(f"\n  Table {i+1} metadata: {metadata}")

    # Alternative: Check table parent nodes
    print("\n" + "=" * 80)
    print("INVESTIGATING TABLE PARENT NODES")
    print("=" * 80)

    for i, table in enumerate(doc_tables[:10]):
        print(f"\nTable {i+1}:")
        print(f"  Caption: {table.caption or 'N/A'}")

        # Check node
        if hasattr(table, 'node'):
            print(f"  Table node ID: {table.node.id}")

        # Check parent
        parent = getattr(table, 'parent', None)
        if parent:
            print(f"  Parent: {type(parent).__name__}")
            print(f"  Parent ID: {parent.id}")

            # Walk up parent chain
            current = parent
            depth = 0
            while current and depth < 10:
                print(f"    Parent {depth}: {type(current).__name__} - {getattr(current, 'tag_name', 'N/A')}")

                # Check if this parent is a section
                if hasattr(current, 'metadata'):
                    if 'section_name' in current.metadata:
                        print(f"      --> Section: {current.metadata['section_name']}")

                # Go to next parent
                current = getattr(current, 'parent', None)
                depth += 1


def debug_section_detection_toc():
    """Debug TOC-based section detection"""

    print("\n\n")
    print("=" * 80)
    print("DEBUGGING TOC-BASED SECTION DETECTION")
    print("=" * 80)

    company = Company("PLTR")
    filing = company.get_filings(form="10-K")[0]

    doc = filing.obj().document

    # Item 8 was detected via TOC
    item8 = doc.sections.get_item("8")

    print(f"\nSection: {item8.name}")
    print(f"Detection method: {item8.detection_method}")
    print(f"Confidence: {item8.confidence}")
    print(f"Offsets: {item8.start_offset} - {item8.end_offset} (length: {item8.end_offset - item8.start_offset:,})")

    # The issue is likely that TOC-based sections don't properly populate the node tree
    print("\nTOC-based section characteristics:")
    print(f"  Has _text_extractor: {item8._text_extractor is not None}")
    print(f"  Node has content: {item8.node.content is not None}")
    print(f"  Node has children: {hasattr(item8.node, 'children') and bool(item8.node.children)}")

    # The problem: TOC-based sections use offsets, but node tree might not be populated
    print("\n" + "=" * 80)
    print("ROOT CAUSE HYPOTHESIS")
    print("=" * 80)
    print("""
The bug is:

1. Item 8 section is detected via TOC (Table of Contents) anchors
2. TOC detection sets start_offset and end_offset based on anchor positions
3. But the section.node is a SectionNode with NO children in its tree
4. When section.tables() calls node.find(), it searches the (empty) node tree
5. Result: 0 tables found, even though tables exist in the document

The fix should:
- Either populate the section.node tree with children in that offset range
- Or make section.tables() search by offset range instead of node tree
    """)


if __name__ == "__main__":
    debug_section_node_tree()
    debug_section_detection_toc()
