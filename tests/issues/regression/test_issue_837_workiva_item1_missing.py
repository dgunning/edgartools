"""
Regression test for GitHub Issue #837:

On Workiva-authored 10-Ks, the new parser dropped Item 1 (Business). For
Allstate's 2026 10-K, ``doc.items`` was missing ``'Item 1'`` and
``TenK.business`` / ``report["Item 1"]`` fell back to the legacy parser. The
behaviour regressed between 5.25.1 (worked) and 5.29.0+ (broken).

Root cause: ``HybridSectionDetector`` auto-detects the filing agent (Workiva
here) and routes to the agent-specific TOC parser, which resolves item identity
via ``TOCAnalyzer._parse_item_from_text``. That helper matched only explicit
"Item N" / "Part X" patterns and — unlike the generic parser's
``_normalize_section_name`` — ignored the schema keyword vocabulary
(Business → Item 1, Risk Factors → Item 1A). Allstate's Workiva TOC splits the
"Item 1." label and the "Business" title into separate cells with different
hrefs, so the grouped-by-href row carried only "Business";
``_parse_item_from_text("Business")`` returned ``None`` and the row was dropped.

Fix: ``_parse_item_from_text`` now falls back to ``schema.match_text`` after the
explicit Item/Part matches, so all four agent parsers resolve title-only rows
the same way the generic parser does.

The unit tests exercise ``_parse_item_from_text`` directly (no network). The
Allstate end-to-end assertion is VCR-backed and pinned to the reported filing.
"""

import pytest

from edgar.documents.utils.toc_analyzer import TOCAnalyzer


@pytest.fixture
def tenk_analyzer():
    return TOCAnalyzer(form="10-K")


class TestParseItemKeywordFallback:
    """_parse_item_from_text resolves title-only rows via the schema vocabulary."""

    def test_business_resolves_to_item_1(self, tenk_analyzer):
        """The #837 bug: a row whose only text is the title "Business"."""
        assert tenk_analyzer._parse_item_from_text("Business") == "Item 1"

    def test_risk_factors_resolves_to_item_1a(self, tenk_analyzer):
        assert tenk_analyzer._parse_item_from_text("Risk Factors") == "Item 1A"

    def test_explicit_item_wins_over_keyword(self, tenk_analyzer):
        """"Item 1A. Risk Factors" resolves by the explicit label, not the keyword."""
        assert tenk_analyzer._parse_item_from_text("Item 1A. Risk Factors") == "Item 1A"

    def test_explicit_item_label_still_works(self, tenk_analyzer):
        assert tenk_analyzer._parse_item_from_text("Item 1.") == "Item 1"

    def test_page_number_is_none(self, tenk_analyzer):
        assert tenk_analyzer._parse_item_from_text("21") is None

    def test_10q_does_not_misresolve_business(self):
        """10-Q schema has no Business→Item 1 rule, so a stray title stays None."""
        analyzer = TOCAnalyzer(form="10-Q")
        assert analyzer._parse_item_from_text("Business") is None


@pytest.mark.network
@pytest.mark.vcr
def test_allstate_2026_10k_item_1_present():
    """End-to-end on the reported filing: Allstate FY2025 10-K (Workiva agent).

    Pinned by accession (not ``.latest()``) and VCR-backed. Before the fix
    ``part_i_item_1`` was absent and ``obj.business`` was ``None``; it now
    resolves to the ~59K Item 1 Business section.
    """
    from edgar import Filing

    filing = Filing(form='10-K', filing_date='2026-02-18', company='ALLSTATE CORP',
                    cik=899051, accession_no='0000899051-26-000031')
    obj = filing.obj()
    secs = obj.document.sections

    assert "part_i_item_1" in secs
    assert "Item 1" in obj.items

    business = secs.get_item("1")
    assert business is not None
    assert business.part == "I"
    assert len(business.text()) == 59_282

    # The high-level accessor now resolves via the new parser, not the legacy
    # fallback.
    assert obj.business is not None
    assert len(obj.business) == 59_282
