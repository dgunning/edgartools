"""Pre-flip regression gate for routing prospectus section text through the TOC
engine (edgartools-llmp.3, Phase 3).

Today 424B/S-1 sections come from the weak pattern extractor (document.py router).
Phase 3 flips the router so anchored forms get TOC-first detection with pattern
as a universal fallback — which is what dissolves the GH #871 prospectus
content-bleed by construction.

This module captures the invariants that must hold on prospectus output BOTH
before the flip (pattern extractor) and after it (TOC engine + fallback). The
design requires this gate to exist and be green on current output *before* the
router changes; the flip is correct only if every invariant here still holds.

The invariants are deliberately property-based, not byte-snapshots: the flip is
*meant* to change how sections are produced (and to improve bleed cases), so the
gate asserts structural correctness (right sections, no cross-section bleed,
stable keys) rather than identical text.
"""
import pytest

from edgar.documents import parse_html
from edgar.documents.config import ParserConfig

# The anchored-prospectus cases are the IMPROVEMENT target of the llmp.3 flip:
# on current `main` the pattern extractor loses Use of Proceeds and bleeds
# Dilution into Underwriting on a TOC-anchored 424B (reproduced below). These are
# marked strict-xfail so they document the acceptance criteria and fail loudly
# (XPASS) the moment the router flip makes them pass — at which point the marker
# is removed. The flat-prospectus cases are the no-regression baseline: they pass
# today via the heading/pattern path and must stay green through the flip.
_until_flip = pytest.mark.xfail(
    reason="fixed by the edgartools-llmp.3 router flip (TOC-first for prospectuses)",
    strict=True,
)


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


@_until_flip
def test_anchored_prospectus_sections_detected():
    keys = set(_sections(_ANCHORED_424B).keys())
    missing = _EXPECTED_ANCHORED - keys
    assert not missing, f"anchored 424B lost sections: {missing} (have {keys})"


def test_flat_prospectus_sections_detected():
    keys = set(_sections(_FLAT_424B).keys())
    missing = _EXPECTED_FLAT - keys
    assert not missing, f"flat 424B lost sections: {missing} (have {keys})"


@_until_flip
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
