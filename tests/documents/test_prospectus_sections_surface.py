"""Verification for the prospectus section surface (edgartools-ybth / gh-866).

`RegistrationS1` and `Prospectus424B` expose `.sections` / `.section(name)` over
the shared title-based section engine. The contract: labelled sections when the
title/TOC anchors resolve, otherwise a single ``'full'`` section carrying the
whole document — a caller asking for section text never silently loses content.

These are offline tests: they drive the `ProspectusSectionsMixin` directly with a
parsed `Document` so no network/cassette is needed.
"""
from edgar.documents import parse_html
from edgar.documents.config import ParserConfig
from edgar.offerings.prospectus._sections import ProspectusSectionsMixin


class _Host(ProspectusSectionsMixin):
    """Minimal host exposing the `_document` the mixin requires."""
    def __init__(self, document):
        self._document = document


# A 424B with a real anchored TOC -> the engine resolves labelled sections.
_ANCHORED = """
<html><body>
<div><b>TABLE OF CONTENTS</b><table>
<tr><td><a href="#uop">Use of Proceeds</a></td><td><a href="#uop">12</a></td></tr>
<tr><td><a href="#rf">Risk Factors</a></td><td><a href="#rf">5</a></td></tr>
<tr><td><a href="#uw">Underwriting</a></td><td><a href="#uw">25</a></td></tr>
</table></div>
<div id="rf"><b>Risk Factors</b><p>MARKER_RF: Investing involves risk.</p></div>
<div id="uop"><b>Use of Proceeds</b><p>MARKER_UOP: net proceeds for general purposes.</p></div>
<div id="uw"><b>Underwriting</b><p>MARKER_UW: the underwriters have agreed to purchase.</p></div>
</body></html>
"""

# A prospectus with no machine-readable TOC and no vocabulary headings -> the
# engine resolves nothing, so the surface must fall back to a single 'full'.
_FLAT_NO_SECTIONS = """
<html><body>
<p>UNIQUE_BODY_TOKEN: this prospectus has only plain paragraphs and no headings.</p>
<p>More narrative text that must still be reachable through the full fallback.</p>
</body></html>
"""


def _host(html):
    return _Host(parse_html(html, ParserConfig(form="424B5")))


def test_labeled_sections_exposed():
    host = _host(_ANCHORED)
    keys = set(host.sections.keys())
    assert {"risk_factors", "use_of_proceeds", "underwriting"} <= keys
    assert "MARKER_RF" in host.section("risk_factors").text()


def test_section_accessor_missing_returns_none():
    host = _host(_ANCHORED)
    assert host.section("definitely_not_a_section") is None


def test_full_fallback_when_no_sections_detected():
    host = _host(_FLAT_NO_SECTIONS)
    assert set(host.sections.keys()) == {"full"}, "should collapse to a single full section"
    full = host.section("full")
    assert full is not None
    # The contract: content is never lost — the body token is reachable via 'full'.
    assert "UNIQUE_BODY_TOKEN" in full.text()


def test_no_document_yields_empty_sections():
    host = _Host(None)
    assert len(host.sections) == 0
    assert host.section("risk_factors") is None
