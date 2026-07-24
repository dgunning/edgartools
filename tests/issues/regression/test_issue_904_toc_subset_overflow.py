"""Regression test for GitHub Issue #904.

Coeur Mining's FY2025 10-K (CIK 0000215466, accession 0000215466-26-000004)
returned ``TenK['Item 7']`` as 257K chars running from the Item 7 header to the
director signatures at end-of-document, with Items 7A/8/9A/10/11 embedded.
Item 1B similarly returned 317K chars for a one-line "None." stub.

Three gaps combined:

1. ``TOCAnalyzer._is_bold_header`` only checked the element's *own* inline
   style. Coeur's body item headers are unstyled divs whose font weight lives
   on child spans — split so only the *title* span is bold ("Item 7A." at
   weight 400, the title at 700) — so the body-header scan matched zero
   headers. Fix: accept an element whose bold child spans carry at least half
   of its text.

2. Body-header recovery ran only below the 10-K item floor (8) and replaced
   the TOC map wholesale. Coeur's TOC anchored exactly 8 canonical items, so
   recovery never ran — and Item 7, the last anchor, extended to EOF. Fix:
   when core items every 10-K carries are missing, union-merge the body scan
   into the TOC map (TOC wins conflicts).

3. Coeur's one-line Item 1B stub and Item 1C share a single anchor div, so
   Item 1B's end anchor equalled its start anchor — an empty span the slicer
   treats as unbounded (ran to EOF). Fix: the end boundary comes from the
   first following section whose anchor differs.

A fourth, belt-and-braces layer (the successor-header guardrail on
``HybridSectionDetector``) flags any remaining item section that still embeds
a line-anchored header of a later, undetected item — the failure class size
bands can't see (Item 7's band is generous; Item 1B has no band at all).
"""
import re

import pytest
from lxml import html as lxml_html

from edgar.documents import HTMLParser
from edgar.documents.config import ParserConfig
from edgar.documents.document import Section
from edgar.documents.extractors.hybrid_section_detector import HybridSectionDetector
from edgar.documents.nodes import SectionNode
from edgar.documents.utils.toc_analyzer import TOCAnalyzer

pytestmark = pytest.mark.regression


# --- Fix 1: split-span bold headers ------------------------------------------

# Coeur's actual body-header shape: weight lives on child spans, and only the
# title span is bold.
SPLIT_SPAN_HEADER = (
    '<div style="margin-top:14pt;text-align:justify">'
    '<span style="color:#000000;font-family:\'Times New Roman\';font-size:10pt;'
    'font-weight:400">Item 7A.</span>'
    '<span style="font-style:italic;font-weight:400">&#160;&#160;</span>'
    '<span style="color:#000000;font-size:10pt;font-weight:700;'
    'text-decoration:underline">Quantitative and Qualitative Disclosures About Market Risk</span>'
    '</div>'
)


@pytest.mark.fast
def test_bold_header_accepts_split_span_heading():
    """A heading whose bold child spans carry the title must count as bold."""
    el = lxml_html.fromstring(SPLIT_SPAN_HEADER)
    assert TOCAnalyzer._is_bold_header(el, el.tag) is True


@pytest.mark.fast
def test_bold_header_rejects_prose_with_minor_bold_emphasis():
    """A prose line with one bold word must not become a heading."""
    el = lxml_html.fromstring(
        '<div>The results discussed under <span style="font-weight:700">Risk</span>'
        ' factors continued to affect operations through the fiscal year and beyond.</div>'
    )
    assert TOCAnalyzer._is_bold_header(el, el.tag) is False


@pytest.mark.fast
def test_bold_header_own_style_still_recognized():
    """The pre-#904 single-element bold heading keeps matching."""
    el = lxml_html.fromstring('<div style="font-weight:700">Item 1A. Risk Factors</div>')
    assert TOCAnalyzer._is_bold_header(el, el.tag) is True


