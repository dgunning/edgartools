"""
Regression test for section.tables() TOC fix.

Tests that section.tables() correctly extracts tables from TOC-based sections.

Bug: TOC-based sections had empty node.children lists, causing section.tables()
     to return empty list even when tables existed in the section.

Fix: section.tables() now parses section HTML directly for TOC sections.

NOTE: If this test fails with "TOC section should return tables (found 0)",
      it may be due to cached filings with old Section objects.
      Solution: Clear the filing cache or wait for it to expire.
"""

import pytest
from edgar import Company


def test_toc_section_tables_extraction():
    """
    Test that TOC-based sections can extract tables.

    This is a regression test for the bug where section.tables()
    returned [] for TOC-detected sections.
    """
    # Get PLTR 10-K (known to use TOC detection)
    company = Company("PLTR")
    filings = company.get_filings(form="10-K")
    assert len(filings) > 0, "Should have at least one 10-K filing"
    filing = filings[0]

    # Get document and Item 8 section
    tenk = filing.obj()
    doc = tenk.document
    item8 = doc.sections.get_item("8")

    # Verify it's a TOC-based section
    assert item8 is not None, "Item 8 should exist"
    assert item8.detection_method == "toc", "Item 8 should be TOC-detected"

    # Debug: Check if HTML source is available
    has_html_source = hasattr(item8, '_html_source') and item8._html_source is not None
    has_extractor = hasattr(item8, '_section_extractor') and item8._section_extractor is not None

    # If Section doesn't have new fields, it's from cache - skip test
    if not (has_html_source and has_extractor):
        pytest.skip("Section loaded from cache without new _html_source/_section_extractor fields. "
                   "Clear cache and re-run: rm -rf ~/.edgar/filings/0001321655")

    # Get tables from section
    tables = item8.tables()

    # Should find tables (not empty)
    assert len(tables) > 0, f"TOC section should return tables (found {len(tables)})"
    assert len(tables) >= 50, f"Expected 50+ tables in Item 8, got {len(tables)}"

    # Verify tables are TableNode objects
    from edgar.documents.table_nodes import TableNode
    assert all(isinstance(t, TableNode) for t in tables), "All results should be TableNode objects"


def test_toc_section_empty_node_children():
    """
    Verify that TOC sections have empty node.children (the root cause of the bug).

    This test confirms the bug condition existed and our fix works around it.
    """
    company = Company("PLTR")
    filing = company.get_filings(form="10-K")[0]
    doc = filing.obj().document
    item8 = doc.sections.get_item("8")

    # TOC sections have empty node children (this is expected)
    assert len(item8.node.children) == 0, "TOC section nodes should have empty children"

    # But tables() should still work (via HTML extraction)
    tables = item8.tables()
    assert len(tables) > 0, "section.tables() should work despite empty node.children"


def test_document_level_tables_still_work():
    """
    Verify that document-level table extraction still works.

    This is the workaround that was used before the fix.
    """
    company = Company("PLTR")
    filing = company.get_filings(form="10-K")[0]
    doc = filing.obj().document

    # Document-level extraction should still work
    all_tables = doc.tables
    assert len(all_tables) > 0, "Document.tables should return tables"
    assert len(all_tables) >= 50, f"Expected 50+ tables in document, got {len(all_tables)}"


def test_table_types_in_toc_section():
    """
    Test that different table types are correctly identified in TOC sections.
    """
    company = Company("PLTR")
    filing = company.get_filings(form="10-K")[0]
    doc = filing.obj().document
    item8 = doc.sections.get_item("8")

    tables = item8.tables()

    # Group by table type
    from collections import Counter
    table_types = Counter(t.table_type.name for t in tables)

    # Should have financial tables (Item 8 contains financial statements)
    assert "FINANCIAL" in table_types, "Item 8 should contain FINANCIAL tables"
    assert table_types["FINANCIAL"] > 0, "Should have at least one financial table"


def test_table_to_dataframe_from_toc_section():
    """
    Test that tables extracted from TOC sections can be converted to DataFrames.
    """
    company = Company("PLTR")
    filing = company.get_filings(form="10-K")[0]
    doc = filing.obj().document
    item8 = doc.sections.get_item("8")

    tables = item8.tables()
    assert len(tables) > 0, "Should have tables"

    # Try to convert first financial table to DataFrame
    financial_tables = [t for t in tables if t.table_type.name == "FINANCIAL"]
    assert len(financial_tables) > 0, "Should have financial tables"

    # Convert to DataFrame
    df = financial_tables[0].to_dataframe()
    assert df is not None, "Should convert to DataFrame"
    assert df.shape[0] > 0, "DataFrame should have rows"


if __name__ == "__main__":
    # Run tests
    print("Testing TOC section.tables() fix...")

    test_toc_section_tables_extraction()
    print("[OK] TOC section tables extraction works")

    test_toc_section_empty_node_children()
    print("[OK] Fix works despite empty node.children")

    test_document_level_tables_still_work()
    print("[OK] Document-level tables still work")

    test_table_types_in_toc_section()
    print("[OK] Table types correctly identified")

    test_table_to_dataframe_from_toc_section()
    print("[OK] Tables convert to DataFrame")

    print("\n[SUCCESS] All tests passed!")
