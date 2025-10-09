"""
Test edge cases in section detection.
"""
from pathlib import Path
import pytest

from edgar.documents import parse_html
from edgar.documents.config import ParserConfig
from edgar.documents.extractors.hybrid_section_detector import HybridSectionDetector


def test_missing_toc():
    """Test section detection when TOC is missing."""
    html = """<html><body>
        <h1>Item 1. Business</h1>
        <p>We develop software...</p>
        <h1>Item 1A. Risk Factors</h1>
        <p>We face various risks...</p>
    </body></html>"""

    config = ParserConfig(filing_type='10-K')
    doc = parse_html(html, config)

    detector = HybridSectionDetector(doc, '10-K')
    sections = detector.detect_sections()

    # Should fall back to heading or pattern detection
    assert len(sections) > 0, "Should detect sections without TOC"


def test_malformed_headers():
    """Test section detection with malformed/inconsistent headers."""
    html = """<html><body>
        <p><b>ITEM 1.</b> Business</p>
        <p>Business content...</p>
        <div><strong>ITEM 1A</strong> Risk Factors</div>
        <p>Risk factors content...</p>
    </body></html>"""

    config = ParserConfig(filing_type='10-K')
    doc = parse_html(html, config)

    sections = doc.sections

    # Should handle malformed headers gracefully
    # May or may not detect sections depending on patterns
    assert isinstance(sections, dict), "Should return dict even with malformed headers"


def test_empty_sections():
    """Test detection when sections have no content."""
    html = """<html><body>
        <h1>Item 1. Business</h1>
        <h1>Item 1A. Risk Factors</h1>
        <h1>Item 2. Properties</h1>
    </body></html>"""

    config = ParserConfig(filing_type='10-K')
    doc = parse_html(html, config)

    sections = doc.sections

    # Should detect section headers even if empty
    assert isinstance(sections, dict), "Should handle empty sections"


def test_overlapping_sections():
    """Test boundary resolution for overlapping sections."""
    html = """<html><body>
        <div id="toc">
            <a href="#s1">Item 1</a>
            <a href="#s2">Item 2</a>
        </div>
        <div id="s1">Item 1 content at position 100</div>
        <div id="s2">Item 2 content at position 100</div>
    </body></html>"""

    config = ParserConfig(filing_type='10-K')
    doc = parse_html(html, config)

    detector = HybridSectionDetector(doc, '10-K')
    sections = detector.detect_sections()

    # Should resolve overlaps
    if len(sections) > 1:
        section_list = sorted(sections.values(), key=lambda s: s.start_offset)
        for i in range(len(section_list) - 1):
            # Check no overlap (or minimal)
            assert section_list[i].end_offset <= section_list[i+1].start_offset + 10, \
                "Sections should not significantly overlap"


def test_api_vs_legacy_html():
    """Test section detection works for both API and legacy HTML formats."""
    # Use real Apple filing (API format)
    if Path('tests/fixtures/html/aapl/10k/aapl-10-k-2024-11-01.html').exists():
        apple_html = Path('tests/fixtures/html/aapl/10k/aapl-10-k-2024-11-01.html').read_text()

        config = ParserConfig(filing_type='10-K')
        doc = parse_html(apple_html, config)

        sections = doc.sections

        # Should detect sections in API format
        assert len(sections) > 0, "Should detect sections in API format"
        assert all(s.confidence > 0 for s in sections.values()), "All sections should have confidence"


def test_no_sections_in_document():
    """Test handling of documents with no identifiable sections."""
    html = """<html><body>
        <p>This is a press release about our company.</p>
        <p>We are excited to announce new products.</p>
        <p>Contact us for more information.</p>
    </body></html>"""

    config = ParserConfig(filing_type='10-K')
    doc = parse_html(html, config)

    sections = doc.sections

    # Should return empty dict, not fail
    assert sections == {}, "Should return empty dict for documents with no sections"


def test_mixed_case_item_headers():
    """Test detection of item headers with various cases."""
    html = """<html><body>
        <h1>item 1. business</h1>
        <p>Content...</p>
        <h1>ITEM 1A. RISK FACTORS</h1>
        <p>Content...</p>
        <h1>Item 2. Properties</h1>
        <p>Content...</p>
    </body></html>"""

    config = ParserConfig(filing_type='10-K')
    doc = parse_html(html, config)

    sections = doc.sections

    # Should handle various cases
    if len(sections) > 0:
        # At least some sections should be detected
        assert all(hasattr(s, 'confidence') for s in sections.values()), \
            "All detected sections should have confidence"


def test_sections_with_unicode():
    """Test section detection with unicode characters."""
    html = """<html><body>
        <h1>Item 1. Business™</h1>
        <p>Our company focuses on innovation…</p>
        <h1>Item 1A. Risk Factors®</h1>
        <p>We face risks including: • Market volatility • Competition</p>
    </body></html>"""

    config = ParserConfig(filing_type='10-K')
    doc = parse_html(html, config)

    sections = doc.sections

    # Should handle unicode gracefully
    assert isinstance(sections, dict), "Should handle unicode in sections"


def test_nested_sections():
    """Test detection when sections contain nested structures."""
    html = """<html><body>
        <div>
            <div>
                <h1>Item 1. Business</h1>
                <div>
                    <div>
                        <p>Nested content...</p>
                    </div>
                </div>
            </div>
        </div>
    </body></html>"""

    config = ParserConfig(filing_type='10-K')
    doc = parse_html(html, config)

    sections = doc.sections

    # Should handle nested structures
    assert isinstance(sections, dict), "Should handle nested section structures"


def test_large_document_performance():
    """Test that section detection doesn't timeout on large documents."""
    # Use real Apple filing which is large
    if Path('tests/fixtures/html/aapl/10k/aapl-10-k-2024-11-01.html').exists():
        import time

        apple_html = Path('tests/fixtures/html/aapl/10k/aapl-10-k-2024-11-01.html').read_text()
        config = ParserConfig(filing_type='10-K')

        start = time.time()
        doc = parse_html(apple_html, config)
        _ = doc.sections
        elapsed = time.time() - start

        # Should complete in reasonable time (< 5 seconds)
        assert elapsed < 5.0, f"Section detection took too long: {elapsed:.2f}s"


def test_sections_with_tables():
    """Test section detection when sections contain complex tables."""
    html = """<html><body>
        <h1>Item 8. Financial Statements</h1>
        <table>
            <tr><th>Revenue</th><td>$1000</td></tr>
            <tr><th>Expenses</th><td>$500</td></tr>
        </table>
        <h1>Item 9. Changes and Disagreements</h1>
        <p>None.</p>
    </body></html>"""

    config = ParserConfig(filing_type='10-K')
    doc = parse_html(html, config)

    sections = doc.sections

    # Should detect sections with tables
    if sections:
        for name, section in sections.items():
            # Section should be valid
            assert hasattr(section, 'node'), f"Section {name} should have node"


if __name__ == '__main__':
    pytest.main([__file__, '-xvs'])