@pytest.mark.fast
def test_body_scan_finds_split_span_headers():
    """The body-header scan resolves a split-span header to its preceding anchor."""
    html = f"""
    <html><body>
    <div id="anchor_115"></div>
    {SPLIT_SPAN_HEADER}
    <p>We are exposed to market risks.</p>
    </body></html>
    """
    analyzer = TOCAnalyzer(form="10-K")
    mapping = analyzer._analyze_body_item_headers(html)
    assert mapping.get("part_ii_item_7a") == "anchor_115"


# --- Fix 2: union-merge of body headers into a gappy TOC map -----------------

# Coeur's TOC parse: exactly 8 canonical items, ending at Item 7 — clears the
# wholesale-replacement floor while missing 7A/8/9A.
COEUR_LIKE_TOC = {
    "part_i_item_1": "t1", "part_i_item_1a": "t1a", "part_i_item_1b": "t1b",
    "part_i_item_1c": "t1c", "part_i_item_2": "t2", "part_i_item_4": "t4",
    "part_ii_item_5": "t5", "part_ii_item_7": "t7",
}


@pytest.mark.fast
def test_missing_core_items_detects_gappy_map():
    analyzer = TOCAnalyzer(form="10-K")
    assert analyzer._missing_core_items(COEUR_LIKE_TOC) == {"7A", "8", "9A"}


@pytest.mark.fast
def test_missing_core_items_empty_for_complete_map():
    analyzer = TOCAnalyzer(form="10-K")
    complete = dict(COEUR_LIKE_TOC,
                    part_ii_item_7a="x", part_ii_item_8="x", part_ii_item_9a="x")
    assert analyzer._missing_core_items(complete) == set()


@pytest.mark.fast
def test_missing_core_items_scoped_to_10k():
    """The body-header signature is 10-K-shaped; other forms never merge."""
    assert TOCAnalyzer(form="10-Q")._missing_core_items({"part_i_item_1": "a"}) == set()
    assert TOCAnalyzer(form="10-K")._missing_core_items({}) == set()


@pytest.mark.fast
def test_union_merge_fills_missing_items_and_toc_wins_conflicts():
    """Body-scan items fill TOC gaps; items the TOC anchored keep its anchor."""
    body_html = f"""
    <html><body>
    <div id="body_7"></div>
    <div><span style="font-weight:400">Item 7.</span>
         <span style="font-weight:700">Management's Discussion and Analysis</span></div>
    <div id="body_7a"></div>
    {SPLIT_SPAN_HEADER}
    <div id="body_8"></div>
    <div><span style="font-weight:400">Item 8.</span>
         <span style="font-weight:700">Financial Statements and Supplementary Data</span></div>
    </body></html>
    """
    analyzer = TOCAnalyzer(form="10-K")
    analyzer._analyze_generic_toc = lambda html_content, tree=None: dict(COEUR_LIKE_TOC)
    merged = analyzer.analyze_toc_structure(body_html)

    # Gaps filled from the body scan:
    assert merged["part_ii_item_7a"] == "body_7a"
    assert merged["part_ii_item_8"] == "body_8"
    # Conflict: the TOC anchored Item 7 — its anchor wins over the body scan's.
    assert merged["part_ii_item_7"] == "t7"
    # Everything the TOC anchored is still present.
    assert set(COEUR_LIKE_TOC) <= set(merged)


# --- Fix 3: sections sharing one anchor don't run to end-of-document ---------

