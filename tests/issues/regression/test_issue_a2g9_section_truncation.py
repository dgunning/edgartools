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

Offline: these tests read committed copies of the primary 10-K documents under
tests/fixtures/html/ instead of each company's latest 10-K, so the filing under test
no longer changes when a company files again. The filings:

- MSFT 10-K filed 2025-07-30, accession 0000950170-25-100235 (msft-20250630.htm)
- AAPL 10-K filed 2024-11-01, accession 0000320193-24-000123 (aapl-20240928.htm)
- GOOGL 10-K filed 2025-02-05, accession 0001652044-25-000014 (goog-20241231.htm)

Ground truth, hand-checked against the MSFT document: in its text, ITEM 1A. RISK FACTORS
starts at character 88,117 and ITEM 1B. UNRESOLVED STAFF COMMENTS at 156,973, and the last
sentence before ITEM 1B is the unionization risk ending "...to establish new relationships
with worker representatives." Extracted, Item 1A is 68,824 characters. The truncated
extraction stopped at ~4.6k and never reached that sentence.
"""
from pathlib import Path

import pytest

from edgar.company_reports import TenK

pytestmark = pytest.mark.fast

HTML_ROOT = Path(__file__).parents[2] / "fixtures" / "html"
MSFT_10K = HTML_ROOT / "msft" / "10k" / "msft-10-k-2025-07-30.html"
AAPL_10K = HTML_ROOT / "aapl" / "10k" / "aapl-10-k-2024-11-01.html"
GOOGL_10K = HTML_ROOT / "googl" / "10k" / "googl-10-k-2025-02-05.html"

MSFT_ITEM_1A_LAST_SENTENCE = (
    "The unionization of significant employee populations could result in higher costs and "
    "other operational changes necessary to respond to changing conditions and to establish "
    "new relationships with worker representatives."
)


class FixtureFiling:
    """The minimum surface a report touches, backed by a local file."""

    filing_date = None
    company = "fixture"

    def __init__(self, path: Path, form: str):
        self._path = path
        self.form = form
        self.accession_number = path.stem
        self.base_dir = str(path.parent)

    def html(self):
        return self._path.read_text(encoding="utf-8", errors="replace")


@pytest.fixture(scope="module")
def msft():
    return TenK(FixtureFiling(MSFT_10K, "10-K"))


def test_the_fixtures_are_present():
    """Absent is not passing."""
    for path in (MSFT_10K, AAPL_10K, GOOGL_10K):
        assert path.is_file(), path


class TestMultiContainerSectionExtraction:
    """Test that section extraction handles multi-container HTML structures."""

    def test_msft_item_1a_not_truncated(self, msft):
        """MSFT 10-K Item 1A should extract full ~69k chars, not truncated ~4.6k chars."""
        item1a = msft["Item 1A"]

        assert item1a is not None, "Item 1A should be found"
        # Before fix: 4,612 chars. After fix: 68,824 chars on this filing.
        assert len(item1a) > 50000, (
            f"Item 1A should be >50k chars (was truncated to ~4.6k before fix), got {len(item1a)}"
        )

    def test_msft_item_1a_runs_to_its_last_risk_factor(self, msft):
        """The section ends with the last sentence before ITEM 1B, which truncation never reached."""
        item1a = msft["Item 1A"]

        assert item1a.startswith("ITEM 1A. RISK FACTORS")
        assert item1a.rstrip().endswith(MSFT_ITEM_1A_LAST_SENTENCE)
        assert "UNRESOLVED STAFF COMMENTS" not in item1a

    @pytest.mark.parametrize("path, section_name, min_length", [
        (AAPL_10K, "Item 1A", 30000),   # Apple Risk Factors
        (GOOGL_10K, "Item 1A", 30000),  # Alphabet Risk Factors
        (MSFT_10K, "Item 7", 30000),    # Microsoft MD&A
    ], ids=["AAPL-1A", "GOOGL-1A", "MSFT-7"])
    def test_section_extraction_across_companies(self, path, section_name, min_length):
        """Verify section extraction works for multiple companies with different HTML structures."""
        tenk = TenK(FixtureFiling(path, "10-K"))

        section_text = tenk[section_name]

        assert section_text is not None, f"{path.stem} {section_name} should be found"
        assert len(section_text) > min_length, (
            f"{path.stem} {section_name} should be >{min_length} chars, got {len(section_text)}"
        )


class TestSectionExtractionConsistency:
    """Test that section extraction is consistent and complete."""

    def test_item_1a_contains_expected_content(self, msft):
        """MSFT Item 1A should contain risk factor content, not just headers."""
        item1a = msft["Item 1A"]
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

    def test_multiple_sections_extractable(self, msft):
        """Multiple sections should be extractable from same document."""
        sections_to_check = ["Item 1", "Item 1A", "Item 7", "Item 8"]
        extracted = {}

        for section_name in sections_to_check:
            content = msft[section_name]
            if content:
                extracted[section_name] = len(content)

        assert len(extracted) >= 3, (
            f"Should extract at least 3 sections, got {len(extracted)}: {list(extracted.keys())}"
        )

        # Each section should have substantial content
        for name, length in extracted.items():
            assert length > 5000, f"{name} should have >5000 chars, got {length}"
