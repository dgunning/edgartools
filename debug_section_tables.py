"""
Debug script to investigate edgar.documents section-table attribution bug

Issue: PLTR 10-K Item 8 shows 0 tables even though tables exist
"""

from edgar import Company


def debug_section_tables():
    """Debug why Item 8 section has no tables"""

    print("=" * 80)
    print("DEBUGGING SECTION-TABLE ATTRIBUTION")
    print("=" * 80)

    # Get PLTR 10-K
    company = Company("PLTR")
    filing = company.get_filings(form="10-K")[0]

    print(f"\nFiling: {filing.form} filed {filing.filing_date}")
    print(f"Accession: {filing.accession_no}")

    # Get document
    tenk = filing.obj()
    doc = tenk.document

    print(f"\nDocument loaded")
    print(f"Total sections: {len(doc.sections)}")
    print(f"Total tables: {len(doc.tables)}")
    print()

    # List all sections
    print("=" * 80)
    print("ALL SECTIONS")
    print("=" * 80)

    sections_dict = doc.sections.__dict__ if hasattr(doc.sections, '__dict__') else {}

    print(f"\nSections object type: {type(doc.sections)}")
    print(f"Sections attributes: {dir(doc.sections)[:10]}")

    # Try to get all section items
    try:
        # Check if sections is iterable
        if hasattr(doc.sections, 'items'):
            for key, section in doc.sections.items():
                print(f"\n  Section: {key}")
                print(f"    Title: {getattr(section, 'title', 'N/A')}")
                print(f"    Type: {type(section)}")
        elif hasattr(doc.sections, '__iter__'):
            for i, section in enumerate(doc.sections):
                print(f"\n  Section {i}: {section}")
    except Exception as e:
        print(f"  Error iterating sections: {e}")

    # Try different ways to access Item 8
    print("\n" + "=" * 80)
    print("ACCESSING ITEM 8")
    print("=" * 80)

    item8_section = None

    # Method 1: get_item
    print("\n[Method 1] doc.sections.get_item('8')")
    try:
        item8_section = doc.sections.get_item("8")
        print(f"  Result: {item8_section}")
        if item8_section:
            print(f"  Title: {item8_section.title}")
            print(f"  Type: {type(item8_section)}")
    except Exception as e:
        print(f"  Error: {e}")

    # Method 2: get_section
    print("\n[Method 2] doc.get_section('item_8')")
    try:
        item8_v2 = doc.get_section("item_8")
        print(f"  Result: {item8_v2}")
        if item8_v2:
            print(f"  Title: {getattr(item8_v2, 'title', 'N/A')}")
    except Exception as e:
        print(f"  Error: {e}")

    # Method 3: Direct attribute access
    print("\n[Method 3] Check sections attributes")
    try:
        if hasattr(doc.sections, '__dict__'):
            for attr in doc.sections.__dict__:
                if 'item' in attr.lower() or '8' in attr:
                    print(f"  Found attribute: {attr}")
                    value = getattr(doc.sections, attr)
                    print(f"    Value: {value}")
    except Exception as e:
        print(f"  Error: {e}")

    # Get tables from Item 8 (if found)
    if item8_section:
        print("\n" + "=" * 80)
        print("ITEM 8 TABLES")
        print("=" * 80)

        print(f"\nItem 8 section: {item8_section.title}")

        # Try to get tables
        try:
            tables = item8_section.tables()
            print(f"Tables count: {len(tables)}")

            if tables:
                for i, table in enumerate(tables[:3]):
                    print(f"\n  Table {i+1}:")
                    print(f"    Caption: {table.caption}")
                    print(f"    Type: {table.table_type}")
            else:
                print("  No tables found!")
        except Exception as e:
            print(f"  Error getting tables: {e}")
            import traceback
            traceback.print_exc()

        # Check section properties
        print("\n" + "-" * 80)
        print("Section properties:")
        print("-" * 80)

        for attr in dir(item8_section):
            if not attr.startswith('_'):
                try:
                    value = getattr(item8_section, attr)
                    if not callable(value):
                        print(f"  {attr}: {value}")
                except Exception as e:
                    print(f"  {attr}: Error - {e}")

    # Analyze all tables
    print("\n" + "=" * 80)
    print("ALL TABLES ANALYSIS")
    print("=" * 80)

    print(f"\nTotal tables in document: {len(doc.tables)}")

    # Show first 10 tables
    for i, table in enumerate(doc.tables[:10]):
        print(f"\n  Table {i+1}:")
        print(f"    Caption: {table.caption or 'N/A'}")
        print(f"    Type: {table.table_type.name}")
        print(f"    Rows: {len(table.rows)}")

        # Check if table has parent info
        if hasattr(table, 'parent'):
            print(f"    Parent: {table.parent}")

        if hasattr(table, 'node'):
            print(f"    Node: {type(table.node)}")

    # Check table distribution
    print("\n" + "-" * 80)
    print("Table type distribution:")
    print("-" * 80)

    from collections import Counter
    type_counts = Counter(t.table_type.name for t in doc.tables)

    for table_type, count in type_counts.most_common():
        print(f"  {table_type}: {count}")

    # Try to find Item 8 in HTML
    print("\n" + "=" * 80)
    print("SEARCHING HTML FOR ITEM 8")
    print("=" * 80)

    html = filing.html()
    print(f"\nHTML length: {len(html):,} chars")

    # Search for Item 8 patterns
    patterns = [
        "ITEM 8",
        "Item 8",
        "item 8",
        "ITEM&#160;8",
        "Item&#160;8",
    ]

    for pattern in patterns:
        count = html.count(pattern)
        if count > 0:
            print(f"  '{pattern}': {count} occurrences")

            # Find first occurrence
            idx = html.find(pattern)
            if idx != -1:
                context = html[max(0, idx-100):idx+200]
                print(f"    First occurrence context:")
                print(f"    ...{context}...")


def debug_section_detection():
    """Debug how sections are detected"""

    print("\n\n")
    print("=" * 80)
    print("SECTION DETECTION ANALYSIS")
    print("=" * 80)

    company = Company("PLTR")
    filing = company.get_filings(form="10-K")[0]

    doc = filing.obj().document

    # Check sections object structure
    print(f"\nSections object: {type(doc.sections)}")
    print(f"Sections repr: {repr(doc.sections)}")

    # Get sections methods
    print("\nSections methods:")
    for method in dir(doc.sections):
        if not method.startswith('_'):
            print(f"  - {method}")

    # Try to understand section storage
    print("\nInvestigating section storage:")

    if hasattr(doc.sections, '_sections'):
        print(f"  _sections: {type(doc.sections._sections)}")
        print(f"  _sections keys: {list(doc.sections._sections.keys())[:10]}")

    if hasattr(doc.sections, 'sections'):
        print(f"  sections: {type(doc.sections.sections)}")

    if hasattr(doc.sections, '__dict__'):
        print(f"  __dict__ keys: {list(doc.sections.__dict__.keys())[:10]}")


if __name__ == "__main__":
    debug_section_tables()
    debug_section_detection()
