"""Regression gate for routing DEF 14A / PRE 14A proxy sections through the TOC
engine (edgartools-x341 / gh-867; the proxy title-engine flip).

Proxies share 424B/S-1's title-based shape, so with ``DEF14A_SCHEMA.title_based``
flipped on the document.py router sends anchored proxies through the TOC-first
hybrid detector (with heading+pattern as a universal fallback) instead of the
weak pattern path. This mirrors ``tests/test_s1_section_flip_gate.py`` for the
Schedule 14A / Reg S-K vocabulary, and locks in the flip so it cannot silently
regress to ``title_based=False``.

The invariants are property-based, not byte-snapshots: the right sections, no
cross-section bleed, the governance/compensation sections that distinguish a
proxy from a prospectus, and the flat-proxy heading fallback. The header-only
sliver guardrail that made the flip clean has its own unit test
(``tests/test_proxy_header_only_guardrail.py``); here it is exercised end-to-end.
"""
from edgar.documents import parse_html
from edgar.documents.config import ParserConfig
from edgar.documents.form_schema import get_form_schema


# An anchored proxy with a real Table of Contents: governance + compensation +
# audit + ownership sections (the bleed-prone, TOC-rich shape the flip improves),
# plus a divider-style "Executive Compensation" entry whose body is just its
# heading (absorbed by the CD&A that follows) — the header-only sliver the
# guardrail must drop rather than emit as a mislabeled 22-char section.
_ANCHORED_PROXY = """
<html><body>
<div><b>TABLE OF CONTENTS</b><table>
<tr><td><a href="#sum">Proxy Summary</a></td><td><a href="#sum">1</a></td></tr>
<tr><td><a href="#prop">Proposal No. 1: Election of Directors</a></td><td><a href="#prop">5</a></td></tr>
<tr><td><a href="#cg">Corporate Governance</a></td><td><a href="#cg">12</a></td></tr>
<tr><td><a href="#ec">Executive Compensation</a></td><td><a href="#ec">30</a></td></tr>
<tr><td><a href="#cda">Compensation Discussion and Analysis</a></td><td><a href="#cda">31</a></td></tr>
<tr><td><a href="#audit">Audit Matters</a></td><td><a href="#audit">60</a></td></tr>
<tr><td><a href="#own">Security Ownership</a></td><td><a href="#own">70</a></td></tr>
</table></div>
<div id="sum"><b>Proxy Summary</b><p>MARKER_SUM: We are holding our annual meeting of stockholders.</p></div>
<div id="prop"><b>Proposal No. 1: Election of Directors</b>
<p>MARKER_PROP: The Board recommends a vote FOR each nominee.</p></div>
<div id="cg"><b>Corporate Governance</b><p>MARKER_CG: Our board is led by an independent chair.</p></div>
<div id="ec"><b>Executive Compensation</b></div>
<div id="cda"><b>Compensation Discussion and Analysis</b>
<p>MARKER_CDA: Our compensation program ties pay to performance.</p></div>
<div id="audit"><b>Audit Matters</b><p>MARKER_AUDIT: The Audit Committee oversees our independent auditors.</p></div>
<div id="own"><b>Security Ownership</b><p>MARKER_OWN: The following table shows beneficial ownership.</p></div>
</body></html>
"""

# A flat proxy (no machine-readable TOC) — headings only. The flip must keep
# detecting these via the heading/pattern fallback layer.
_FLAT_PROXY = """
<html><body>
<h2>Corporate Governance</h2><p>MARKER_CG: Our board is led by an independent chair.</p>
<h2>Compensation Discussion and Analysis</h2><p>MARKER_CDA: We tie pay to performance.</p>
<h2>Audit Matters</h2><p>MARKER_AUDIT: The Audit Committee oversees our auditors.</p>
<h2>Security Ownership</h2><p>MARKER_OWN: Beneficial ownership of our stock.</p>
</body></html>
"""

_EXPECTED_ANCHORED = {
    "proxy_summary", "voting_proposals", "corporate_governance",
    "compensation_discussion_and_analysis", "audit_matters", "security_ownership",
}
_EXPECTED_FLAT = {
    "corporate_governance", "compensation_discussion_and_analysis",
    "audit_matters", "security_ownership",
}


def _sections(html, form="DEF 14A"):
    return parse_html(html, ParserConfig(form=form)).sections


def test_def14a_schema_is_title_based():
    """The flip itself — both proxy forms route through the title engine."""
    assert get_form_schema("DEF 14A").title_based
    assert get_form_schema("PRE 14A").title_based


def test_anchored_proxy_sections_detected():
    keys = set(_sections(_ANCHORED_PROXY).keys())
    missing = _EXPECTED_ANCHORED - keys
    assert not missing, f"anchored proxy lost sections: {missing} (have {keys})"


def test_proxy_governance_sections_present():
    """Corporate Governance + CD&A + Audit — the sections that distinguish a
    proxy from a 424B/S-1 prospectus."""
    keys = set(_sections(_ANCHORED_PROXY).keys())
    assert {"corporate_governance", "compensation_discussion_and_analysis", "audit_matters"} <= keys


def test_header_only_sliver_not_emitted():
    """The divider 'Executive Compensation' entry (body absorbed by CD&A) must be
    dropped by the guardrail, not emitted as a mislabeled sliver."""
    secs = _sections(_ANCHORED_PROXY)
    if "executive_compensation" in secs:
        # If present at all, it must carry real content — never a bare heading.
        assert len(secs["executive_compensation"].text().strip()) >= 64


def test_no_cross_section_bleed():
    """Each section holds its own marker and not the next section's."""
    secs = _sections(_ANCHORED_PROXY)
    cg = secs["corporate_governance"].text()
    assert "MARKER_CG" in cg
    assert "MARKER_AUDIT" not in cg and "MARKER_OWN" not in cg


def test_flat_proxy_sections_detected():
    keys = set(_sections(_FLAT_PROXY).keys())
    missing = _EXPECTED_FLAT - keys
    assert not missing, f"flat proxy lost sections: {missing} (have {keys})"
