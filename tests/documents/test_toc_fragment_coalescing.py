"""Fragmented / divider-tab proxy TOC handling for title-based sections (edgartools-zas6).

JPMorgan-style proxies break a per-<a> TOC strategy two more ways beyond the
hierarchy handled in test_toc_hierarchy_bounding.py:

1. **Fragmented entries** — one logical TOC entry is split across several <a>
   elements that all target the same anchor ("PROPOSAL NO." / "1" / "Election of
   directors", and even a split word "E" + "ngagement"), with running-header and
   page-number digits as their own links. Matching each fragment alone keys a
   section on a fragment or drops the proposal number. The parser coalesces
   consecutive same-anchor links into one logical entry, strips leading/trailing
   page digits, and matches the vocabulary once on the whole title.

2. **Divider tabs on a flat TOC** — JPMorgan's TOC carries no indentation; it marks
   its parts ("Corporate governance", "Executive compensation") as bold text on a
   filled background while nested subsections are plain. Those tabs head the
   outline, so a section under a divider must run to the next divider, absorbing
   the proposals and subsections nested beneath it.

Offline tests driving TOCAnalyzer directly with synthetic HTML; the DEF 14A flip
stays held until this lands, so the parser is exercised through an inline
title-based schema.
"""
import dataclasses

import pytest

from edgar.documents.form_schema import DEF14A_SCHEMA
from edgar.documents.utils.toc_analyzer import TOCAnalyzer


@pytest.fixture
def proxy_analyzer():
    analyzer = TOCAnalyzer(form="DEF 14A")
    analyzer.schema = dataclasses.replace(DEF14A_SCHEMA, title_based=True)
    return analyzer


# A TOC whose first entry is fragmented across four <a> elements all pointing at
# #p1: the label, the proposal number, the title, and the page number. Only the
# coalesced title "PROPOSAL NO. 1 Election of Directors" matches the vocabulary.
_FRAGMENTED = """
<html><body>
<div><b>TABLE OF CONTENTS</b>
<table>
<tr><td>
  <a href="#p1">PROPOSAL NO.</a><a href="#p1">1</a><a href="#p1">Election of Directors</a><a href="#p1">7</a>
</td></tr>
<tr><td><a href="#audit">Audit Matters</a><a href="#audit">40</a></td></tr>
</table></div>
<div id="p1"><b>Election of Directors</b><p>P1_BODY the nominees stand for election.</p></div>
<div id="audit"><b>Audit Matters</b><p>AUDIT_BODY auditor information.</p></div>
</body></html>
"""


def test_fragmented_entry_coalesces_and_matches(proxy_analyzer):
    """The four-fragment first entry keys to voting_proposals (its number is kept,
    not stripped as a page reference) and anchors to #p1."""
    mapping = proxy_analyzer.analyze_toc_structure(_FRAGMENTED)
    assert mapping.get("voting_proposals") == "p1"
    assert mapping.get("audit_matters") == "audit"


# Leading running-header digits ("202" + "6") and a trailing page number ("1")
# wrap the real title; the entry must still resolve to proxy_summary.
_HEADER_DIGITS = """
<html><body>
<div><b>TABLE OF CONTENTS</b>
<table>
<tr><td><a href="#sum">202</a><a href="#sum">6</a><a href="#sum">Proxy Summary</a><a href="#sum">1</a></td></tr>
<tr><td><a href="#gov">Corporate Governance</a><a href="#gov">7</a></td></tr>
</table></div>
<div id="sum"><b>Proxy Summary</b><p>SUM_BODY highlights.</p></div>
<div id="gov"><b>Corporate Governance</b><p>GOV_BODY governance.</p></div>
</body></html>
"""


def test_leading_and_trailing_page_digits_stripped(proxy_analyzer):
    mapping = proxy_analyzer.analyze_toc_structure(_HEADER_DIGITS)
    assert mapping.get("proxy_summary") == "sum"
    assert mapping.get("corporate_governance") == "gov"


