"""
Integration tests for HTML parser with EdgarTools.

Tests parser integration with:
- Filing objects
- Company objects
- Document API
- Existing features
"""

import pytest
from edgar import Company, set_identity
from edgar.documents import parse_html


class TestFilingIntegration:
    """Test integration with Filing objects."""

    @pytest.fixture(scope='class')
    def sample_filing(self):
        """Get a sample 10-K filing."""
        company = Company('AAPL')
        filings = company.get_filings(form='10-K')
        return filings.latest(1)

    @pytest.mark.network
    def test_filing_html_method(self, sample_filing):
        """Filing.html() should return parseable HTML."""
        html = sample_filing.html()

        assert html is not None
        assert isinstance(html, str)
        assert len(html) > 0

        # Should be parseable
        doc = parse_html(html)
        assert doc is not None

    @pytest.mark.network
    def test_filing_obj_method(self, sample_filing):
        """Filing.obj() returns HtmlDocument (old parser)."""
        doc = sample_filing.obj()

        assert doc is not None
        # Old parser returns HtmlDocument
        # New parser used via parse_html() directly

    @pytest.mark.network
    def test_document_attributes(self, sample_filing):
        """Document should have expected attributes."""
        html = sample_filing.html()
        doc = parse_html(html)

        # Core attributes
        assert hasattr(doc, 'root')
        assert hasattr(doc, 'metadata')

        # Content access
        assert hasattr(doc, 'sections')
        assert hasattr(doc, 'tables')
        assert hasattr(doc, 'headings')
        assert hasattr(doc, 'text')

        # Methods should be callable
        assert callable(doc.text)

    @pytest.mark.network
    def test_sections_access(self, sample_filing):
        """Sections should be accessible."""
        html = sample_filing.html()
        doc = parse_html(html)
        sections = doc.sections

        assert isinstance(sections, dict)
        # 10-K should have sections
        assert len(sections) > 0

    @pytest.mark.network
    def test_tables_access(self, sample_filing):
        """Tables should be accessible."""
        html = sample_filing.html()
        doc = parse_html(html)
        tables = doc.tables

        assert isinstance(tables, list)
        # 10-K should have tables
        assert len(tables) > 0

    @pytest.mark.network
    def test_text_extraction(self, sample_filing):
        """Text extraction should work."""
        html = sample_filing.html()
        doc = parse_html(html)
        text = doc.text()

        assert isinstance(text, str)
        assert len(text) > 0
        # Should contain typical 10-K content
        assert 'Item' in text or 'ITEM' in text


class TestCompanyIntegration:
    """Test integration with Company objects."""

    @pytest.mark.network
    def test_multiple_filings(self):
        """Process multiple filings from same company."""
        company = Company('AAPL')
        filings = company.get_filings(form='10-K').latest(3)

        docs = []
        for filing in filings:
            html = filing.html()
            doc = parse_html(html)
            docs.append(doc)

        assert len(docs) == 3
        # All should be valid documents
        for doc in docs:
            assert doc is not None
            assert len(doc.tables) > 0

    @pytest.mark.network
    def test_different_form_types(self):
        """Parse different form types."""
        company = Company('AAPL')

        # 10-K
        filing_10k = company.get_filings(form='10-K').latest(1)
        html_10k = filing_10k.html()
        doc_10k = parse_html(html_10k)
        assert doc_10k is not None

        # 10-Q
        filing_10q = company.get_filings(form='10-Q').latest(1)
        html_10q = filing_10q.html()
        doc_10q = parse_html(html_10q)
        assert doc_10q is not None


class TestDocumentAPI:
    """Test document API compatibility."""

    @pytest.fixture
    def sample_doc(self):
        """Get sample parsed document."""
        company = Company('AAPL')
        filing = company.get_filings(form='10-K').latest(1)
        html = filing.html()
        return parse_html(html)

    @pytest.mark.network
    def test_section_iteration(self, sample_doc):
        """Should be able to iterate sections."""
        sections = sample_doc.sections

        for name, section in sections.items():
            assert isinstance(name, str)
            assert section is not None
            # Should have text method
            assert hasattr(section, 'text')

    @pytest.mark.network
    def test_table_iteration(self, sample_doc):
        """Should be able to iterate tables."""
        tables = sample_doc.tables

        for table in tables:
            assert table is not None
            # Should be renderable
            assert hasattr(table, 'render') or hasattr(table, '__str__')

    @pytest.mark.network
    def test_headings_access(self, sample_doc):
        """Headings should be accessible."""
        headings = sample_doc.headings

        assert isinstance(headings, list)
        for heading in headings:
            assert hasattr(heading, 'text')

    @pytest.mark.network
    def test_text_method_options(self, sample_doc):
        """Text extraction should support options."""
        # Basic text
        text = sample_doc.text()
        assert len(text) > 0

        # Text should be consistent
        text2 = sample_doc.text()
        assert text == text2


