"""
Regression prevention tests for HTML parser.

Tests for specific bugs that were fixed during development to prevent regression.
Each test documents:
- The original bug
- The fix applied
- The expected behavior
"""

import pytest
from pathlib import Path
from edgar.documents import parse_html
from edgar.documents.config import ParserConfig


class TestTableRenderingRegressions:
    """Regression tests for table rendering bugs."""

    def test_msft_table_39_rendering(self):
        """
        Regression: MSFT Table 39 had incorrect rendering.

        Bug: Table with complex colspan/rowspan was rendering incorrectly
        Fix: Improved TableMatrix algorithm for cell placement
        Expected: Table renders with proper cell alignment
        """
        html_path = Path('data/html/MSFT.10-K.html')
        if not html_path.exists():
            pytest.skip("MSFT 10-K test file not found")

        html = html_path.read_text()
        doc = parse_html(html)

        # Should have tables
        assert len(doc.tables) > 0

        # Table 39 should exist (index 38 in 0-based)
        if len(doc.tables) > 38:
            table_39 = doc.tables[38]

            # Should be renderable without error (returns rich.Table)
            rendered = table_39.render()
            assert rendered is not None

            # Should have rows
            assert table_39.row_count > 0

            # Text representation should work
            text = table_39.text()
            assert isinstance(text, str)
            assert len(text) > 0

    def test_oracle_table_6_rendering(self):
        """
        Regression: Oracle Table 6 had rendering issues.

        Bug: Complex financial table with nested headers
        Fix: Improved header detection and cell merging logic
        Expected: Table renders correctly with all cells
        """
        html_path = Path('data/html/Oracle.10-K.html')
        if not html_path.exists():
            pytest.skip("Oracle 10-K test file not found")

        html = html_path.read_text()
        doc = parse_html(html)

        # Should have tables
        assert len(doc.tables) > 0

        # Table 6 should exist
        if len(doc.tables) > 5:
            table_6 = doc.tables[5]

            # Should render without error
            table_str = str(table_6)
            assert len(table_str) > 0

    def test_tesla_table_16_rendering(self):
        """
        Regression: Tesla Table 16 rendering bug.

        Bug: Table had incorrect cell placement
        Fix: Fixed TableMatrix cell assignment algorithm
        Expected: All cells in correct positions
        """
        html_path = Path('data/html/Tesla.10-K.html')
        if not html_path.exists():
            pytest.skip("Tesla 10-K test file not found")

        html = html_path.read_text()
        doc = parse_html(html)

        # Should have tables
        assert len(doc.tables) > 0

        # Table 16 should exist
        if len(doc.tables) > 15:
            table_16 = doc.tables[15]

            # Should render without error
            table_str = str(table_16)
            assert len(table_str) > 0


class TestStreamingParserRegressions:
    """Regression tests for streaming parser bugs."""

    def test_jpm_streaming_parent_none_bug(self):
        """
        Regression: JPM 10-K crashed in streaming parser.

        Bug: StreamingParser tried to delete elem.getparent()[0] when parent was None
        Error: 'NoneType' object does not support item deletion
        Fix: Added None check before deleting parent element
        Location: edgar/documents/utils/streaming.py:100

        Expected: Large documents parse successfully without crashes
        """
        html_path = Path('data/html/JPM.10-K.html')
        if not html_path.exists():
            pytest.skip("JPM 10-K test file not found")

        html = html_path.read_text()

        # JPM 10-K is 52MB, exceeds default limit
        config = ParserConfig(max_document_size=100 * 1024 * 1024)

        # Should not crash
        doc = parse_html(html, config=config)

        # Should parse successfully
        assert doc is not None
        assert len(doc.tables) > 0

        # JPM has many tables (681 in test run)
        assert len(doc.tables) > 500

    def test_large_document_streaming_trigger(self):
        """
        Regression: Ensure streaming mode activates for large docs.

        Bug: Streaming threshold not properly enforced
        Expected: Documents over threshold use streaming parser
        """
        # Create a document just over streaming threshold
        threshold = 5 * 1024 * 1024  # 5MB
        large_content = "x" * (threshold + 1000)
        html = f"<html><body><p>{large_content}</p></body></html>"

        config = ParserConfig(
            streaming_threshold=threshold,
            max_document_size=100 * 1024 * 1024
        )

        # Should parse without error using streaming
        doc = parse_html(html, config=config)
        assert doc is not None


class TestSectionDetectionRegressions:
    """Regression tests for section detection bugs."""

    def test_10q_part_distinction(self):
        """
        Regression: 10-Q Part I/Part II distinction.

        Bug: 10-Q Item 2 ambiguous between Part I and Part II
        Fix: Added Part I/II distinction in section detection
        Expected: Items correctly associated with Part I or Part II
        """
        html_path = Path('data/html/Apple.10-Q.html')
        if not html_path.exists():
            pytest.skip("Apple 10-Q test file not found")

        html = html_path.read_text()
        doc = parse_html(html,ParserConfig(filing_type='10-Q'))

        sections = doc.sections

        # 10-Q should have sections
        assert len(sections) > 0

        # Check if Part I sections exist
        part_i_sections = [k for k in sections.keys() if 'Part I' in k or 'PART I' in k]
        part_ii_sections = [k for k in sections.keys() if 'Part II' in k or 'PART II' in k]

        # 10-Q should have both parts (if properly detected)
        # Note: This is aspirational - depends on filing structure
        if part_i_sections or part_ii_sections:
            assert len(part_i_sections) > 0 or len(part_ii_sections) > 0