SHARED_ANCHOR_10K = """
<html><body>
<table>
<tr><td><a href="#a1">Item 1. Business</a></td></tr>
<tr><td><a href="#a1a">Item 1A. Risk Factors</a></td></tr>
<tr><td><a href="#a1bc">Item 1B. Unresolved Staff Comments</a></td></tr>
<tr><td><a href="#a1bc">Item 1C. Cybersecurity</a></td></tr>
<tr><td><a href="#a2">Item 2. Properties</a></td></tr>
<tr><td><a href="#a3">Item 3. Legal Proceedings</a></td></tr>
<tr><td><a href="#a4">Item 4. Mine Safety Disclosures</a></td></tr>
<tr><td><a href="#a5">Item 5. Market for Registrant's Common Equity</a></td></tr>
<tr><td><a href="#a7">Item 7. Management's Discussion and Analysis</a></td></tr>
</table>
<div id="a1"></div><div style="font-weight:700">Item 1. Business</div>
<p>We mine gold and silver at several sites.</p>
<div id="a1a"></div><div style="font-weight:700">Item 1A. Risk Factors</div>
<p>Metals prices fluctuate and may affect our results.</p>
<div id="a1bc"></div><div style="font-weight:700">Item 1B. Unresolved Staff Comments</div>
<p>None.</p>
<div style="font-weight:700">Item 1C. Cybersecurity</div>
<p>Our cybersecurity program manages material risks from threats.</p>
<div id="a2"></div><div style="font-weight:700">Item 2. Properties</div>
<p>Our principal properties are mines located in several states.</p>
<div id="a3"></div><div style="font-weight:700">Item 3. Legal Proceedings</div>
<p>We are party to routine litigation.</p>
<div id="a4"></div><div style="font-weight:700">Item 4. Mine Safety Disclosures</div>
<p>See exhibit 95.1 for mine safety information.</p>
<div id="a5"></div><div style="font-weight:700">Item 5. Market for Registrant's Common Equity</div>
<p>Our common stock trades on the NYSE.</p>
<div id="a7"></div><div style="font-weight:700">Item 7. Management's Discussion and Analysis</div>
<p>The following discussion covers our results of operations.</p>
<p>SIGNATURES-MARKER Pursuant to the requirements of the Securities Exchange Act.</p>
</body></html>
"""


@pytest.mark.fast
def test_shared_anchor_section_does_not_run_to_end_of_document():
    """Item 1B (sharing its anchor with 1C) must end at the next distinct
    anchor, not at end-of-document."""
    doc = HTMLParser(ParserConfig(form="10-K")).parse(SHARED_ANCHOR_10K)
    sections = HybridSectionDetector(doc, form="10-K").detect_sections()

    item_1b = sections.get("part_i_item_1b")
    assert item_1b is not None, f"got: {sorted(sections.keys())}"
    text = item_1b.text() or ""
    assert "None." in text
    # Bounded at Item 2's anchor — the tail of the filing must not leak in.
    assert "SIGNATURES-MARKER" not in text
    assert "routine litigation" not in text


# --- Layer 4: successor-header guardrail --------------------------------------

def _make_10k_detector():
    doc = HTMLParser(ParserConfig(form="10-K")).parse(
        "<html><body><p>placeholder</p></body></html>"
    )
    return HybridSectionDetector(doc, form="10-K")


def _toc_section(name, part, item, text, method="toc"):
    return Section(
        name=name, title=name, node=SectionNode(section_name=name),
        start_offset=0, end_offset=len(text), confidence=0.95,
        detection_method=method, part=part, item=item,
        _text_extractor=lambda _name=None, _t=text, **kwargs: _t,
    )


@pytest.mark.fast
def test_successor_guardrail_flags_embedded_undetected_item():
    """An Item 8 embedding a line-anchored 'Item 9.' header (Item 9 not in the
    map) is flagged and downgraded — the Coeur failure class."""
    filler = "Consolidated statements of operations follow. " * 500
    text = filler + "\nItem 9.\xa0\xa0Changes in and Disagreements with Accountants\n\nNone.\n"
    sections = {
        "part_ii_item_8": _toc_section("part_ii_item_8", "II", "8", text),
    }
    result = _make_10k_detector()._apply_successor_guardrail(sections)
    flagged = result["part_ii_item_8"]
    assert any("Item 9" in w for w in flagged.warnings), flagged.warnings
    assert flagged.confidence == 0.5


