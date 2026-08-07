"""
Regression test for GitHub Issue #836 (follow-on to #821):

The 10-K TOC section detector emitted spurious ``part_iv_item_1`` /
``part_iv_item_1a`` keys for UnitedHealth's 2026 10-K. Both were 220,642-char
slabs anchored on an "ITEM 1A. RISK FACTORS" cross-reference inside the Part IV
exhibit index and extended to near end-of-document. Because
``SectionCollection.get_item("1")`` returns the *first* section whose ``.item``
matches (trusting the detector's part label) and the spurious Part IV entry
sorted ahead of the real ``part_i_item_1``, ``sections.get_item("1")`` and
``sections.get("Item 1")`` silently returned 220K of Risk Factors instead of
the 47K Item 1 Business section. No exception was raised.

Root cause: ``TocAnalyzer._make_section_key`` paired the running ``current_part``
with the matched item unconditionally. On a 10-K every item has exactly one
valid Part (Items 1–4 are Part I only), so a detected Part IV for Item 1/1A is a
misplaced anchor.

Fix: ``_make_section_key`` now returns ``None`` (rejecting the detection) when a
detected part conflicts with the item's SEC-canonical part on a unique-item
form. The bare/inferred-part paths are unchanged, and retrieval of any dropped
section falls through to the canonical-Part key or the legacy parser (same path
as #821).

The unit tests here exercise ``_make_section_key`` directly (no network). The
UNH end-to-end assertion is marked ``network`` and pinned to the reported
filing.
"""

import pytest

from edgar.documents.utils.toc_analyzer import TOCAnalyzer


@pytest.fixture
def tenk_analyzer():
    return TOCAnalyzer(form="10-K")


class TestMakeSectionKeyValidity:
    """_make_section_key rejects an item detected *after* its canonical Part.

    The rule is directional: a detected Part later than the item's only valid
    Part is a back-reference (exhibit index / cross-reference) and is dropped; a
    detected Part earlier than canonical is a coarse single-header TOC and is
    kept.
    """

    def test_rejects_item_1_under_part_iv(self, tenk_analyzer):
        """The #836 bug: Item 1 cited in the Part IV exhibit index is a back-ref."""
        assert tenk_analyzer._make_section_key("Item 1", "Part IV") is None

    def test_rejects_item_1a_under_part_iv(self, tenk_analyzer):
        assert tenk_analyzer._make_section_key("Item 1A", "Part IV") is None

    def test_rejects_item_1_under_part_ii(self, tenk_analyzer):
        """The #821 GS mislabel direction: Item 1 under a later Part II."""
        assert tenk_analyzer._make_section_key("Item 1", "Part II") is None

    def test_keeps_item_7_under_part_i_coarse_toc(self, tenk_analyzer):
        """Item 7 (canonical Part II) listed under a lone earlier Part I header.

        This is a coarse TOC, not a back-reference — the detected key is kept so
        a real section is not lost.
        """
        assert tenk_analyzer._make_section_key("Item 7", "Part I") == "part_i_item_7"

    def test_keeps_item_1_under_part_i(self, tenk_analyzer):
        """The legitimate detection is unchanged."""
        assert tenk_analyzer._make_section_key("Item 1", "Part I") == "part_i_item_1"

    def test_keeps_item_15_under_part_iv(self, tenk_analyzer):
        """Item 15 genuinely lives in Part IV — must not be rejected."""
        assert tenk_analyzer._make_section_key("Item 15", "Part IV") == "part_iv_item_15"

    def test_infers_part_when_none_detected(self, tenk_analyzer):
        """No part context: infer the canonical part from the item number (3usf)."""
        assert tenk_analyzer._make_section_key("Item 1", None) == "part_i_item_1"
        assert tenk_analyzer._make_section_key("Item 7", None) == "part_ii_item_7"

    def test_part_label_format_tolerance(self, tenk_analyzer):
        """Ranking is on the roman numeral, not exact string form."""
        # bare roman, lowercase — same Part, still kept
        assert tenk_analyzer._make_section_key("Item 1", "I") == "i_item_1"
        # later bare roman — still rejected as a back-reference
        assert tenk_analyzer._make_section_key("Item 1", "iv") is None


class TestTenQUnaffected:
    """10-Q items repeat across parts — no canonical part, so never rejected."""

    def test_10q_trusts_detected_part(self):
        analyzer = TOCAnalyzer(form="10-Q")
        # Part II Item 1 (Legal Proceedings) is valid on a 10-Q — must be kept.
        assert analyzer._make_section_key("Item 1", "Part II") == "part_ii_item_1"
        assert analyzer._make_section_key("Item 1", "Part I") == "part_i_item_1"


@pytest.mark.network
@pytest.mark.vcr
def test_unh_2026_10k_no_spurious_part_iv_item_1():
    """End-to-end on the reported filing: UNH FY2025 10-K.

    Pinned by accession (not ``.latest()``) so the regression stays anchored to
    the document that exhibited the bug even after UNH files its next 10-K, and
    VCR-backed for determinism. Before the fix, ``sections.get_item("1")``
    returned a 220,642-char Part IV Risk-Factors slab; it now returns the real
    46,852-char Item 1 Business section.
    """
    from edgar import Filing

    filing = Filing(form='10-K', filing_date='2026-03-02',
                    company='UNITEDHEALTH GROUP INC', cik=731766,
                    accession_no='0000731766-26-000062')
    obj = filing.obj()
    secs = obj.document.sections

    assert "part_iv_item_1" not in secs
    assert "part_iv_item_1a" not in secs

    # get_item("1") returns the real Part I Business section, not the 220K slab.
    business = secs.get_item("1")
    assert business is not None
    assert business.part == "I"
    assert len(business.text()) == 46_852

    # The high-level accessor is unchanged (the #821 fix).
    assert len(obj.business) == 46_852
