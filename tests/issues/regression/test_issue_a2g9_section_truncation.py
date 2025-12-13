"""
Regression tests for Issue edgartools-a2g9: TOC section extraction truncates multi-container sections.

Bug: Section extraction returned only ~4,612 chars instead of ~69,000+ chars for MSFT Item 1A
(Risk Factors) because _extract_section_content() only walked siblings, missing content when
start and end anchors were in different parent containers.

Root cause: HTML documents like MSFT's 10-K have section content spread across multiple container
elements. The old algorithm walked siblings of the start anchor, but would stop when siblings
ran out, even though the end anchor was further down in a different container.

Fix: edgar/documents/extractors/toc_section_extractor.py:200-273
Changed from sibling-walking to document-order traversal using etree.iterwalk(), which correctly
handles multi-container sections by iterating through all elements between start and end anchors.

Test cases cover:
- MSFT 10-K Item 1A extraction length (should be >50k chars)
- Section extraction consistency across multiple companies
- No regression in normal single-container sections
"""
import pytest


@pytest.mark.network
class TestMultiContainerSectionExtraction:
    """Test that section extraction handles multi-container HTML structures."""

    def test_msft_item_1a_not_truncated(self):
        """MSFT 10-K Item 1A should extract full ~69k chars, not truncated ~4.6k chars."""
        from edgar import Company

        msft = Company("MSFT")
        tenk = msft.get_filings(form="10-K").latest(1).obj()

        item1a = tenk["Item 1A"]

        assert item1a is not None, "Item 1A should be found"
        # Before fix: 4,612 chars. After fix: ~69,000 chars
        # Use 50k as threshold to allow for filing variations
        assert len(item1a) > 50000, (
            f"Item 1A should be >50k chars (was truncated to ~4.6k before fix), got {len(item1a)}"
        )

    def test_section_extraction_across_companies(self):
        """Verify section extraction works for multiple companies with different HTML structures."""
        from edgar import Company

        test_cases = [
            ("AAPL", "Item 1A", 30000),  # Apple Risk Factors
            ("GOOGL", "Item 1A", 30000),  # Alphabet Risk Factors
            ("MSFT", "Item 7", 30000),  # Microsoft MD&A
        ]

        for ticker, section_name, min_length in test_cases:
            company = Company(ticker)
            tenk = company.get_filings(form="10-K").latest(1).obj()

            section_text = tenk[section_name]

            assert section_text is not None, f"{ticker} {section_name} should be found"
            assert len(section_text) > min_length, (
                f"{ticker} {section_name} should be >{min_length} chars, got {len(section_text)}"
            )


@pytest.mark.network
class TestSectionExtractionConsistency:
    """Test that section extraction is consistent and complete."""

    def test_item_1a_contains_expected_content(self):
        """MSFT Item 1A should contain risk factor content, not just headers."""
        from edgar import Company

        msft = Company("MSFT")
        tenk = msft.get_filings(form="10-K").latest(1).obj()

        item1a = tenk["Item 1A"]
        item1a_lower = item1a.lower() if item1a else ""

        # Check for content that should appear throughout the section
        assert "risk" in item1a_lower, "Item 1A should contain 'risk'"
        assert "competition" in item1a_lower or "competitive" in item1a_lower, (
            "Item 1A should discuss competition"
        )
        # Check for content that appears later in the section (was truncated before fix)
        assert "cybersecurity" in item1a_lower or "security" in item1a_lower, (
            "Item 1A should discuss security risks (appears later in section)"
        )

    def test_multiple_sections_extractable(self):
        """Multiple sections should be extractable from same document."""
        from edgar import Company

        msft = Company("MSFT")
        tenk = msft.get_filings(form="10-K").latest(1).obj()

        sections_to_check = ["Item 1", "Item 1A", "Item 7", "Item 8"]
        extracted = {}

        for section_name in sections_to_check:
            content = tenk[section_name]
            if content:
                extracted[section_name] = len(content)

        assert len(extracted) >= 3, (
            f"Should extract at least 3 sections, got {len(extracted)}: {list(extracted.keys())}"
        )

        # Each section should have substantial content
        for name, length in extracted.items():
            assert length > 5000, f"{name} should have >5000 chars, got {length}"
