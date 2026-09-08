"""Regression gate for routing prospectus section text through the TOC engine
(edgartools-llmp.3, Phase 3).

The document.py router now sends anchored 424B prospectuses through the TOC-first
hybrid detector (with heading+pattern as a universal fallback) instead of straight
to the weak pattern extractor — which dissolves the GH #871 prospectus
content-bleed by construction.

This module guards the invariants on prospectus output:
  * anchored 424B (TOC-rich): the correct section set with anchor-bounded text and
    no cross-section bleed — these failed on the old pattern path and the flip
    fixed them; the gate keeps them fixed.
  * flat 424B (no machine-readable TOC): sections still detected via the
    heading/pattern fallback the flip preserves.

The invariants are deliberately property-based, not byte-snapshots: the flip
changes how sections are produced, so the gate asserts structural correctness
(right sections, no cross-section bleed, stable keys) rather than identical text.
"""
from edgar.documents import parse_html
from edgar.documents.config import ParserConfig

# Before the edgartools-llmp.3 flip the pattern extractor lost Use of Proceeds and
# bled Dilution into Underwriting on a TOC-anchored 424B. The flip routes anchored
# prospectuses through the TOC engine, so these now pass: the anchored cases are a
# live regression guard against that bleed returning, and the flat cases guard the
# heading/pattern fallback that flat prospectuses still use.


# A 424B with a real anchored Table of Contents (the bleed-prone, TOC-rich shape
# the flip most improves) plus an internal sub-heading inside Use of Proceeds.
_ANCHORED_424B = """
<html><body>
<div><b>TABLE OF CONTENTS</b><table>
<tr><td><a href="#uop">Use of Proceeds</a></td><td><a href="#uop">12</a></td></tr>
<tr><td><a href="#dil">Dilution</a></td><td><a href="#dil">18</a></td></tr>
<tr><td><a href="#uw">Underwriting</a></td><td><a href="#uw">25</a></td></tr>
</table></div>
<div id="uop"><b>Use of Proceeds</b>
<p>MARKER_UOP: We intend to use the net proceeds for general corporate purposes.</p>
<h3>Anticipated Allocation</h3>
<p>MARKER_UOP_TAIL: A portion may be allocated to repayment of debt.</p>
</div>
<div id="dil"><b>Dilution</b><p>MARKER_DIL: Your interest will be diluted.</p></div>
<div id="uw"><b>Underwriting</b><p>MARKER_UW: The underwriters have agreed to purchase the shares.</p></div>
</body></html>
"""

# A flat 424B (no machine-readable TOC) — headings only. The flip must keep
# detecting these via the heading/pattern fallback layer.
_FLAT_424B = """
<html><body>
<h2>Risk Factors</h2><p>MARKER_RF: Investing involves risk.</p>
<h2>Use of Proceeds</h2><p>MARKER_UOP: We intend to use the net proceeds.</p>
<h2>Underwriting</h2><p>MARKER_UW: The underwriters have agreed to purchase.</p>
</body></html>
"""

_EXPECTED_ANCHORED = {"use_of_proceeds", "dilution", "underwriting"}
_EXPECTED_FLAT = {"risk_factors", "use_of_proceeds", "underwriting"}


def _sections(html):
    return parse_html(html, ParserConfig(form="424B5")).sections


def test_anchored_prospectus_sections_detected():
    keys = set(_sections(_ANCHORED_424B).keys())
    missing = _EXPECTED_ANCHORED - keys
    assert not missing, f"anchored 424B lost sections: {missing} (have {keys})"


def test_flat_prospectus_sections_detected():
    keys = set(_sections(_FLAT_424B).keys())
    missing = _EXPECTED_FLAT - keys
    assert not missing, f"flat 424B lost sections: {missing} (have {keys})"


def test_no_cross_section_bleed_anchored():
    """The #871 invariant: a section's text must not contain another's body."""
    secs = _sections(_ANCHORED_424B)
    uop = secs["use_of_proceeds"].text()
    # Own body, including the part after the internal sub-heading, is retained.
    assert "MARKER_UOP" in uop and "MARKER_UOP_TAIL" in uop
    # ...but neighbouring sections must not bleed in.
    assert "MARKER_DIL" not in uop, "Use of Proceeds bled into Dilution"
    assert "MARKER_UW" not in uop, "Use of Proceeds bled into Underwriting"
    assert "MARKER_UW" not in secs["dilution"].text(), "Dilution bled into Underwriting"


def test_internal_subheading_is_not_its_own_section():
    """A non-vocabulary sub-heading must stay inside its parent section."""
    keys = _sections(_ANCHORED_424B).keys()
    assert not any("allocation" in k.lower() for k in keys)
