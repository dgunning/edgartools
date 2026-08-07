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


# --- edgartools-rbsx: agent path no longer drops Item 9C / Signatures ---------

# Minimal Workiva-style TOC: five normal split-cell item rows (enough item links
# for the link-based TOC finder), plus the two rows the agent path used to drop —
# a 9C row whose "Item 9C." label is PLAIN TEXT (only the title and page are
# links, so the href-grouped text lacks the number) and a bare "Part IV" header
# followed by a numberless "Signatures" row.
WORKIVA_9C_SIG_HTML = """
<html><body>
<div>TABLE OF CONTENTS</div>
<table>
<tr><td><a href="#a13">Item 1.</a></td><td><a href="#a13">Business</a></td><td><a href="#a13">1</a></td></tr>
<tr><td><a href="#a52">Item 1A.</a></td><td><a href="#a52">Risk Factors</a></td><td><a href="#a52">5</a></td></tr>
<tr><td><a href="#a70">Item 1B.</a></td><td><a href="#a70">Unresolved Staff Comments</a></td><td><a href="#a70">15</a></td></tr>
<tr><td><a href="#a94">Item 7.</a></td><td><a href="#a94">MD&amp;A</a></td><td><a href="#a94">20</a></td></tr>
<tr><td><a href="#a175">Item 8.</a></td><td><a href="#a175">Financial Statements</a></td><td><a href="#a175">30</a></td></tr>
<tr><td>Item 9C.</td><td><a href="#a235">Disclosure Regarding Foreign Jurisdictions that Prevent Inspections</a></td><td><a href="#a235">170</a></td></tr>
<tr><td colspan="3">Part IV</td></tr>
<tr><td><a href="#a265">Signatures</a></td><td><a href="#a265">177</a></td></tr>
</table>
<div id="a13">Item 1. Business</div>
<div id="a52">Item 1A. Risk Factors</div>
<div id="a70">Item 1B. Unresolved Staff Comments</div>
<div id="a94">Item 7. MD&A</div>
<div id="a175">Item 8. Financial Statements</div>
<div id="a235">Item 9C. Disclosure Regarding Foreign Jurisdictions that Prevent Inspections</div>
<div id="a265">Signatures</div>
</body></html>
"""


class TestRbsxNamedSectionAndRowFallback:
    """Agent path keeps Item 9C (plain-text label) and Signatures (named section)."""

    def test_signatures_named_section_resolves(self):
        analyzer = TOCAnalyzer(form="10-K")
        assert analyzer._parse_item_from_text("Signatures") == "signatures"

    def test_item_label_only_row_does_not_invent_a_section(self):
        """A bare title with no number and no allowlist entry still stays None."""
        analyzer = TOCAnalyzer(form="10-K")
        assert analyzer._parse_item_from_text(
            "Disclosure Regarding Foreign Jurisdictions that Prevent Inspections"
        ) is None

    def test_workiva_recovers_9c_from_plain_text_label(self):
        """Item 9C's number lives in a non-link cell; recovered from row text."""
        result = TOCAnalyzer(form="10-K")._analyze_workiva_toc(WORKIVA_9C_SIG_HTML)
        assert result.get("part_ii_item_9c") == "a235"

    def test_workiva_recovers_signatures_under_part_iv(self):
        """A text-only 'Part IV' header gives the numberless Signatures its part."""
        result = TOCAnalyzer(form="10-K")._analyze_workiva_toc(WORKIVA_9C_SIG_HTML)
        assert result.get("part_iv_signatures") == "a265"


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

    # edgartools-rbsx: the Workiva agent TOC parser is now a strict superset of
    # the generic parser. It previously dropped Item 9C (whose "Item 9C." label
    # is plain text, not a link) and Signatures (a numberless named section).
    # Assert mapping parity — identical anchors, nothing the generic path finds
    # is lost — and that Item 9C reaches obj.items. Reuses this test's cassette.
    from edgar.documents.utils.toc_analyzer import TOCAnalyzer

    html = filing.html()
    analyzer = TOCAnalyzer(form="10-K")
    generic = analyzer.analyze_toc_structure(html)
    workiva = analyzer.analyze_toc_structure(html, agent='Workiva')
    assert workiva.get('part_ii_item_9c') == generic['part_ii_item_9c']
    assert workiva.get('part_iv_signatures') == generic['part_iv_signatures']
    assert set(generic) - set(workiva) == set()
    assert "Item 9C" in obj.items

    # edgartools-nqzc: the named Signatures section now surfaces in
    # document.sections with its real content (was dropped — a backward
    # end-anchor from an order-400 misclassification emptied its text).
    signatures = secs.get("part_iv_signatures")
    assert signatures is not None
    sig_text = signatures.text()
    assert len(sig_text) > 10_000
    assert "Pursuant to the requirements" in sig_text

    # edgartools-nqzc Layer 1/2: the named-section API surface.
    assert signatures.kind == "named"
    assert secs.named("signatures") is signatures        # typed accessor
    assert obj.signatures is not None                    # report convenience prop
    assert "Pursuant to the requirements" in obj.signatures
    assert "Signatures" not in obj.items                 # not an SEC Item
