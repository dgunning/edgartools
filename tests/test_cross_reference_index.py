"""
Tests for Cross Reference Index parser.
"""

import pytest
from edgar.documents.cross_reference_index import (
    CrossReferenceIndex,
    PageRange,
    IndexEntry,
    detect_cross_reference_index,
    parse_cross_reference_index
)


class TestPageRange:
    """Test PageRange parsing."""

    def test_single_page(self):
        """Test parsing single page number."""
        ranges = PageRange.parse("25")
        assert len(ranges) == 1
        assert ranges[0].start == 25
        assert ranges[0].end == 25
        assert str(ranges[0]) == "25"

    def test_page_range(self):
        """Test parsing page range."""
        ranges = PageRange.parse("26-33")
        assert len(ranges) == 1
        assert ranges[0].start == 26
        assert ranges[0].end == 33
        assert str(ranges[0]) == "26-33"

    def test_multiple_ranges(self):
        """Test parsing multiple page ranges."""
        ranges = PageRange.parse("4-7, 9-11, 74-75")
        assert len(ranges) == 3

        assert ranges[0].start == 4
        assert ranges[0].end == 7

        assert ranges[1].start == 9
        assert ranges[1].end == 11

        assert ranges[2].start == 74
        assert ranges[2].end == 75

    def test_not_applicable(self):
        """Test parsing 'Not applicable'."""
        ranges = PageRange.parse("Not applicable")
        assert len(ranges) == 0

    def test_empty_string(self):
        """Test parsing empty string."""
        ranges = PageRange.parse("")
        assert len(ranges) == 0


class TestIndexEntry:
    """Test IndexEntry dataclass."""

    def test_item_id(self):
        """Test item_id property."""
        entry = IndexEntry(
            item_number="1A",
            item_title="Risk Factors",
            pages=[PageRange(start=26, end=33)]
        )
        assert entry.item_id == "1A"

    def test_full_item_name(self):
        """Test full_item_name property."""
        entry = IndexEntry(
            item_number="1A",
            item_title="Risk Factors",
            pages=[PageRange(start=26, end=33)]
        )
        assert entry.full_item_name == "Item 1A. Risk Factors"


class TestCrossReferenceIndex:
    """Test CrossReferenceIndex parser."""

    @pytest.fixture
    def ge_sample_html(self):
        """Load GE Cross Reference Index sample."""
        import os
        sample_path = os.path.join(
            os.path.dirname(__file__),
            'data/cross_reference_index/ge_10k_cross_reference_sample.html'
        )
        if os.path.exists(sample_path):
            with open(sample_path, 'r') as f:
                return f.read()
        return None

    @pytest.fixture
    def ge_full_html(self):
        """Get full GE 10-K HTML (network test)."""
        pytest.importorskip("edgar")
        from edgar import Company

        company = Company('GE')
        filing = company.get_filings(form='10-K').latest()
        return filing.html()

    def test_has_index_with_sample(self, ge_sample_html):
        """Test detecting Cross Reference Index in sample."""
        if ge_sample_html is None:
            pytest.skip("Sample HTML not available")

        # Sample is just the table, might not have the header
        # This test verifies the basic structure
        index = CrossReferenceIndex(ge_sample_html)
        # Should not crash
        assert index is not None

    @pytest.mark.network
    def test_has_index_full_filing(self, ge_full_html):
        """Test detecting Cross Reference Index in full GE filing."""
        index = CrossReferenceIndex(ge_full_html)
        assert index.has_index() is True

    @pytest.mark.network
    def test_parse_full_filing(self, ge_full_html):
        """Test parsing Cross Reference Index from full GE filing."""
        index = CrossReferenceIndex(ge_full_html)
        entries = index.parse()

        # Should have multiple entries
        assert len(entries) > 0

        # Check specific items
        if '1' in entries:
            item1 = entries['1']
            assert item1.item_title == 'Business'
            assert len(item1.pages) > 0

        if '1A' in entries:
            item1a = entries['1A']
            assert item1a.item_title == 'Risk Factors'
            assert len(item1a.pages) > 0
            # GE has "26-33" for Risk Factors
            assert any(p.start == 26 and p.end == 33 for p in item1a.pages)

    @pytest.mark.network
    def test_get_item(self, ge_full_html):
        """Test getting specific item."""
        index = CrossReferenceIndex(ge_full_html)
        index.parse()

        item1a = index.get_item('1A')
        assert item1a is not None
        assert item1a.item_title == 'Risk Factors'

        # Non-existent item
        item_none = index.get_item('99')
        assert item_none is None

    @pytest.mark.network
    def test_get_page_ranges(self, ge_full_html):
        """Test getting page ranges for item."""
        index = CrossReferenceIndex(ge_full_html)

        ranges = index.get_page_ranges('1A')
        assert len(ranges) > 0
        assert any(p.start == 26 and p.end == 33 for p in ranges)

        # Non-existent item
        ranges_empty = index.get_page_ranges('99')
        assert len(ranges_empty) == 0

    @pytest.mark.network
    def test_find_page_breaks(self, ge_full_html):
        """Test finding page breaks in HTML."""
        index = CrossReferenceIndex(ge_full_html)
        breaks = index.find_page_breaks()

        # Should have multiple page breaks
        assert len(breaks) > 10
        # First break should be at position 0
        assert breaks[0] == 0
        # Breaks should be sorted
        assert breaks == sorted(breaks)

    @pytest.mark.network
    def test_extract_content_by_page_range(self, ge_full_html):
        """Test extracting content by page range."""
        index = CrossReferenceIndex(ge_full_html)

        # Extract page 26
        content = index.extract_content_by_page_range(PageRange(start=26, end=26))

        if content:
            # Should contain some content
            assert len(content) > 0
            # Might contain risk-related keywords (not guaranteed)

    @pytest.mark.network
    def test_extract_item_content(self, ge_full_html):
        """Test extracting item content."""
        index = CrossReferenceIndex(ge_full_html)

        # Extract Risk Factors (Item 1A)
        content = index.extract_item_content('1A')

        if content:
            # Should have substantial content
            assert len(content) > 1000
            # Might contain risk-related keywords


class TestConvenienceFunctions:
    """Test convenience functions."""

    @pytest.mark.network
    def test_detect_cross_reference_index(self):
        """Test detect_cross_reference_index function."""
        from edgar import Company

        company = Company('GE')
        filing = company.get_filings(form='10-K').latest()
        html = filing.html()

        assert detect_cross_reference_index(html) is True

    @pytest.mark.network
    def test_parse_cross_reference_index(self):
        """Test parse_cross_reference_index function."""
        from edgar import Company

        company = Company('GE')
        filing = company.get_filings(form='10-K').latest()
        html = filing.html()

        entries = parse_cross_reference_index(html)

        assert len(entries) > 0
        assert '1A' in entries
        assert entries['1A'].item_title == 'Risk Factors'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
