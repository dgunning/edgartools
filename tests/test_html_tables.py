import pytest
from bs4 import BeautifulSoup
from edgar.files.html import TableNode, TableRow, TableCell, StyleInfo
from edgar.files.tables import ProcessedTable

def create_table_node(rows: list[list[tuple[str, int]]]) -> TableNode:
    """Helper to create a TableNode from a list of row specs
    Each row is a list of (content, colspan) tuples
    """
    table_rows = []
    for row_spec in rows:
        cells = [
            TableCell(content=content, colspan=colspan)
            for content, colspan in row_spec
        ]
        table_rows.append(TableRow(cells=cells))
    return TableNode(content=table_rows, style=StyleInfo())

def test_basic_row_count():
    """Test basic row counting"""
    # Simple 2x2 table
    table = create_table_node([
        [("A", 1), ("B", 1)],
        [("C", 1), ("D", 1)]
    ])
    assert table.row_count == 2
    assert table.processed_row_count == 2


def test_empty_table():
    """Test handling of empty tables"""
    table = create_table_node([])
    assert table.row_count == 0
    assert table.approximate_column_count == 0
    assert table.processed_row_count == 0
    assert table.processed_column_count == 0


def test_basic_column_count():
    """Test basic column counting"""
    # Simple 2x3 table
    table = create_table_node([
        [("A", 1), ("B", 1), ("C", 1)],
        [("D", 1), ("E", 1), ("F", 1)]
    ])
    assert table.approximate_column_count == 3
    assert table.processed_column_count == 3


def test_colspan_handling():
    """Test handling of colspans"""
    # Table with colspan
    table = create_table_node([
        [("Header", 2)],
        [("Col1", 1), ("Col2", 1)],
        [("Data", 2)]
    ])
    assert table.approximate_column_count == 2
    assert table.processed_column_count == 2


def test_irregular_columns():
    """Test handling of irregular column counts"""
    table = create_table_node([
        [("A", 1), ("B", 1)],
        [("C", 1)],  # Row with fewer columns
        [("D", 1), ("E", 1), ("F", 1)]  # Row with more columns
    ])
    assert table.approximate_column_count == 3
    # Processed count should standardize to max valid columns
    assert table.processed_column_count == 3


def test_complex_spans():
    """Test complex colspan scenarios"""
    table = create_table_node([
        [("Header1", 2), ("Header2", 1)],
        [("SubA", 1), ("SubB", 1), ("SubC", 1)],
        [("Data1", 3)],
        [("X", 1), ("Y", 1), ("Z", 1)]
    ])
    assert table.approximate_column_count == 3
    assert table.processed_column_count == 3


def test_processed_table_caching():
    """Test that processed results are cached"""
    table = create_table_node([
        [("A", 1), ("B", 1)],
        [("C", 1), ("D", 1)]
    ])

    # Force processing
    first_processed = table._processed
    second_processed = table._processed

    # Should be the same object (cached)
    assert first_processed is second_processed


def test_reset_processing():
    """Test processing reset"""
    table = create_table_node([
        [("A", 1), ("B", 1)],
        [("C", 1), ("D", 1)]
    ])

    # Force initial processing
    initial_processed = table._processed

    # Reset and reprocess
    table.reset_processing()
    new_processed = table._processed

    # Should be different objects
    assert initial_processed is not new_processed


def test_processed_table_headers():
    """Test row counting with headers"""
    table = create_table_node([
        [("Header1", 1), ("Header2", 1)],
        [("Data1", 1), ("Data2", 1)]
    ])

    # Mock processed table with explicit headers
    table._processed_table = ProcessedTable(
        headers=["Header1", "Header2"],
        data_rows=[["Data1", "Data2"]],
        column_alignments=["left", "right"]
    )

    assert table.processed_row_count == 2  # 1 header + 1 data row
    assert table.processed_column_count == 2


def test_edge_cases():
    """Test edge cases and boundary conditions"""
    # Test single cell table
    table = create_table_node([[("Single", 1)]])
    assert table.row_count == 1
    assert table.approximate_column_count == 1

    # Test table with empty cells
    table = create_table_node([
        [("", 1), ("", 1)],
        [("Data", 1), ("", 1)]
    ])
    assert table.row_count == 2
    assert table.approximate_column_count == 2

    # Test large colspan
    table = create_table_node([[("Wide", 100)]])
    assert table.approximate_column_count == 100

    # Test mixed empty and populated rows
    table = create_table_node([
        [("A", 1), ("B", 1)],
        [("", 1), ("", 1)],
        [("C", 1), ("D", 1)]
    ])
    assert table.row_count == 3
