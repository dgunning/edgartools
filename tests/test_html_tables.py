import pytest
from bs4 import BeautifulSoup
from edgar.files.html import TableNode, TableRow, TableCell, StyleInfo, Document
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


def test_table_with_tbody_structure():
    """Test parsing of HTML tables with tbody elements containing tr rows
    
    This test covers the specific case that was failing before the fix where
    tables with <tbody><tr>...</tr></tbody> structure were not being processed
    because the parser was only looking for direct child <tr> elements.
    """
    html_content = """
    <html>
    <body>
        <div>Content before table</div>
        <table cellspacing="0" cellpadding="0" border="0" style="font-family: Arial; font-size: 10pt; width: 100%; border-collapse: collapse;">
            <tbody>
                <tr>
                    <td style="width: 35%; vertical-align: bottom;">
                        <div style="text-align: center;">Title of each class</div>
                    </td>
                    <td style="width: 30%; vertical-align: bottom;">
                        <div style="text-align: center;">Trading symbol(s)</div>
                    </td>
                    <td style="width: 34.94%; vertical-align: bottom;">
                        <div style="text-align: center;">Name of each exchange on which registered</div>
                    </td>
                </tr>
                <tr>
                    <td style="width: 35%; vertical-align: bottom;">
                        <div style="text-align: center;">Common Stock, $0.00001 par value per share</div>
                    </td>
                    <td style="width: 30%; vertical-align: bottom;">
                        <div style="text-align: center;">AAPL</div>
                    </td>
                    <td style="width: 34.94%; vertical-align: bottom;">
                        <div style="text-align: center;">The Nasdaq Stock Market LLC</div>
                    </td>
                </tr>
                <tr>
                    <td style="width: 35%; vertical-align: bottom;">
                        <div style="text-align: center;">0.000% Notes due 2025</div>
                    </td>
                    <td style="width: 30%; vertical-align: bottom;">
                        <div style="text-align: center;">—</div>
                    </td>
                    <td style="width: 34.94%; vertical-align: bottom;">
                        <div style="text-align: center;">The Nasdaq Stock Market LLC</div>
                    </td>
                </tr>
            </tbody>
        </table>
        <div>Content after table</div>
    </body>
    </html>
    """
    
    # Parse the document
    document = Document.parse(html_content)
    assert document is not None
    
    # Check that we have the expected nodes
    table_nodes = [node for node in document.nodes if node.type == 'table']
    text_nodes = [node for node in document.nodes if node.type == 'text_block']
    
    # Should have exactly 1 table node
    assert len(table_nodes) == 1, f"Expected 1 table node, got {len(table_nodes)}"
    
    # Verify the table structure
    table = table_nodes[0]
    assert table.row_count == 3, f"Expected 3 rows, got {table.row_count}"
    assert table.approximate_column_count == 3, f"Expected 3 columns, got {table.approximate_column_count}"
    
    # Verify table content by checking the first row
    first_row = table.content[0]
    assert len(first_row.cells) == 3
    
    # Check cell contents (the divs should be processed to extract text)
    cell_texts = [cell.content.strip() for cell in first_row.cells]
    assert "Title of each class" in cell_texts[0]
    assert "Trading symbol" in cell_texts[1]
    assert "exchange" in cell_texts[2]
    
    # Verify second row contains AAPL data
    second_row = table.content[1]
    cell_texts = [cell.content.strip() for cell in second_row.cells]
    assert "Common Stock" in cell_texts[0]
    assert "AAPL" in cell_texts[1]
    assert "Nasdaq" in cell_texts[2]
    
    # Should also have text nodes for content before/after table
    assert len(text_nodes) >= 2, f"Expected at least 2 text nodes, got {len(text_nodes)}"
    
    # Verify markdown conversion includes the table
    markdown = document.to_markdown()
    assert "Title of each class" in markdown
    assert "AAPL" in markdown
    assert "Common Stock" in markdown
    assert "|" in markdown  # Should contain table formatting


def test_table_with_nested_structure_multiple_tbody():
    """Test parsing of more complex table structures with multiple tbody elements"""
    html_content = """
    <html>
    <body>
        <table border="0" cellpadding="0" cellspacing="0">
            <thead>
                <tr>
                    <th>Header 1</th>
                    <th>Header 2</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>Data 1A</td>
                    <td>Data 1B</td>
                </tr>
                <tr>
                    <td>Data 2A</td>
                    <td>Data 2B</td>
                </tr>
            </tbody>
            <tbody>
                <tr>
                    <td>Data 3A</td>
                    <td>Data 3B</td>
                </tr>
            </tbody>
        </table>
    </body>
    </html>
    """
    
    document = Document.parse(html_content)
    assert document is not None
    
    table_nodes = [node for node in document.nodes if node.type == 'table']
    assert len(table_nodes) == 1
    
    table = table_nodes[0]
    # Should have all rows: 1 thead + 2 tbody sections with 3 data rows total = 4 total rows
    assert table.row_count == 4
    assert table.approximate_column_count == 2
    
    # Check content
    all_texts = []
    for row in table.content:
        for cell in row.cells:
            all_texts.append(cell.content.strip())
    
    # Should contain all the expected data
    expected_texts = ["Header 1", "Header 2", "Data 1A", "Data 1B", "Data 2A", "Data 2B", "Data 3A", "Data 3B"]
    for expected in expected_texts:
        assert expected in all_texts, f"Expected text '{expected}' not found in table content"