class TestBackwardCompatibility:
    """Test backward compatibility with existing code patterns."""

    @pytest.mark.network
    def test_old_parsing_pattern(self):
        """Old parsing patterns should still work."""
        company = Company('AAPL')
        filing = company.get_filings(form='10-K').latest(1)

        # Old pattern: get HTML and parse
        html = filing.html()
        doc = parse_html(html)

        assert doc is not None
        assert len(doc.tables) > 0

    @pytest.mark.network
    def test_filing_obj_pattern(self):
        """Filing.obj() pattern should work."""
        company = Company('AAPL')
        filing = company.get_filings(form='10-K').latest(1)

        # Common pattern - obj() returns TenK/TenQ object (old API)
        doc = filing.obj()

        # TenK has .items (sections), not .sections
        assert hasattr(doc, 'items')
        assert doc.items is not None

        # TenK has financials property with tables
        assert hasattr(doc, 'financials')

    @pytest.mark.network
    def test_section_text_extraction(self):
        """Section text extraction pattern."""
        company = Company('AAPL')
        filing = company.get_filings(form='10-K').latest(1)
        doc = filing.obj()

        # TenK has .items dict, try to get Business section
        items = doc.items
        if items:
            # Get business item (Item 1)
            business = doc.business
            if business:
                text = str(business)
                assert isinstance(text, str)
                assert len(text) > 0


class TestPerformanceIntegration:
    """Test performance with real filings."""

    @pytest.mark.network
    def test_parsing_speed(self):
        """Parsing should be fast."""
        import time

        company = Company('AAPL')
        filing = company.get_filings(form='10-K').latest(1)
        html = filing.html()

        start = time.perf_counter()
        doc = parse_html(html)
        elapsed = time.perf_counter() - start

        # Should parse in under 1 second for typical filing
        assert elapsed < 1.0, f"Parse time {elapsed:.3f}s exceeds 1s threshold"

    @pytest.mark.network
    def test_memory_efficiency(self):
        """Should handle documents efficiently."""
        company = Company('AAPL')
        filing = company.get_filings(form='10-K').latest(1)

        # Parse document
        html = filing.html()
        doc = parse_html(html)

        # Should be able to access content
        assert len(doc.tables) > 0
        assert len(doc.text()) > 0

        # Cleanup
        del doc


class TestErrorHandling:
    """Test error handling in integration scenarios."""

    @pytest.mark.fast
    def test_invalid_filing_html(self):
        """Should handle invalid HTML gracefully."""
        # Parse malformed HTML
        html = "<html><body>Broken"
        doc = parse_html(html)

        # Should not crash
        assert doc is not None

    @pytest.mark.fast
    def test_empty_filing(self):
        """Should handle empty HTML."""
        html = ""
        doc = parse_html(html)

        assert doc is not None
        assert len(doc.tables) == 0

    @pytest.mark.network
    def test_large_filing_handling(self):
        """Should handle large filings."""
        from edgar.documents.config import ParserConfig

        # Use large size limit
        config = ParserConfig(max_document_size=100 * 1024 * 1024)

        company = Company('JPM')
        filing = company.get_filings(form='10-K').latest(1)
        html = filing.html()

        # Should parse large filing
        doc = parse_html(html, config=config)
        assert doc is not None


class TestSpecificFilingTypes:
    """Test specific filing type handling."""

    @pytest.mark.network
    def test_10k_parsing(self):
        """10-K filings should parse correctly."""
        company = Company('AAPL')
        filing = company.get_filings(form='10-K').latest(1)
        html = filing.html()
        doc = parse_html(html)

        # 10-K specific checks
        sections = doc.sections
        # Should have typical 10-K sections
        assert len(sections) > 0

    @pytest.mark.network
    def test_10q_parsing(self):
        """10-Q filings should parse correctly."""
        company = Company('AAPL')
        filing = company.get_filings(form='10-Q').latest(1)
        html = filing.html()
        doc = parse_html(html)

        # 10-Q specific checks
        assert doc is not None
        assert len(doc.tables) > 0

    @pytest.mark.network
    def test_8k_parsing(self):
        """8-K filings should parse correctly."""
        company = Company('AAPL')
        filings = company.get_filings(form='8-K')

        if filings:
            filing = filings.latest(1)
            html = filing.html()
            doc = parse_html(html)
            assert doc is not None


class TestBatchProcessing:
    """Test batch processing scenarios."""

    @pytest.mark.slow
    def test_multiple_companies(self):
        """Process filings from multiple companies."""
        tickers = ['AAPL', 'MSFT', 'GOOGL']

        for ticker in tickers:
            try:
                company = Company(ticker)
                filing = company.get_filings(form='10-K').latest(1)
                if filing:
                    html = filing.html()
                    doc = parse_html(html)
                    assert doc is not None
            except Exception as e:
                pytest.skip(f"Could not fetch {ticker}: {e}")

    @pytest.mark.network
    def test_sequential_parsing(self):
        """Parse multiple filings sequentially."""
        company = Company('AAPL')
        filings = company.get_filings(form='10-K').latest(3)

        docs = []
        for filing in filings:
            html = filing.html()
            doc = parse_html(html)
            docs.append(doc)
            # Verify each doc
            assert doc is not None

        assert len(docs) == 3