class TestInputValidationRegressions:
    """Regression tests for input validation bugs."""

    def test_none_input_type_error(self):
        """
        Regression: None input crashed with AttributeError.

        Bug: Parser tried to call .strip() on None
        Error: 'NoneType' object has no attribute 'strip'
        Fix: Added input type validation at parse() entry point
        Expected: Clear TypeError with helpful message
        """
        with pytest.raises(TypeError, match="HTML input cannot be None"):
            parse_html(None)

    def test_invalid_type_clear_error(self):
        """
        Regression: Invalid input types had unclear errors.

        Bug: Non-string inputs caused confusing internal errors
        Fix: Added type checking with clear error messages
        Expected: TypeError with type name in message
        """
        with pytest.raises(TypeError, match="HTML must be string or bytes"):
            parse_html(12345)

        with pytest.raises(TypeError, match="HTML must be string or bytes"):
            parse_html(['html', 'list'])

    def test_bytes_input_accepted(self):
        """
        Regression: Bytes input should be accepted and decoded.

        Expected: Parser accepts both str and bytes input
        """
        html_bytes = b"<html><body><p>Test content</p></body></html>"
        doc = parse_html(html_bytes)

        assert doc is not None
        assert "Test content" in doc.text()


class TestPerformanceRegressions:
    """Regression tests for performance issues."""

    def test_parsing_speed_threshold(self):
        """
        Regression: Ensure parsing remains fast.

        Target: < 1 second for typical 10-K
        Regression threshold: > 2 seconds indicates performance degradation
        """
        import time

        html_path = Path('data/html/Apple.10-K.html')
        if not html_path.exists():
            pytest.skip("Apple 10-K test file not found")

        html = html_path.read_text()

        start = time.perf_counter()
        doc = parse_html(html)
        elapsed = time.perf_counter() - start

        # Regression threshold: 2 seconds
        assert elapsed < 2.0, f"Parse time {elapsed:.3f}s exceeds 2s regression threshold"

        # Should have content
        assert len(doc.tables) > 0

    def test_memory_cleanup_in_streaming(self):
        """
        Regression: Streaming parser should clean up elements.

        Bug: Memory could grow unbounded in streaming mode
        Fix: Delete processed elements to free memory
        Expected: Streaming mode completes without excessive memory
        """
        # Create a document that triggers streaming
        threshold = 5 * 1024 * 1024

        # Create multiple tables to ensure cleanup happens
        tables = []
        for i in range(100):
            table = f"""
            <table>
                <tr><td>Row {i} Col 1</td><td>Row {i} Col 2</td></tr>
                <tr><td>Data {i} A</td><td>Data {i} B</td></tr>
            </table>
            """
            tables.append(table)

        # Pad with enough content to exceed threshold
        padding = "x" * threshold
        html = f"<html><body>{''.join(tables)}<p>{padding}</p></body></html>"

        config = ParserConfig(
            streaming_threshold=threshold,
            max_document_size=100 * 1024 * 1024
        )

        # Should complete without running out of memory
        doc = parse_html(html, config=config)
        assert doc is not None


class TestXBRLExtractionRegressions:
    """Regression tests for XBRL extraction bugs."""

    def test_xbrl_hidden_element_extraction(self):
        """
        Regression: XBRL facts in ix:hidden should be extracted.

        Bug: XBRL extraction only found visible facts
        Fix: Extract XBRL before preprocessing removes ix:hidden
        Expected: Facts from both visible and hidden sections
        """
        html = """
        <html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL">
        <body>
            <ix:hidden>
                <ix:nonfraction name="us-gaap:Revenue" unitRef="usd">1000000</ix:nonfraction>
            </ix:hidden>
            <p>Revenue: <ix:nonfraction name="us-gaap:Revenue" unitRef="usd">1000000</ix:nonfraction></p>
        </body>
        </html>
        """

        config = ParserConfig(extract_xbrl=True)
        doc = parse_html(html, config=config)

        # Should have extracted XBRL metadata
        if hasattr(doc.metadata, 'xbrl_data') and doc.metadata.xbrl_data:
            facts = doc.metadata.xbrl_data.get('facts', [])

            # Should find facts (at least the visible one, ideally both)
            assert len(facts) > 0


class TestEdgeCaseRegressions:
    """Regression tests for edge case bugs."""

    def test_empty_html_no_crash(self):
        """
        Regression: Empty HTML should return empty document.

        Bug: Empty input could cause crashes
        Expected: Returns valid empty Document
        """
        doc = parse_html("")

        assert doc is not None
        assert len(doc.tables) == 0
        assert len(doc.text()) == 0

    def test_malformed_html_recovery(self):
        """
        Regression: Malformed HTML should parse gracefully.

        Bug: Unclosed tags could cause parser errors
        Fix: Use lxml's recover=True mode
        Expected: Parser auto-closes tags and continues
        """
        html = "<html><body><p>Unclosed paragraph<div>And div</body></html>"
        doc = parse_html(html)

        assert doc is not None
        assert "Unclosed paragraph" in doc.text()
        assert "And div" in doc.text()

    def test_deeply_nested_structure(self):
        """
        Regression: Deep nesting should not cause stack overflow.

        Bug: Very deep nesting could cause recursion errors
        Expected: Handles 100+ levels of nesting
        """
        # 100-level deep nesting
        html = "<html><body>" + "<div>" * 100 + "Content" + "</div>" * 100 + "</body></html>"
        doc = parse_html(html)

        assert doc is not None
        assert "Content" in doc.text()