@pytest.mark.fast
def test_successor_guardrail_ignores_detected_successors():
    """No flag when the embedded item exists as its own section."""
    filler = "Consolidated statements of operations follow. " * 500
    text = filler + "\nItem 9.\xa0Changes in and Disagreements with Accountants\n"
    sections = {
        "part_ii_item_8": _toc_section("part_ii_item_8", "II", "8", text),
        "part_ii_item_9": _toc_section("part_ii_item_9", "II", "9", "None."),
    }
    result = _make_10k_detector()._apply_successor_guardrail(sections)
    assert result["part_ii_item_8"].warnings == []
    assert result["part_ii_item_8"].confidence == 0.95


@pytest.mark.fast
def test_successor_guardrail_ignores_mini_toc_runs():
    """A tight run of item headers (an embedded TOC/index page) is not an
    absorbed-item signal."""
    filler = "Business overview text. " * 800
    mini_toc = "\nItem 10.\xa0Directors\nItem 11.\xa0Executive Compensation\nItem 12.\xa0Security Ownership\n"
    sections = {
        "part_i_item_1": _toc_section("part_i_item_1", "I", "1", filler + mini_toc),
    }
    result = _make_10k_detector()._apply_successor_guardrail(sections)
    assert result["part_i_item_1"].warnings == []


@pytest.mark.fast
def test_successor_guardrail_skips_small_and_non_toc_sections():
    small = "Item 9.\xa0Changes.\n" + "text " * 10
    sections = {
        "part_ii_item_8": _toc_section("part_ii_item_8", "II", "8", small),
        "mda": _toc_section("mda", "II", "7",
                            ("prose " * 4000) + "\nItem 9.\xa0Changes.\n", method="pattern"),
    }
    result = _make_10k_detector()._apply_successor_guardrail(sections)
    assert result["part_ii_item_8"].warnings == []
    assert result["mda"].warnings == []


@pytest.mark.fast
def test_successor_guardrail_ignores_midline_cross_references():
    """'see Item 9A below' mid-sentence must not flag."""
    text = ("Our controls are described elsewhere; see Item 9A below for detail. "
            * 400)
    sections = {
        "part_ii_item_8": _toc_section("part_ii_item_8", "II", "8", text),
    }
    result = _make_10k_detector()._apply_successor_guardrail(sections)
    assert result["part_ii_item_8"].warnings == []


# --- End-to-end: Coeur Mining 10-K under VCR ----------------------------------

@pytest.mark.network
@pytest.mark.vcr
def test_coeur_item7_bounded_and_body_items_recovered():
    """Coeur 10-K: Item 7 stops at Item 7A; 7A/8/9A exist; Item 1B is a stub."""
    from edgar import get_by_accession_number

    tenk = get_by_accession_number("0000215466-26-000004").obj()
    sections = tenk.document.sections

    # The body-header items missing from the TOC are recovered.
    for key in ("part_ii_item_7a", "part_ii_item_8", "part_ii_item_9a"):
        assert key in sections, f"{key} missing; got {sorted(sections.keys())}"
        assert sections[key].detection_method == "toc"

    # Item 7 is the MD&A only — bounded at Item 7A, not end-of-document.
    item7 = tenk["Item 7"]
    assert item7.lstrip().startswith("Item 7.")
    assert 60_000 < len(item7) < 150_000, len(item7)  # was 257,440 overflowed
    for successor in ("Item 7A", "Item 8", "Item 9A"):
        assert not re.search(rf"(?m)^\s*{successor}\s*\.", item7), (
            f"{successor} header embedded in Item 7"
        )
    # Ground truth: the MD&A ends with the FY guidance table, not signatures.
    assert "Director" not in item7[-500:]

    # Item 1B is the one-line stub plus at most the adjacent 1C (shared
    # anchor), not 317K of the document tail.
    item_1b = sections["part_i_item_1b"].text()
    assert "None." in item_1b[:200]
    assert len(item_1b) < 10_000, len(item_1b)
