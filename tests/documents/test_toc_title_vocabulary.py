"""TOC engine title-vocabulary capability for prospectuses (edgartools-llmp.3).

Phase 3 increment 1: TOCAnalyzer learns to key a title-based form's TOC
(424B prospectuses) by matching link text against FormSchema.section_patterns,
so SECSectionExtractor — the anchor-first engine — can slice prospectus sections
with correct boundaries. This is gated on FormSchema.title_based, so Item forms
(10-K/10-Q/8-K/20-F) never reach it and are unaffected.

These tests exercise the engine directly (no router change): document.sections
still routes 424B to the pattern extractor until the Phase 3 flip. They lock the
new capability that the flip will then surface through the public API.
"""
from edgar.documents import parse_html
from edgar.documents.config import ParserConfig
from edgar.documents.extractors.toc_section_extractor import SECSectionExtractor
from edgar.documents.form_schema import get_form_schema


_ANCHORED_424B = """
<html><body>
<div><b>TABLE OF CONTENTS</b><table>
<tr><td><a href="#uop">Use of Proceeds</a></td><td><a href="#uop">12</a></td></tr>
<tr><td><a href="#dil">Dilution</a></td><td><a href="#dil">18</a></td></tr>
<tr><td><a href="#uw">Underwriting</a></td><td><a href="#uw">25</a></td></tr>
</table></div>
<div id="uop"><b>Use of Proceeds</b><p>MARKER_UOP net proceeds.</p>
<h3>Anticipated Allocation</h3><p>MARKER_UOP_TAIL debt.</p></div>
<div id="dil"><b>Dilution</b><p>MARKER_DIL diluted.</p></div>
<div id="uw"><b>Underwriting</b><p>MARKER_UW purchase.</p></div>
</body></html>
"""


def _extractor(html, form="424B5"):
    return SECSectionExtractor(parse_html(html, ParserConfig(form=form)), form=form)


def test_424b_schema_is_title_based():
    schema = get_form_schema("424B5")
    assert schema.title_based
    assert schema.match_section_pattern("Use of Proceeds") == "use_of_proceeds"
    assert schema.match_section_pattern("Underwriting") == "underwriting"
    assert schema.match_section_pattern("Totally Unrelated Heading") is None
    # 10-K is item-based, never title-based.
    assert not get_form_schema("10-K").title_based


def test_toc_engine_detects_prospectus_sections():
    ext = _extractor(_ANCHORED_424B)
    assert set(ext.get_available_sections()) == {"use_of_proceeds", "dilution", "underwriting"}


def test_toc_engine_boundaries_have_no_bleed():
    ext = _extractor(_ANCHORED_424B)
    uop = ext.get_section_text("use_of_proceeds") or ""
    assert "MARKER_UOP" in uop and "MARKER_UOP_TAIL" in uop  # own body kept
    assert "MARKER_DIL" not in uop and "MARKER_UW" not in uop  # neighbours excluded
    assert "MARKER_UW" not in (ext.get_section_text("dilution") or "")


def test_toc_link_with_trailing_page_number_still_matches():
    """Real TOCs put the page number in the link text; it must not block the match."""
    html = _ANCHORED_424B.replace(
        '<a href="#uop">Use of Proceeds</a>', '<a href="#uop">Use of Proceeds .... 12</a>'
    )
    ext = _extractor(html)
    assert "use_of_proceeds" in ext.get_available_sections()


# Body order here is Dilution THEN Use of Proceeds — the reverse of their order in
# the 424B section-patterns vocabulary. Sections must be bounded by physical
# document position, not declaration order; otherwise Dilution's end anchor points
# at an earlier body position and it over-captures (the bug real ABNB 424B4
# surfaced: a section ballooning to ~540KB).
_OUT_OF_ORDER_424B = """
<html><body>
<div><b>TABLE OF CONTENTS</b><table>
<tr><td><a href="#dil">Dilution</a></td></tr>
<tr><td><a href="#uop">Use of Proceeds</a></td></tr>
</table></div>
<div id="dil"><b>Dilution</b><p>MARKER_DIL diluted.</p></div>
<div id="uop"><b>Use of Proceeds</b><p>MARKER_UOP net proceeds.</p></div>
</body></html>
"""


def test_sections_bounded_by_document_order_not_declaration_order():
    ext = _extractor(_OUT_OF_ORDER_424B)
    dil = ext.get_section_text("dilution") or ""
    # Dilution comes first in the body; it must stop at Use of Proceeds, not run
    # backwards/over it.
    assert "MARKER_DIL" in dil
    assert "MARKER_UOP" not in dil, "Dilution over-captured Use of Proceeds (declaration-order bug)"


# TOC lists a section we have no vocabulary for ("Glossary of Terms") between two
# we do. Use of Proceeds must stop at the glossary's anchor, not absorb it (the
# gap the real ABNB 424B4 exposed: a section swallowing the untracked body + the
# financial statements). ("Management" used to be the untracked example here, but
# 424B now shares S-1's full prospectus vocabulary and surfaces it as a section —
# gh-878; a glossary is genuinely outside the vocabulary.)
_GAP_424B = """
<html><body>
<div><b>TABLE OF CONTENTS</b><table>
<tr><td><a href="#uop">Use of Proceeds</a></td></tr>
<tr><td><a href="#glos">Glossary of Terms</a></td></tr>
<tr><td><a href="#uw">Underwriting</a></td></tr>
</table></div>
<div id="uop"><b>Use of Proceeds</b><p>MARKER_UOP net proceeds.</p></div>
<div id="glos"><b>Glossary of Terms</b><p>MARKER_GLOS defined terms.</p></div>
<div id="uw"><b>Underwriting</b><p>MARKER_UW purchase.</p></div>
</body></html>
"""


def test_detected_section_does_not_absorb_untracked_gap_section():
    ext = _extractor(_GAP_424B)
    # "Glossary of Terms" isn't in the prospectus vocabulary, so it isn't surfaced
    # as a section...
    assert "glossary_of_terms" not in [s.lower() for s in ext.get_available_sections()]
    # ...but Use of Proceeds must still stop at it, not swallow its body.
    uop = ext.get_section_text("use_of_proceeds") or ""
    assert "MARKER_UOP" in uop
    assert "MARKER_GLOS" not in uop, "Use of Proceeds absorbed the untracked Glossary section"
    assert "MARKER_UW" not in uop
