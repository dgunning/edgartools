"""
Edge case tests for HTML parser.

Tests parser robustness against:
- Empty/minimal documents
- Malformed HTML
- Extreme structures (deep nesting, large colspan/rowspan)
- Unicode and special characters
- Invalid inputs
"""

import pytest
from edgar.documents import parse_html
from edgar.documents.exceptions import HTMLParsingError


class TestEmptyAndMinimalDocuments:
    """Test handling of empty and minimal documents."""

    @pytest.mark.fast
    def test_empty_html(self):
        """Empty HTML should parse gracefully."""
        html = ""
        doc = parse_html(html)
        assert doc is not None

    @pytest.mark.fast
    def test_empty_document(self):
        """Document with no content should parse."""
        html = "<html><body></body></html>"
        doc = parse_html(html)
        assert doc is not None
        assert len(doc.text()) == 0
        assert len(doc.tables) == 0

    @pytest.mark.fast
    def test_minimal_text_only(self):
        """Minimal document with just text."""
        html = "<html><body>Hello World</body></html>"
        doc = parse_html(html)
        assert doc is not None
        assert "Hello World" in doc.text()

    @pytest.mark.fast
    def test_only_whitespace(self):
        """Document with only whitespace."""
        html = "<html><body>   \n\n   \t\t   </body></html>"
        doc = parse_html(html)
        assert doc is not None
        # May have minimal whitespace in output


class TestMalformedHTML:
    """Test handling of malformed HTML."""

    @pytest.mark.fast
    def test_unclosed_tags(self):
        """Unclosed tags should be handled."""
        html = "<html><body><p>Unclosed paragraph<div>And div</body></html>"
        doc = parse_html(html)
        assert doc is not None
        # Parser should auto-close tags

    @pytest.mark.fast
    def test_mismatched_tags(self):
        """Mismatched tags should be handled."""
        html = "<html><body><b>Bold<i>Italic</b>Text</i></body></html>"
        doc = parse_html(html)
        assert doc is not None

    @pytest.mark.fast
    def test_missing_closing_html(self):
        """Missing closing HTML tag."""
        html = "<html><body>Content</body>"
        doc = parse_html(html)
        assert doc is not None

    @pytest.mark.fast
    def test_table_with_missing_tr(self):
        """Table with missing <tr> tags."""
        html = """
        <html><body>
        <table>
            <td>Cell 1</td>
            <td>Cell 2</td>
        </table>
        </body></html>
        """
        doc = parse_html(html)
        assert doc is not None
        # Parser should handle gracefully


class TestExtremeStructures:
    """Test extreme HTML structures."""

    @pytest.mark.fast
    def test_deeply_nested_divs(self):
        """Very deep nesting should work."""
        # Create 100-level deep nesting
        html = "<html><body>" + "<div>" * 100 + "Content" + "</div>" * 100 + "</body></html>"
        doc = parse_html(html)
        assert doc is not None
        assert "Content" in doc.text()

    @pytest.mark.fast
    def test_table_with_large_colspan(self):
        """Table with very large colspan."""
        html = """
        <html><body>
        <table>
            <tr><td colspan="1000">Wide header</td></tr>
            <tr><td>A</td><td>B</td><td>C</td></tr>
        </table>
        </body></html>
        """
        doc = parse_html(html)
        assert doc is not None
        assert len(doc.tables) == 1

    @pytest.mark.fast
    def test_table_with_large_rowspan(self):
        """Table with very large rowspan."""
        html = """
        <html><body>
        <table>
            <tr><td rowspan="1000">Tall cell</td><td>Data</td></tr>
            <tr><td>More</td></tr>
        </table>
        </body></html>
        """
        doc = parse_html(html)
        assert doc is not None
        assert len(doc.tables) == 1

    @pytest.mark.fast
    def test_table_with_extreme_dimensions(self):
        """Table with extreme colspan and rowspan."""
        html = """
        <html><body>
        <table>
            <tr><td colspan="500" rowspan="500">Huge cell</td></tr>
        </table>
        </body></html>
        """
        doc = parse_html(html)
        assert doc is not None
        assert len(doc.tables) == 1

    @pytest.mark.fast
    def test_many_tables(self):
        """Document with many tables."""
        tables_html = "<table><tr><td>Table</td></tr></table>" * 1000
        html = f"<html><body>{tables_html}</body></html>"
        doc = parse_html(html)
        assert doc is not None
        assert len(doc.tables) == 1000


class TestUnicodeAndSpecialCharacters:
    """Test Unicode and special character handling."""

    @pytest.mark.fast
    def test_unicode_content(self):
        """Unicode content should be preserved."""
        html = """
        <html><body>
        <p>Café résumé naïve</p>
        <p>日本語 中文 한국어</p>
        <p>العربية עברית</p>
        <p>Emoji: 🚀 📊 ✅</p>
        </body></html>
        """
        doc = parse_html(html)
        text = doc.text()

        assert "Café" in text
        assert "résumé" in text
        assert "日本語" in text
        assert "中文" in text
        assert "العربية" in text
        assert "🚀" in text

    @pytest.mark.fast
    def test_special_html_entities(self):
        """HTML entities should be decoded."""
        html = """
        <html><body>
        <p>&lt;tag&gt; &amp; &quot;quoted&quot; &apos;text&apos;</p>
        <p>&copy; &reg; &trade;</p>
        </body></html>
        """
        doc = parse_html(html)
        text = doc.text()
        # Should contain decoded entities
        assert doc is not None

    @pytest.mark.fast
    def test_special_characters_in_tables(self):
        """Special characters in table cells."""
        html = """
        <html><body>
        <table>
            <tr><td>$1,234.56</td><td>(negative)</td><td>100%</td></tr>
            <tr><td>€5,678</td><td>—</td><td>N/A</td></tr>
            <tr><td>≥</td><td>≤</td><td>≠</td></tr>
        </table>
        </body></html>
        """
        doc = parse_html(html)
        assert len(doc.tables) == 1
        table = doc.tables[0]
        table_str = str(table)
        assert "$1,234.56" in table_str


