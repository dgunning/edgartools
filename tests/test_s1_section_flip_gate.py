"""Regression gate for routing S-1 registration-statement sections through the
TOC engine (edgartools-ybth / gh-866; Phase 3 flip extended to S-1).

S-1 prospectuses share 424B's title-based shape, so the document.py router now
sends anchored S-1s through the TOC-first hybrid detector (with heading+pattern
as a universal fallback) instead of straight to the weak pattern extractor —
dissolving the same prospectus content-bleed by construction. This mirrors
``tests/test_prospectus_section_flip_gate.py`` for the S-1 vocabulary.

The invariants are property-based, not byte-snapshots: the gate asserts
structural correctness (right sections, no cross-section bleed, stable keys, the
registration-specific Business/Management sections that distinguish an S-1 from a
424B) rather than identical text.
"""
from edgar.documents import parse_html
from edgar.documents.config import ParserConfig

# An S-1 with a real anchored Table of Contents (the bleed-prone, TOC-rich shape
# the flip most improves) plus an internal sub-heading inside Use of Proceeds and
# the registration-specific Business/Management sections a 424B usually omits.
_ANCHORED_S1 = """
<html><body>
<div><b>TABLE OF CONTENTS</b><table>
<tr><td><a href="#sum">Prospectus Summary</a></td><td><a href="#sum">1</a></td></tr>
<tr><td><a href="#rf">Risk Factors</a></td><td><a href="#rf">10</a></td></tr>
<tr><td><a href="#uop">Use of Proceeds</a></td><td><a href="#uop">30</a></td></tr>
<tr><td><a href="#biz">Business</a></td><td><a href="#biz">45</a></td></tr>
<tr><td><a href="#mgmt">Management</a></td><td><a href="#mgmt">70</a></td></tr>
<tr><td><a href="#uw">Underwriting</a></td><td><a href="#uw">90</a></td></tr>
</table></div>
<div id="sum"><b>Prospectus Summary</b><p>MARKER_SUM: We are an emerging growth company.</p></div>
<div id="rf"><b>Risk Factors</b><p>MARKER_RF: Investing involves risk.</p></div>
<div id="uop"><b>Use of Proceeds</b>
<p>MARKER_UOP: We intend to use the net proceeds for general corporate purposes.</p>
<h3>Anticipated Allocation</h3>
<p>MARKER_UOP_TAIL: A portion may be allocated to research and development.</p>
</div>
<div id="biz"><b>Business</b><p>MARKER_BIZ: We design and sell widgets.</p></div>
<div id="mgmt"><b>Management</b><p>MARKER_MGMT: Our directors and executive officers.</p></div>
<div id="uw"><b>Underwriting</b><p>MARKER_UW: The underwriters have agreed to purchase the shares.</p></div>
</body></html>
"""

# A flat S-1 (no machine-readable TOC) — headings only. The flip must keep
# detecting these via the heading/pattern fallback layer.
_FLAT_S1 = """
<html><body>
<h2>Risk Factors</h2><p>MARKER_RF: Investing involves risk.</p>
<h2>Use of Proceeds</h2><p>MARKER_UOP: We intend to use the net proceeds.</p>
<h2>Business</h2><p>MARKER_BIZ: We design and sell widgets.</p>
<h2>Underwriting</h2><p>MARKER_UW: The underwriters have agreed to purchase.</p>
</body></html>
"""

_EXPECTED_ANCHORED = {"summary", "risk_factors", "use_of_proceeds", "business", "management", "underwriting"}
_EXPECTED_FLAT = {"risk_factors", "use_of_proceeds", "business", "underwriting"}


def _sections(html, form="S-1"):
    return parse_html(html, ParserConfig(form=form)).sections


def test_anchored_s1_sections_detected():
    keys = set(_sections(_ANCHORED_S1).keys())
    missing = _EXPECTED_ANCHORED - keys
    assert not missing, f"anchored S-1 lost sections: {missing} (have {keys})"


def test_s1_registration_sections_present():
    """Business and Management — the S-1 sections a 424B vocabulary lacks."""
    keys = set(_sections(_ANCHORED_S1).keys())
    assert "business" in keys and "management" in keys


def test_flat_s1_sections_detected():
    keys = set(_sections(_FLAT_S1).keys())
    missing = _EXPECTED_FLAT - keys
    assert not missing, f"flat S-1 lost sections: {missing} (have {keys})"


def test_no_cross_section_bleed_anchored():
    """The content-bleed invariant: a section's text must not contain another's body."""
    secs = _sections(_ANCHORED_S1)
    uop = secs["use_of_proceeds"].text()
    # Own body, including the part after the internal sub-heading, is retained.
    assert "MARKER_UOP" in uop and "MARKER_UOP_TAIL" in uop
    # ...but neighbouring sections must not bleed in.
    assert "MARKER_BIZ" not in uop, "Use of Proceeds bled into Business"
    assert "MARKER_UW" not in uop, "Use of Proceeds bled into Underwriting"
    assert "MARKER_UW" not in secs["business"].text(), "Business bled into Underwriting"


def test_internal_subheading_is_not_its_own_section():
    """A non-vocabulary sub-heading must stay inside its parent section."""
    keys = _sections(_ANCHORED_S1).keys()
    assert not any("allocation" in k.lower() for k in keys)


def test_s1_amendment_routes_like_s1():
    """S-1/A normalizes to the S-1 schema and detects the same sections."""
    keys = set(_sections(_FLAT_S1, form="S-1/A").keys())
    missing = _EXPECTED_FLAT - keys
    assert not missing, f"S-1/A lost sections: {missing} (have {keys})"
