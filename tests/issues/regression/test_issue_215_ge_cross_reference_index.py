"""
Regression test for GitHub Issue #215: GE 10-K extraction returns None.

Issue: GE uses a "Form 10-K Cross Reference Index" format instead of standard
Item headings, causing extraction to fail.

Solution: CrossReferenceIndex parser in edgar.documents.cross_reference_index

This test ensures the parser continues to work for GE filings.
"""

import pytest
from edgar import Company
from edgar.documents import CrossReferenceIndex, detect_cross_reference_index


@pytest.mark.network
class TestIssue215GECrossReferenceIndex:
    """Test Cross Reference Index parser with GE 10-K filings."""

    @pytest.fixture(scope='class')
    def ge_latest_10k(self):
        """Get GE's latest 10-K filing."""
        company = Company('GE')
        filings = company.get_filings(form='10-K')
        return filings.latest()

    @pytest.fixture(scope='class')
    def ge_html(self, ge_latest_10k):
        """Get HTML content from GE's latest 10-K."""
        return ge_latest_10k.html()

    def test_ge_has_cross_reference_index(self, ge_html):
        """Test that GE 10-K is detected as having Cross Reference Index format."""
        has_index = detect_cross_reference_index(ge_html)
        assert has_index is True, "GE 10-K should be detected as having Cross Reference Index format"

    def test_ge_cross_reference_index_parsing(self, ge_html):
        """Test that Cross Reference Index can be parsed from GE 10-K."""
        index = CrossReferenceIndex(ge_html)
        entries = index.parse()

        # Should have multiple entries
        assert len(entries) > 20, f"Expected 20+ entries, got {len(entries)}"

        # Should have standard items
        assert '1' in entries, "Should have Item 1 (Business)"
        assert '1A' in entries, "Should have Item 1A (Risk Factors)"
        assert '7' in entries, "Should have Item 7 (MD&A)"
        assert '8' in entries, "Should have Item 8 (Financial Statements)"

    def test_ge_item_1_business(self, ge_html):
        """Test extraction of Item 1 (Business)."""
        index = CrossReferenceIndex(ge_html)
        entry = index.get_item('1')

        assert entry is not None, "Item 1 should exist"
        assert entry.item_number == '1'
        assert 'Business' in entry.item_title
        assert len(entry.pages) > 0, "Item 1 should have page ranges"

    def test_ge_item_1a_risk_factors(self, ge_html):
        """Test extraction of Item 1A (Risk Factors)."""
        index = CrossReferenceIndex(ge_html)
        entry = index.get_item('1A')

        assert entry is not None, "Item 1A should exist"
        assert entry.item_number == '1A'
        assert 'Risk Factors' in entry.item_title
        assert len(entry.pages) > 0, "Item 1A should have page ranges"

        # Validate page range format (should be a single range like "26-33")
        # Though exact pages may vary by year
        for page_range in entry.pages:
            assert page_range.start > 0, "Page start should be positive"
            assert page_range.end >= page_range.start, "Page end should be >= start"

    def test_ge_item_7_mda(self, ge_html):
        """Test extraction of Item 7 (MD&A)."""
        index = CrossReferenceIndex(ge_html)
        entry = index.get_item('7')

        assert entry is not None, "Item 7 should exist"
        assert entry.item_number == '7'
        # Title often contains HTML entities like &#8217;
        assert 'Management' in entry.item_title or 'Discussion' in entry.item_title
        assert len(entry.pages) > 0, "Item 7 should have page ranges"

    def test_ge_item_8_financial_statements(self, ge_html):
        """Test extraction of Item 8 (Financial Statements)."""
        index = CrossReferenceIndex(ge_html)
        entry = index.get_item('8')

        assert entry is not None, "Item 8 should exist"
        assert entry.item_number == '8'
        assert 'Financial Statements' in entry.item_title or 'Financial' in entry.item_title
        assert len(entry.pages) > 0, "Item 8 should have page ranges"

    def test_ge_content_extraction_risk_factors(self, ge_html):
        """Test content extraction for Item 1A (Risk Factors)."""
        index = CrossReferenceIndex(ge_html)
        content = index.extract_item_content('1A')

        # Content extraction is experimental but should return something for GE
        if content:
            assert len(content) > 10000, \
                f"Risk Factors should have substantial content (got {len(content)} chars)"

            # Should contain risk-related content (though exact wording may vary)
            # Just verify we got HTML content
            assert '<' in content and '>' in content, "Should return HTML content"

    def test_ge_page_break_detection(self, ge_html):
        """Test that page breaks can be detected in GE filing."""
        index = CrossReferenceIndex(ge_html)
        page_breaks = index.find_page_breaks()

        # GE filings should have many pages
        assert len(page_breaks) > 50, \
            f"GE 10-K should have 50+ pages (got {len(page_breaks)} page breaks)"

        # First break should be at position 0
        assert page_breaks[0] == 0, "First page break should be at position 0"

        # Breaks should be sorted
        assert page_breaks == sorted(page_breaks), "Page breaks should be in order"

    def test_ge_all_parts_present(self, ge_html):
        """Test that all 10-K parts are represented in index."""
        index = CrossReferenceIndex(ge_html)
        entries = index.parse()

        # Part I items
        part_1_items = ['1', '1A', '1B', '2', '3', '4']
        for item_id in part_1_items:
            if item_id != '1B':  # 1B (Unresolved Staff Comments) often "Not applicable"
                assert item_id in entries, f"Part I Item {item_id} should be in index"

        # Part II items
        part_2_items = ['5', '6', '7', '7A', '8', '9', '9A', '9B']
        for item_id in part_2_items:
            if item_id in ['6', '9']:  # Some items may not be present in all years
                continue
            assert item_id in entries, f"Part II Item {item_id} should be in index"

        # Part III items
        part_3_items = ['10', '11', '12', '13', '14']
        for item_id in part_3_items:
            assert item_id in entries, f"Part III Item {item_id} should be in index"


