"""
Regression test for GitHub Issue #251: Citigroup 10-K section extraction returns None.

Issue: Citigroup uses bare item numbers (e.g., "1.", "1A.") without the "Item" prefix
and the heading "FORM 10-K CROSS-REFERENCE INDEX" (all caps, hyphenated).
All three parsing strategies failed:
1. TOC parser: links contain only page numbers
2. CrossReferenceIndex: case-sensitive heading match + "Item" prefix required
3. Legacy chunked parser: no "Item X" text anywhere in the 16MB HTML

Solution: Made CrossReferenceIndex detection case-insensitive and hyphen-tolerant,
supported bare item numbers, en-dash page ranges, and continuation rows.
"""

import pytest
from edgar import Company
from edgar.documents import CrossReferenceIndex


@pytest.mark.network
class TestIssue251CitigroupCrossReference:
    """Test Cross Reference Index parser with Citigroup 10-K filings."""

    @pytest.fixture(scope='class')
    def citi_html(self):
        """Get HTML content from Citigroup's latest 10-K."""
        company = Company('C')
        filing = company.get_filings(form='10-K').latest()
        return filing.html()

    def test_citigroup_has_cross_reference_index(self, citi_html):
        """Citigroup's FORM 10-K CROSS-REFERENCE INDEX is detected."""
        assert CrossReferenceIndex(citi_html).has_index()

    def test_citigroup_parses_all_items(self, citi_html):
        """All 14 standard items are parsed from bare item numbers."""
        entries = CrossReferenceIndex(citi_html).parse()
        assert len(entries) >= 14, f"Expected 14+ entries, got {len(entries)}"

        for item_id in ['1', '1A', '1B', '1C', '2', '3', '4',
                         '5', '6', '7', '7A', '8', '9', '9A']:
            assert item_id in entries, f"Missing Item {item_id}"

    def test_citigroup_item1_continuation_rows(self, citi_html):
        """Item 1 page ranges span multiple continuation rows."""
        entry = CrossReferenceIndex(citi_html).get_item('1')
        assert entry is not None
        assert 'Business' in entry.item_title
        # Item 1 has pages across 3 rows: "4-36, 121-127," + "129, 160-164," + "299-300"
        assert len(entry.pages) >= 5, f"Expected 5+ page ranges, got {len(entry.pages)}"

    def test_citigroup_en_dash_page_ranges(self, citi_html):
        """En-dash (&#8211;) page ranges are parsed correctly."""
        entry = CrossReferenceIndex(citi_html).get_item('1A')
        assert entry is not None
        assert len(entry.pages) > 0
        assert entry.pages[0].start == 49
        assert entry.pages[0].end == 62

    def test_citigroup_tenk_section_extraction(self, citi_html):
        """TenK extracts actual content via cross-reference index."""
        company = Company('C')
        filing = company.get_filings(form='10-K').latest()
        tenk = filing.obj()

        # Item 7 (MD&A) should have substantial content
        mda = tenk['Item 7']
        assert mda is not None, "Item 7 (MD&A) should not be None"
        assert len(mda) > 100000, f"MD&A too short: {len(mda)} chars"

        # Item 1A (Risk Factors) should have content
        risk = tenk['Item 1A']
        assert risk is not None, "Item 1A (Risk Factors) should not be None"
        assert len(risk) > 10000, f"Risk Factors too short: {len(risk)} chars"
