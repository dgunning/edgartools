"""Hierarchical-TOC sibling bounding for title-based proxy sections (edgartools-gb99).

A flat "bound at the next TOC entry" strategy works on single-level prospectus/S-1
TOCs but slices proxy sections to slivers: real DEF 14A TOCs nest sub-entries under
a section (KO's "Report of the Audit Committee" sits under "Audit Matters"), and the
sub-entry's own vocabulary match becomes the parent's end boundary — KO
``audit_matters`` collapsed to 13 chars. The title TOC parser now reads each entry's
indentation depth and bounds a section at the next *sibling-or-shallower* entry,
absorbing its deeper children. It also keys a section to its shallowest-indented
match, so Apple's ``executive_compensation`` resolves to the real section, not the
"Executive Compensation" highlight nested inside the Proxy Summary.

These are offline tests driving ``TOCAnalyzer`` directly with synthetic HTML; the
DEF 14A flip itself stays held (``title_based=False``) until the fragmented-TOC work
(edgartools-zas6) also lands, so the parser is exercised through a title-based schema
constructed inline rather than through ``Document.sections``.
"""
import dataclasses

import pytest

from edgar.documents.form_schema import DEF14A_SCHEMA
from edgar.documents.utils.toc_analyzer import TOCAnalyzer


@pytest.fixture
def proxy_analyzer():
    """A TOCAnalyzer whose DEF 14A schema is flipped title-based for the test."""
    analyzer = TOCAnalyzer(form="DEF 14A")
    analyzer.schema = dataclasses.replace(DEF14A_SCHEMA, title_based=True)
    return analyzer


# A proxy TOC where each major section is followed by a deeper-indented sub-entry,
# and the audit sub-entry ("Report of the Audit Committee") itself matches the
# audit vocabulary — the exact KO failure shape. Indentation (padding-left) carries
# the hierarchy: top-level = 0pt, sub-entries = 20pt.
_HIERARCHICAL = """
<html><body>
<div><b>TABLE OF CONTENTS</b>
<table>
<tr><td style="padding-left:0pt"><a href="#gov">Corporate Governance</a></td></tr>
<tr><td style="padding-left:20pt"><a href="#govsub">Board Independence</a></td></tr>
<tr><td style="padding-left:0pt"><a href="#audit">Audit Matters</a></td></tr>
<tr><td style="padding-left:20pt"><a href="#auditrep">Report of the Audit Committee</a></td></tr>
<tr><td style="padding-left:20pt"><a href="#auditfees">Independent Accountant Fees</a></td></tr>
<tr><td style="padding-left:0pt"><a href="#own">Security Ownership</a></td></tr>
</table></div>
<div id="gov"><b>Corporate Governance</b><p>GOV_BODY governance narrative.</p></div>
<div id="govsub"><b>Board Independence</b><p>GOVSUB_BODY independence details.</p></div>
<div id="audit"><b>Audit Matters</b><p>AUDIT_BODY audit overview.</p></div>
<div id="auditrep"><b>Report of the Audit Committee</b><p>AUDITREP_BODY the committee reports.</p></div>
<div id="auditfees"><b>Independent Accountant Fees</b><p>AUDITFEES_BODY fees paid.</p></div>
<div id="own"><b>Security Ownership</b><p>OWN_BODY beneficial ownership.</p></div>
</body></html>
"""


def test_section_bounds_at_sibling_not_descendant(proxy_analyzer):
    """audit_matters must run past its own deeper sub-entries to the next
    top-level sibling (Security Ownership), not stop at the audit sub-entry."""
    mapping = proxy_analyzer.analyze_toc_structure(_HIERARCHICAL)

    assert mapping.get("audit_matters") == "audit"
    # End is the next SIBLING (Security Ownership), not the descendant audit
    # sub-entry that previously sliced this to ~13 chars.
    assert proxy_analyzer.title_section_end("audit_matters") == "own"


def test_corporate_governance_absorbs_its_subentry(proxy_analyzer):
    """A section absorbs its deeper child and stops at the next sibling."""
    proxy_analyzer.analyze_toc_structure(_HIERARCHICAL)
    # Corporate Governance's only child (Board Independence, 20pt) is a
    # descendant, so the section ends at the next top-level entry: Audit Matters.
    assert proxy_analyzer.title_section_end("corporate_governance") == "audit"


