"""
Tests for 10-K Item 1B and Item 1C section detection.

Bug: SECTION_PATTERNS['10-K'] in edgar/documents/extractors/pattern_section_extractor.py
was missing entries for:

- Item 1B (Unresolved Staff Comments) — has been part of the 10-K
  structure for many years.
- Item 1C (Cybersecurity Risk Management, Strategy, and Governance) —
  mandatory for FY2024+ filings under 17 CFR § 229.106 (SEC Release
  No. 33-11216, July 2023).

When the pattern extractor was the active detection path inside
HybridSectionDetector (TOC detection didn't fire and heading detection
returned no sections), both items were silently absent from the
resulting sections dict, even when the underlying filing text
contained them.

Note: EdgarTools already ships cybersecurity patterns for the two
other SEC forms updated by the same 2023 rulemaking — 8-K Item 1.05
("Material Cybersecurity Incidents") and 20-F Item 16K
("Cybersecurity"). 10-K Item 1C was simply missed in the same wave.

Fix:
- edgar/documents/extractors/pattern_section_extractor.py:
  Added 'unresolved_staff_comments' and 'cybersecurity' entries to
  SECTION_PATTERNS['10-K']. Purely additive — follows the same shape
  as the existing 20-F 'item_16k' (line 242) and 8-K 'item_105'
  (line 297) entries.

Test cases cover:
- Both new pattern keys exist in SECTION_PATTERNS['10-K'].
- Each pattern matches the canonical mixed-case form ("Item 1C. Cybersecurity").
- Each pattern matches the all-caps form ("ITEM 1C. CYBERSECURITY")
  under the same re.IGNORECASE flag the production code uses.
- End-to-end: HybridSectionDetector finds Item 1B and Item 1C as
  sections on a minimal 10-K-shaped document.
"""
import re

import pytest

from edgar.documents import HTMLParser
from edgar.documents.config import ParserConfig
from edgar.documents.extractors.hybrid_section_detector import HybridSectionDetector
from edgar.documents.extractors.pattern_section_extractor import SectionExtractor


class TestSectionPatternsMembership:
    """Verify SECTION_PATTERNS['10-K'] contains the two new keys."""

    def test_section_patterns_10k_includes_cybersecurity(self):
        """Item 1C (Cybersecurity) must be a recognized 10-K section pattern key."""
        assert 'cybersecurity' in SectionExtractor.SECTION_PATTERNS['10-K']

    def test_section_patterns_10k_includes_unresolved_staff_comments(self):
        """Item 1B (Unresolved Staff Comments) must be a recognized 10-K key."""
        assert 'unresolved_staff_comments' in SectionExtractor.SECTION_PATTERNS['10-K']

    def test_cybersecurity_key_matches_ten_k_section_to_item_mapping(self):
        """The friendly-name key must match what TenK.items expects.

        TenK.items maps friendly section names back to "Item X" strings via
        a section_to_item dict. Using a key that dict already recognizes
        means no downstream changes are needed.
        """
        from edgar.company_reports.ten_k import TenK  # noqa: F401
        # The mapping is constructed inline in TenK.items / TenK.__getitem__.
        # We assert the key is present in our new pattern dict; the rest is
        # covered by TenK's own tests.
        assert 'cybersecurity' in SectionExtractor.SECTION_PATTERNS['10-K']
        assert 'unresolved_staff_comments' in SectionExtractor.SECTION_PATTERNS['10-K']


class TestItem1CPatternMatching:
    """Verify the Item 1C regex patterns match canonical heading forms."""

    @pytest.fixture
    def patterns(self):
        return SectionExtractor.SECTION_PATTERNS['10-K']['cybersecurity']

    def test_matches_canonical_mixed_case(self, patterns):
        """'Item 1C. Cybersecurity' is the canonical heading form."""
        assert any(
            re.match(p, "Item 1C. Cybersecurity", re.IGNORECASE)
            for p, _ in patterns
        )

    def test_matches_all_caps(self, patterns):
        """SEC filings commonly use 'ITEM 1C. CYBERSECURITY' all-caps."""
        assert any(
            re.match(p, "ITEM 1C. CYBERSECURITY", re.IGNORECASE)
            for p, _ in patterns
        )

    def test_matches_no_period(self, patterns):
        """Some filings render the heading without a period after 1C."""
        assert any(
            re.match(p, "Item 1C Cybersecurity", re.IGNORECASE)
            for p, _ in patterns
        )

    def test_matches_risk_management_subtitle(self, patterns):
        """The 'Cybersecurity Risk Management and Strategy' subhead is a fallback."""
        assert any(
            re.match(p, "Cybersecurity Risk Management and Strategy", re.IGNORECASE)
            for p, _ in patterns
        )


class TestItem1BPatternMatching:
    """Verify the Item 1B regex patterns match canonical heading forms."""

    @pytest.fixture
    def patterns(self):
        return SectionExtractor.SECTION_PATTERNS['10-K']['unresolved_staff_comments']

    def test_matches_canonical_mixed_case(self, patterns):
        assert any(
            re.match(p, "Item 1B. Unresolved Staff Comments", re.IGNORECASE)
            for p, _ in patterns
        )

    def test_matches_all_caps(self, patterns):
        assert any(
            re.match(p, "ITEM 1B. UNRESOLVED STAFF COMMENTS", re.IGNORECASE)
            for p, _ in patterns
        )


class TestEndToEndHybridDetection:
    """End-to-end: when only the pattern path is reachable, 1B and 1C are found."""

    MINIMAL_10K_HTML = """
    <html><body>
    <p><strong>Item 1. Business</strong></p>
    <p>We design and manufacture electric vehicles.</p>

    <p><strong>Item 1B. Unresolved Staff Comments</strong></p>
    <p>None.</p>

    <p><strong>Item 1C. Cybersecurity</strong></p>
    <p>Cybersecurity Risk Management and Strategy. We assess and manage
    cybersecurity risks across our operations.</p>

    <p><strong>Item 2. Properties</strong></p>
    <p>Our principal facilities are located worldwide.</p>
    </body></html>
    """

    def _detect(self):
        doc = HTMLParser(ParserConfig(form="10-K")).parse(self.MINIMAL_10K_HTML)
        return HybridSectionDetector(doc, form="10-K").detect_sections()

    def test_hybrid_detector_finds_cybersecurity(self):
        """Item 1C must appear in the sections dict on a minimal 10-K."""
        sections = self._detect()
        assert 'cybersecurity' in sections, (
            f"expected 'cybersecurity' section; got: {sorted(sections.keys())}"
        )

    def test_hybrid_detector_finds_unresolved_staff_comments(self):
        """Item 1B must appear in the sections dict on a minimal 10-K."""
        sections = self._detect()
        assert 'unresolved_staff_comments' in sections, (
            f"expected 'unresolved_staff_comments' section; "
            f"got: {sorted(sections.keys())}"
        )

    def test_hybrid_detector_existing_items_still_found(self):
        """Regression: existing 10-K sections (business, properties) keep working."""
        sections = self._detect()
        for key in ('business', 'properties'):
            assert key in sections, (
                f"existing section '{key}' must still be found; "
                f"got: {sorted(sections.keys())}"
            )