# A FLAT TOC (no indentation) whose parts are bold + background-filled divider
# tabs, with plain nested subsections between them — the JPMorgan shape. The
# divider depth must bound corporate_governance at the next divider
# (executive_compensation), absorbing the nested proposal and subsection.
_DIVIDER = """
<html><body>
<div><b>TABLE OF CONTENTS</b>
<table>
<tr><td style="font-weight:700;background-color:#f4efe7"><a href="#gov">Corporate governance</a></td></tr>
<tr><td><a href="#prop1">PROPOSAL 1: Election of directors</a></td></tr>
<tr><td><a href="#boardgov">Board governance</a></td></tr>
<tr><td><a href="#dircomp">Director compensation</a></td></tr>
<tr><td style="font-weight:700;background-color:#f4efe7"><a href="#ec">Executive compensation</a></td></tr>
<tr><td><a href="#cda">Compensation discussion and analysis</a></td></tr>
<tr><td style="font-weight:700;background-color:#f4efe7"><a href="#audit">Audit matters</a></td></tr>
</table></div>
<div id="gov"><b>Corporate governance</b><p>GOV_BODY governance opening.</p></div>
<div id="prop1"><b>PROPOSAL 1: Election of directors</b><p>PROP1_BODY the nominees.</p></div>
<div id="boardgov"><b>Board governance</b><p>BOARDGOV_BODY committees.</p></div>
<div id="dircomp"><b>Director compensation</b><p>DIRCOMP_BODY fees.</p></div>
<div id="ec"><b>Executive compensation</b><p>EC_BODY pay overview.</p></div>
<div id="cda"><b>Compensation discussion and analysis</b><p>CDA_BODY analysis.</p></div>
<div id="audit"><b>Audit matters</b><p>AUDIT_BODY auditor.</p></div>
</body></html>
"""


def test_divider_tab_bounds_at_next_divider(proxy_analyzer):
    """corporate_governance is a divider tab, so it runs to the next divider
    (executive_compensation), absorbing the nested proposal, board-governance, and
    director-compensation entries rather than stopping at the proposal."""
    proxy_analyzer.analyze_toc_structure(_DIVIDER)
    assert proxy_analyzer.title_section_end("corporate_governance") == "ec"
    # The nested director_compensation is still its own (overlapping) subsection.
    assert proxy_analyzer.title_section_end("director_compensation") == "ec"
    # executive_compensation (divider) runs to the next divider, audit_matters,
    # absorbing the nested CD&A.
    assert proxy_analyzer.title_section_end("executive_compensation") == "audit"


def test_divider_section_absorbs_nested_body(proxy_analyzer):
    """The absorbed children's body text is reachable through the divider section."""
    import edgar.documents.form_schema as fs
    flipped = dataclasses.replace(fs.DEF14A_SCHEMA, title_based=True)
    orig = fs.DEF14A_SCHEMA
    fs.DEF14A_SCHEMA = flipped
    fs._SCHEMAS["DEF 14A"] = flipped
    try:
        from edgar.documents import parse_html
        from edgar.documents.config import ParserConfig
        doc = parse_html(_DIVIDER, ParserConfig(form="DEF 14A"))
        gov = doc.sections.get("corporate_governance")
        assert gov is not None
        text = gov.text()
        assert "GOV_BODY" in text
        assert "BOARDGOV_BODY" in text  # nested subsection absorbed
        assert "DIRCOMP_BODY" in text   # nested matched subsection absorbed
        assert "EC_BODY" not in text     # stops at the next divider
    finally:
        fs.DEF14A_SCHEMA = orig
        fs._SCHEMAS["DEF 14A"] = orig


def test_is_divider_requires_bold_and_background():
    from lxml import html as lhtml

    def first_a(html):
        return next(lhtml.fromstring(html).iter("a"))

    bold_bg = first_a('<td style="font-weight:700;background-color:#eee"><a href="#x">t</a></td>')
    assert TOCAnalyzer._is_divider(bold_bg)
    # Bold alone (no fill) is an ordinary emphasised heading, not a divider tab.
    bold_only = first_a('<td style="font-weight:700"><a href="#x">t</a></td>')
    assert not TOCAnalyzer._is_divider(bold_only)
    # A white background is page chrome, not a tab.
    white = first_a('<td style="font-weight:bold;background:#ffffff"><a href="#x">t</a></td>')
    assert not TOCAnalyzer._is_divider(white)