# Apple shape: a key appears first as a deeper highlight nested in the Proxy
# Summary, then again as the real top-level section. Shallowest match must win.
_SUMMARY_NESTED = """
<html><body>
<div><b>TABLE OF CONTENTS</b>
<table>
<tr><td style="padding-left:0pt"><a href="#sum">Proxy Statement Summary</a></td></tr>
<tr><td style="padding-left:20pt"><a href="#sumec">Executive Compensation</a></td></tr>
<tr><td style="padding-left:20pt"><a href="#sumgov">Corporate Governance</a></td></tr>
<tr><td style="padding-left:0pt"><a href="#ec">Executive Compensation</a></td></tr>
<tr><td style="padding-left:0pt"><a href="#own">Security Ownership</a></td></tr>
</table></div>
<div id="sum"><b>Proxy Statement Summary</b><p>SUM_BODY a highlight reel.</p></div>
<div id="sumec"><b>Executive Compensation</b><p>SUMEC tiny highlight blurb.</p></div>
<div id="sumgov"><b>Corporate Governance</b><p>SUMGOV tiny highlight blurb.</p></div>
<div id="ec"><b>Executive Compensation</b><p>EC_BODY the real compensation section.</p></div>
<div id="own"><b>Security Ownership</b><p>OWN_BODY beneficial ownership.</p></div>
</body></html>
"""


def test_shallowest_match_wins_over_summary_highlight(proxy_analyzer):
    """executive_compensation keys to the top-level section (#ec, 0pt), not the
    highlight nested in the Proxy Summary (#sumec, 20pt) that occurs first."""
    mapping = proxy_analyzer.analyze_toc_structure(_SUMMARY_NESTED)
    assert mapping.get("executive_compensation") == "ec"


# A flat single-level TOC (prospectus/S-1 shape, and WMT-style flat proxies):
# every entry at the same indent. The sibling rule must collapse to the prior
# "bound at the next entry" behaviour — no regression.
_FLAT = """
<html><body>
<div><b>TABLE OF CONTENTS</b>
<table>
<tr><td style="padding-left:0pt"><a href="#gov">Corporate Governance</a></td></tr>
<tr><td style="padding-left:0pt"><a href="#audit">Audit Matters</a></td></tr>
<tr><td style="padding-left:0pt"><a href="#own">Security Ownership</a></td></tr>
</table></div>
<div id="gov"><b>Corporate Governance</b><p>GOV_BODY.</p></div>
<div id="audit"><b>Audit Matters</b><p>AUDIT_BODY.</p></div>
<div id="own"><b>Security Ownership</b><p>OWN_BODY.</p></div>
</body></html>
"""


def test_flat_toc_bounds_at_next_entry(proxy_analyzer):
    """On a flat TOC every entry is a sibling, so each section still ends at the
    immediately following entry — unchanged from the pre-gb99 behaviour."""
    proxy_analyzer.analyze_toc_structure(_FLAT)
    assert proxy_analyzer.title_section_end("corporate_governance") == "audit"
    assert proxy_analyzer.title_section_end("audit_matters") == "own"
    assert proxy_analyzer.title_section_end("security_ownership") is None  # runs to EOF


# --- _toc_indent unit coverage: the CSS the proxies actually use --------------

def _a(style_chain):
    """Build a nested <a> whose ancestors carry the given styles (innermost
    first), parse it, and return the <a> element."""
    from lxml import html as lhtml
    html = "".join(f'<div style="{s}">' for s in reversed(style_chain))
    html += '<a href="#x">t</a>' + "</div>" * len(style_chain)
    return lhtml.fromstring(html).iter("a").__next__()


def test_toc_indent_reads_margin_shorthand_left():
    # KO sub-entries express indent via the 4-value margin shorthand's left slot.
    el = _a(["margin:0pt 0pt 0pt 5.75pt"])
    assert TOCAnalyzer._toc_indent(el) == pytest.approx(5.75)


def test_toc_indent_nets_hanging_indent_to_zero():
    # padding-left:7.2pt + text-indent:-7.2pt is a hanging indent; it renders flush.
    el = _a(["padding-left:7.2pt;text-indent:-7.2pt"])
    assert TOCAnalyzer._toc_indent(el) == pytest.approx(0.0)


def test_toc_indent_sums_ancestor_offsets():
    el = _a(["padding-left:9pt", "padding-left:36pt"])
    assert TOCAnalyzer._toc_indent(el) == pytest.approx(45.0)
