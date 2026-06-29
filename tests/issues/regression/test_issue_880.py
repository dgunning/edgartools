"""
Regression test for GH #880 / edgartools-01x4:
TenK[item] merges adjacent Part III items; the absorbed item returns empty.

Bug (FIXED): When a 10-K uses a compact "incorporated by reference" Part III
stub (e.g., Tesla FY2022), Items 10-14 were rendered as sparse bold paragraphs
rather than semantic heading nodes. Only Item 10 had a HeadingNode child
("DIRECTORS, EXECUTIVE OFFICERS AND CORPORATE GOVERNANCE"); Items 11-14 were
bare ParagraphNodes. Because Item 11's header was never registered in the pattern
extractor's boundary_indices set, Item 10's section span ran straight through it,
absorbing "ITEM 11. EXECUTIVE COMPENSATION" into Item 10's text and leaving Item
11 empty. Part III items (10-14) were absent from o.items entirely.

Root cause (triple failure):
1. _TEN_K_SECTION_PATTERNS had no entries for Part III Items 10-14, so they were
   never registered as section boundaries.
2. _find_section_headers Strategy 3 is gated on "no complete item headers found
   yet" and was therefore skipped for this filing (Part I/II had complete headers).
   The new Strategy 3b (unconditional, checks bold *children* of ParagraphNodes)
   was needed to capture Items 11-14 as boundary candidates.
3. HybridSectionDetector stopped at TOC detection, which correctly found the
   main sections but omitted Part III (proxy-incorporated, not in the TOC). The
   pattern extractor was never invoked to fill in the missing items.

Fix (three-part):
- edgar/documents/form_schema.py: Added part_iii_item_10..14 and part_iv_item_16
  patterns to _TEN_K_SECTION_PATTERNS so their headers act as section boundaries.
- edgar/documents/extractors/pattern_section_extractor.py: Added Strategy 3b
  that unconditionally captures ParagraphNodes with bold TextNode children whose
  text matches a section-header pattern (Item N. TITLE).
- edgar/documents/extractors/hybrid_section_detector.py: After TOC detection
  succeeds, call _augment_with_pattern_sections() to merge in any items the TOC
  missed (specifically the proxy-incorporated Part III stub).

Ground truth (Tesla FY2022 10-K, accession 0000950170-23-001409, filed 2023-01-31):
- Item 10 ("DIRECTORS, EXECUTIVE OFFICERS AND CORPORATE GOVERNANCE"): ~513 chars
  (a "see proxy statement" stub; does NOT contain "ITEM 11").
- Item 11 ("EXECUTIVE COMPENSATION"): ~172 chars (separate "see proxy" stub).
- Items 10-14 all appear in o.items.
"""

from pathlib import Path

import pytest

import edgar

# ---------------------------------------------------------------------------
# VCR configuration — use a single module-level cassette for the Tesla fixture
# so all tests in this module share one recording.
# ---------------------------------------------------------------------------
try:
    import vcr as _vcr_module

    _CASSETTES_DIR = Path(__file__).parent.parent.parent / "cassettes"
    _my_vcr = _vcr_module.VCR(
        cassette_library_dir=str(_CASSETTES_DIR),
        record_mode="none",            # replay cassette only; never re-record
        match_on=["method", "scheme", "host", "port", "path", "query"],
        filter_headers=["User-Agent", "Authorization"],
        decode_compressed_response=True,
    )
    _HAS_VCR = True
except ImportError:
    _HAS_VCR = False
    _my_vcr = None


# ---------------------------------------------------------------------------
# Tesla FY2022 10-K: incorporated-by-reference Part III stub
# Cassette: tests/cassettes/test_issue_880_tesla_2022.yaml
# ---------------------------------------------------------------------------

_TESLA_2022_CASSETTE = "test_issue_880_tesla_2022.yaml"


@pytest.fixture(scope="module")
def tesla_2022_10k():
    """Tesla FY2022 10-K filed 2023-01-31 (accession 0000950170-23-001409).

    The cassette records all HTTP calls needed to fetch and parse the filing.
    If the cassette does not exist, regenerate it by temporarily switching
    record_mode to "once" in _my_vcr above and running the test once with
    network access, then restore record_mode to "none".
    """
    if _HAS_VCR:
        # record_mode="once" will record on first run and replay thereafter.
        with _my_vcr.use_cassette(_TESLA_2022_CASSETTE):
            return edgar.get_by_accession_number("0000950170-23-001409").obj()
    else:
        pytest.skip("vcrpy not installed — install it to run this test offline")


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

class TestTesla2022PartIII:
    """GH #880: Part III items must be independently extractable."""

    def test_item_10_does_not_absorb_item_11(self, tesla_2022_10k):
        """Item 10 must terminate at the Item 11 header, not absorb it.

        Before the fix: Item 10 contained 'ITEM 11. EXECUTIVE COMPENSATION'
        because the Item 11 paragraph was not registered as a boundary.
        """
        t10 = (tesla_2022_10k["Item 10"] or "").strip()
        assert "ITEM 11" not in t10.upper(), (
            "Item 10 must not absorb Item 11 header — boundary detection broken"
        )

    def test_item_10_ground_truth_length(self, tesla_2022_10k):
        """Item 10 is a short 'see proxy' stub — ground truth is ~513 chars."""
        t10 = (tesla_2022_10k["Item 10"] or "").strip()
        # Allow ±25% around the ground-truth 513-char stub
        assert 300 <= len(t10) <= 650, (
            f"Item 10 length {len(t10)} outside expected range [300, 650]; "
            "got absorbed or empty section"
        )

    def test_item_11_is_non_empty(self, tesla_2022_10k):
        """Item 11 must return its own 'see proxy' stub, not be empty.

        Before the fix: Item 11 returned empty string because its content was
        absorbed into Item 10 and no section boundary was detected.
        Ground truth: ~172-char 'see proxy' sentence.
        """
        t11 = (tesla_2022_10k["Item 11"] or "").strip()
        assert len(t11) > 50, (
            f"Item 11 is nearly empty ({len(t11)} chars) — boundary detection broken"
        )
        # Ground-truth content substring (stable proxy-reference language)
        assert "proxy statement" in t11.lower(), (
            "Item 11 must contain the proxy-reference boilerplate"
        )

    def test_part_iii_items_in_items_list(self, tesla_2022_10k):
        """Part III items 10-14 must all appear in o.items.

        Before the fix: o.items contained only Parts I/II/IV items.
        """
        items = tesla_2022_10k.items
        for item_num in ("Item 10", "Item 11", "Item 12", "Item 13", "Item 14"):
            assert item_num in items, (
                f"{item_num} missing from o.items={items}; "
                "Part III detection broken"
            )

    def test_parts_i_ii_unchanged(self, tesla_2022_10k):
        """Parts I/II items must still be present and have content (no regression)."""
        items = tesla_2022_10k.items
        for item_num in ("Item 1", "Item 1A", "Item 7", "Item 8"):
            assert item_num in items, (
                f"{item_num} missing from o.items after fix; regression"
            )
        # Verify substantive content is still returned
        t1 = (tesla_2022_10k["Item 1"] or "").strip()
        assert len(t1) > 1000, (
            f"Item 1 (Business) has only {len(t1)} chars — content lost"
        )
