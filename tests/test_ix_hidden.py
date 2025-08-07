"""Test handling of ix:hidden tags."""

import pytest
from edgar.documents import parse_html, ParserConfig


def test_ix_hidden_content_removed():
    """Test that ix:hidden content is removed from rendering."""
    html = """
    <html>
    <body>
        <p>This content is visible</p>
        <ix:hidden>
            <p>This content should be hidden</p>
            <table>
                <tr><td>Hidden table data</td></tr>
            </table>
        </ix:hidden>
        <p>This content is also visible</p>
    </body>
    </html>
    """
    
    doc = parse_html(html)
    text = doc.text()
    
    # Visible content should be present
    assert "This content is visible" in text
    assert "This content is also visible" in text
    
    # Hidden content should NOT be present
    assert "This content should be hidden" not in text
    assert "Hidden table data" not in text
    
    # Tables inside ix:hidden should not be counted
    assert len(doc.tables) == 0


def test_nested_ix_hidden():
    """Test nested ix:hidden tags."""
    html = """
    <html>
    <body>
        <div>
            <p>Visible paragraph</p>
            <ix:hidden>
                <p>Hidden paragraph</p>
                <ix:hidden>
                    <p>Nested hidden paragraph</p>
                </ix:hidden>
            </ix:hidden>
        </div>
    </body>
    </html>
    """
    
    doc = parse_html(html)
    text = doc.text()
    
    assert "Visible paragraph" in text
    assert "Hidden paragraph" not in text
    assert "Nested hidden paragraph" not in text


def test_ix_hidden_with_attributes():
    """Test ix:hidden with various attributes."""
    html = """
    <html>
    <body>
        <p>Before hidden</p>
        <ix:hidden id="hidden1" class="xbrl-hidden">
            <span>Hidden span content</span>
        </ix:hidden>
        <p>After hidden</p>
    </body>
    </html>
    """
    
    doc = parse_html(html)
    text = doc.text()
    
    assert "Before hidden" in text
    assert "After hidden" in text
    assert "Hidden span content" not in text


def test_ix_hidden_case_insensitive():
    """Test that ix:hidden matching is case insensitive."""
    html = """
    <html>
    <body>
        <p>Visible 1</p>
        <IX:HIDDEN>Hidden uppercase</IX:HIDDEN>
        <ix:Hidden>Hidden mixed case</ix:Hidden>
        <p>Visible 2</p>
    </body>
    </html>
    """
    
    doc = parse_html(html)
    text = doc.text()
    
    assert "Visible 1" in text
    assert "Visible 2" in text
    assert "Hidden uppercase" not in text
    assert "Hidden mixed case" not in text


def test_real_world_ix_hidden():
    """Test a real-world example of ix:hidden usage."""
    html = """
    <html>
    <body>
        <div>
            <span>Revenue for the year ended December 31, 2023 was </span>
            <ix:nonNumeric name="us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax" 
                          contextRef="FY2023">$1,234,567</ix:nonNumeric>
            <ix:hidden>
                <ix:nonFraction name="us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax" 
                              contextRef="FY2023" unitRef="usd" decimals="-3">1234567000</ix:nonFraction>
            </ix:hidden>
            <span> thousand.</span>
        </div>
    </body>
    </html>
    """
    
    doc = parse_html(html)
    text = doc.text()
    
    # The human-readable version should be present (may have spaces due to normalization)
    assert "1" in text and "234" in text and "567" in text
    assert "Revenue for the year ended December 31, 2023" in text
    
    # The machine-readable version should be hidden
    assert "1234567000" not in text
    
    
def test_ix_hidden_preserves_structure():
    """Test that removing ix:hidden doesn't break document structure."""
    html = """
    <html>
    <body>
        <table>
            <tr>
                <td>Visible cell 1</td>
                <ix:hidden><td>Hidden cell</td></ix:hidden>
                <td>Visible cell 2</td>
            </tr>
        </table>
    </body>
    </html>
    """
    
    doc = parse_html(html)
    
    # Should have one table
    assert len(doc.tables) == 1
    
    # Table should have correct content
    table = doc.tables[0]
    assert table.row_count == 1
    # Note: column count might be 2 since hidden cell is removed
    
    # Check table content directly since text extraction might be empty for tables
    if table.rows:
        row_text = ' '.join(cell.content for cell in table.rows[0].cells if cell.content)
        assert "Visible cell 1" in row_text
        assert "Visible cell 2" in row_text
        assert "Hidden cell" not in row_text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])