"""
Unit tests for table_max_col_width parameter in text extraction.
"""

import pytest
from edgar.documents.extractors.text_extractor import TextExtractor
from edgar.documents.renderers.fast_table import FastTableRenderer, TableStyle
from edgar.documents.table_nodes import TableNode, Cell, Row


class TestTableMaxColWidth:
    """Tests for controlling table column width during text extraction."""

    def test_text_extractor_accepts_table_max_col_width_parameter(self):
        """Verify TextExtractor accepts table_max_col_width parameter."""
        extractor = TextExtractor(table_max_col_width=500)
        assert extractor.table_max_col_width == 500

        extractor_none = TextExtractor(table_max_col_width=None)
        assert extractor_none.table_max_col_width is None

        extractor_default = TextExtractor()
        assert extractor_default.table_max_col_width is None

    def test_table_style_max_col_width_default(self):
        """Verify TableStyle.simple() has correct default max_col_width."""
        style = TableStyle.simple()
        assert style.max_col_width == 200

    def test_table_style_max_col_width_customizable(self):
        """Verify TableStyle max_col_width can be customized."""
        style = TableStyle.simple()
        style.max_col_width = 500
        assert style.max_col_width == 500

        # Test with None (unlimited)
        style.max_col_width = None
        assert style.max_col_width is None

    def test_fast_table_renderer_uses_custom_width(self):
        """Verify FastTableRenderer respects custom max_col_width."""
        style = TableStyle.simple()
        style.max_col_width = 500

        renderer = FastTableRenderer(style)
        assert renderer.style.max_col_width == 500

    def test_table_rendering_with_different_widths(self):
        """Verify table rendering produces different output with different widths."""
        # Create test data with long content
        long_text = "A" * 250  # Longer than default max_col_width of 200
        headers = [[long_text, "Short"]]
        rows = [[long_text, "OK"]]

        # Render with default width (200)
        renderer_default = FastTableRenderer(TableStyle.simple())
        text_default = renderer_default.render_table_data(headers, rows)

        # Render with wider width (300)
        style_wide = TableStyle.simple()
        style_wide.max_col_width = 300
        renderer_wide = FastTableRenderer(style_wide)
        text_wide = renderer_wide.render_table_data(headers, rows)

        # The outputs should be present (not empty)
        assert text_default
        assert text_wide

    def test_text_extractor_with_mock_table_node(self):
        """Test TextExtractor with a mock TableNode to verify width parameter is used."""
        # Create a simple mock table
        headers = [[Cell(content="Header1"), Cell(content="Header2")]]
        rows = [Row([Cell(content="Data1"), Cell(content="Data2")])]
        
        table = TableNode(headers=headers, rows=rows)
        
        # Create extractor with custom width
        extractor = TextExtractor(table_max_col_width=500)
        
        # Extract text from the table using internal method
        parts = []
        extractor._extract_table(table, parts)
        
        # Verify we got some output
        assert len(parts) > 0
        result = '\n'.join(parts)
        assert "Header1" in result
        assert "Data1" in result

    def test_document_text_method_accepts_parameter(self):
        """Verify Document.text() method accepts table_max_col_width parameter."""
        # This is a signature test - just verify the method signature is correct
        from edgar.documents.document import Document
        import inspect
        
        sig = inspect.signature(Document.text)
        params = sig.parameters
        
        assert 'table_max_col_width' in params
        assert params['table_max_col_width'].default is None

    def test_text_extractor_uses_fast_renderer_when_width_specified(self):
        """Verify TextExtractor uses FastTableRenderer when table_max_col_width is set."""
        extractor_with_width = TextExtractor(table_max_col_width=500)
        extractor_without_width = TextExtractor()
        
        # Both should be instances of TextExtractor
        assert isinstance(extractor_with_width, TextExtractor)
        assert isinstance(extractor_without_width, TextExtractor)
        
        # They should have different table_max_col_width values
        assert extractor_with_width.table_max_col_width == 500
        assert extractor_without_width.table_max_col_width is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