class TestInvalidInputs:
    """Test handling of invalid inputs."""

    @pytest.mark.fast
    def test_none_input(self):
        """None input should raise error."""
        with pytest.raises(TypeError):
            parse_html(None)

    def test_non_string_input(self):
        """Non-string input should raise error."""
        with pytest.raises(TypeError, match="HTML must be string or bytes"):
            parse_html(12345)

    def test_binary_input_accepted(self):
        """Binary input should be accepted and decoded."""
        html_bytes = b"<html><body>Binary input test</body></html>"
        doc = parse_html(html_bytes)
        assert doc is not None
        assert "Binary input test" in doc.text()


class TestComplexRealWorldScenarios:
    """Test complex real-world scenarios."""

    def test_mixed_table_structure(self):
        """Table with mixed header/data patterns."""
        html = """
        <html><body>
        <table>
            <tr><th>Header 1</th><th>Header 2</th></tr>
            <tr><td>Data 1</td><td>Data 2</td></tr>
            <tr><th>Sub-header</th><td>More data</td></tr>
            <tr><td>Data 3</td><td>Data 4</td></tr>
        </table>
        </body></html>
        """
        doc = parse_html(html)
        assert len(doc.tables) == 1

    def test_nested_tables(self):
        """Tables nested inside tables."""
        html = """
        <html><body>
        <table>
            <tr>
                <td>Outer</td>
                <td>
                    <table>
                        <tr><td>Inner</td></tr>
                    </table>
                </td>
            </tr>
        </table>
        </body></html>
        """
        doc = parse_html(html)
        assert doc is not None
        # Should extract both tables

    def test_table_with_complex_formatting(self):
        """Table with complex inline formatting."""
        html = """
        <html><body>
        <table>
            <tr>
                <td><b>Bold</b> <i>Italic</i> <u>Underline</u></td>
                <td><span style="color:red">Red</span> text</td>
            </tr>
        </table>
        </body></html>
        """
        doc = parse_html(html)
        assert len(doc.tables) == 1
        # Text should be extracted from formatted cells

    def test_table_with_links_and_images(self):
        """Table with links and images."""
        html = """
        <html><body>
        <table>
            <tr>
                <td><a href="url">Link text</a></td>
                <td><img src="image.jpg" alt="Image"/></td>
            </tr>
        </table>
        </body></html>
        """
        doc = parse_html(html)
        assert len(doc.tables) == 1

    def test_non_standard_section_formatting(self):
        """Non-standard section headers."""
        html = """
        <html><body>
        <h1>ITEM 1 BUSINESS</h1>
        <p>Content...</p>
        <h1>Item 7. MD&A</h1>
        <p>More content...</p>
        <h2>Item 8 - Financial Statements and Data</h2>
        <p>Financial content...</p>
        </body></html>
        """
        doc = parse_html(html)
        sections = doc.sections
        # Should detect sections with various formats

    def test_combined_items(self):
        """Combined Items (e.g., Items 10, 13, 14)."""
        html = """
        <html><body>
        <h1>Items 10, 13 and 14. Directors, Executive Officers and Corporate Governance</h1>
        <p>Combined content...</p>
        </body></html>
        """
        doc = parse_html(html)
        sections = doc.sections
        # Should handle combined items

    def test_xbrl_inline_facts(self):
        """Document with inline XBRL facts."""
        html = """
        <html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL">
        <body>
        <p>Revenue: <ix:nonfraction name="us-gaap:Revenue" unitRef="usd">1000000</ix:nonfraction></p>
        <p>Shares: <ix:nonfraction name="us-gaap:SharesOutstanding" unitRef="shares">500000</ix:nonfraction></p>
        </body>
        </html>
        """
        doc = parse_html(html)
        assert doc is not None
        # Should extract XBRL facts

    def test_very_long_text_cell(self):
        """Table cell with very long text."""
        long_text = "This is a very long narrative text. " * 1000
        html = f"""
        <html><body>
        <table>
            <tr><td>Short</td><td>{long_text}</td></tr>
        </table>
        </body></html>
        """
        doc = parse_html(html)
        assert len(doc.tables) == 1

    def test_whitespace_preservation(self):
        """Important whitespace should be handled correctly."""
        html = """
        <html><body>
        <table>
            <tr><td>$ </td><td> 1,234</td></tr>
            <tr><td>( </td><td> 5,678 )</td></tr>
        </table>
        </body></html>
        """
        doc = parse_html(html)
        assert len(doc.tables) == 1
        # Currency symbols and parentheses should be near values


class TestPerformanceBoundaries:
    """Test performance boundaries and limits."""

    def test_document_size_limit(self):
        """Document approaching size limit."""
        # Create ~10MB document
        large_text = "x" * (10 * 1024 * 1024)
        html = f"<html><body>{large_text}</body></html>"

        doc = parse_html(html)
        assert doc is not None

    def test_many_small_elements(self):
        """Document with many small elements."""
        # Create 10,000 paragraphs
        paragraphs = "<p>Text</p>" * 10000
        html = f"<html><body>{paragraphs}</body></html>"

        doc = parse_html(html)
        assert doc is not None

    def test_complex_nested_structure(self):
        """Complex nested structure with multiple element types."""
        html = """
        <html><body>
        """ + "\n".join([
            f"<div><table><tr><td><p>Content {i}</p></td></tr></table></div>"
            for i in range(1000)
        ]) + """
        </body></html>
        """

        doc = parse_html(html)
        assert doc is not None