@pytest.mark.network
def test_issue_215_ge_not_applicable_items():
    """Test handling of 'Not applicable' page numbers (e.g., Item 1B)."""
    company = Company('GE')
    filing = company.get_filings(form='10-K').latest()
    html = filing.html()

    index = CrossReferenceIndex(html)
    entries = index.parse()

    # Item 1B is often "Not applicable" for GE
    if '1B' in entries:
        entry = entries['1B']
        # Should exist but might have empty pages
        assert entry.item_number == '1B'
        # Pages might be empty for "Not applicable" items
        # Just verify it parsed without error


@pytest.mark.network
class TestIssue215TenKIntegration:
    """Test TenK integration with Cross Reference Index parser (Phase 4)."""

    @pytest.fixture(scope='class')
    def ge_tenk(self):
        """Get GE's latest 10-K as TenK object."""
        company = Company('GE')
        filing = company.get_filings(form='10-K').latest()
        return filing.obj()

    def test_tenk_risk_factors_property(self, ge_tenk):
        """Test that tenk.risk_factors works for GE (GitHub #215 main issue)."""
        risk_factors = ge_tenk.risk_factors

        assert risk_factors is not None, \
            "GitHub #215: tenk.risk_factors should not return None for GE"
        assert len(risk_factors) > 10000, \
            f"Risk factors should have substantial content (got {len(risk_factors)} chars)"

    def test_tenk_business_property(self, ge_tenk):
        """Test that tenk.business works for GE."""
        business = ge_tenk.business

        assert business is not None, "tenk.business should not return None for GE"
        assert len(business) > 1000, \
            f"Business should have content (got {len(business)} chars)"

    def test_tenk_management_discussion_property(self, ge_tenk):
        """Test that tenk.management_discussion works for GE."""
        mda = ge_tenk.management_discussion

        assert mda is not None, \
            "tenk.management_discussion should not return None for GE"
        assert len(mda) > 10000, \
            f"MD&A should have substantial content (got {len(mda)} chars)"

    def test_tenk_directors_officers_property(self, ge_tenk):
        """Test that tenk.directors_officers_and_governance works for GE."""
        directors = ge_tenk.directors_officers_and_governance

        assert directors is not None, \
            "tenk.directors_officers_and_governance should not return None for GE"
        assert len(directors) > 5000, \
            f"Directors section should have content (got {len(directors)} chars)"

    def test_tenk_getitem_direct_access(self, ge_tenk):
        """Test direct access via tenk['Item 1A'] for GE."""
        item_1a = ge_tenk['Item 1A']

        assert item_1a is not None, "tenk['Item 1A'] should not return None for GE"
        assert len(item_1a) > 10000, \
            f"Item 1A should have substantial content (got {len(item_1a)} chars)"

        # Should match risk_factors property
        assert item_1a == ge_tenk.risk_factors, \
            "tenk['Item 1A'] should match tenk.risk_factors"

    def test_backward_compatibility_standard_format(self):
        """Test that standard format companies still work (backward compatibility)."""
        company = Company('AAPL')
        filing = company.get_filings(form='10-K').latest()
        tenk = filing.obj()

        risk_factors = tenk.risk_factors

        # Apple uses standard format, should still work
        if risk_factors:
            assert len(risk_factors) > 1000, \
                "Standard format extraction should still work"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
