"""ProxyStatement.sections — semantic section text surface (edgartools-x341 / gh-867).

The DEF 14A title-engine flip lets a proxy expose Schedule 14A / Reg S-K semantic
sections. ``ProxyStatement.sections`` / ``.section(key)`` / ``.document`` are the
data-object surface over that engine. These tests cover the contract offline
(deterministic, via a stub filing feeding synthetic proxy HTML) plus a pinned
real-filing ground truth.
"""
import pytest

from edgar import Company, Filing
from edgar.proxy import ProxyStatement


# --- offline: a stub filing feeding synthetic proxy HTML ---------------------

_ANCHORED_PROXY = """
<html><body>
<div><b>TABLE OF CONTENTS</b><table>
<tr><td><a href="#sum">Proxy Summary</a></td><td><a href="#sum">1</a></td></tr>
<tr><td><a href="#cg">Corporate Governance</a></td><td><a href="#cg">12</a></td></tr>
<tr><td><a href="#cda">Compensation Discussion and Analysis</a></td><td><a href="#cda">31</a></td></tr>
<tr><td><a href="#audit">Audit Matters</a></td><td><a href="#audit">60</a></td></tr>
</table></div>
<div id="sum"><b>Proxy Summary</b><p>MARKER_SUM: We are holding our annual meeting.</p></div>
<div id="cg"><b>Corporate Governance</b><p>MARKER_CG: Our board is led by an independent chair.</p></div>
<div id="cda"><b>Compensation Discussion and Analysis</b>
<p>MARKER_CDA: Our compensation program ties pay to performance.</p></div>
<div id="audit"><b>Audit Matters</b><p>MARKER_AUDIT: The Audit Committee oversees our auditors.</p></div>
</body></html>
"""


class _StubFiling:
    """Minimal Filing stand-in: ProxyStatement.sections only needs form + html()."""
    def __init__(self, html, form="DEF 14A"):
        self.form = form
        self._html = html
        self.cik = 123
        self.accession_no = "0000000000-00-000000"

    def html(self):
        return self._html


def _proxy(html, form="DEF 14A"):
    return ProxyStatement(_StubFiling(html, form))


@pytest.mark.fast
class TestProxySectionsOffline:
    """Deterministic contract + silence checks — no network."""

    def test_sections_resolve_to_proxy_vocabulary(self):
        secs = _proxy(_ANCHORED_PROXY).sections
        assert {"proxy_summary", "corporate_governance",
                "compensation_discussion_and_analysis", "audit_matters"} <= set(secs)

    def test_section_returns_text_for_known_key(self):
        proxy = _proxy(_ANCHORED_PROXY)
        cda = proxy.section("compensation_discussion_and_analysis")
        assert cda is not None
        assert "MARKER_CDA" in cda.text()

    def test_section_does_not_bleed_into_next(self):
        cg = _proxy(_ANCHORED_PROXY).section("corporate_governance")
        assert "MARKER_CG" in cg.text()
        assert "MARKER_AUDIT" not in cg.text()

    def test_silence_unknown_key_returns_none(self):
        """A useful absence, not an error: an unrecognized key -> None."""
        assert _proxy(_ANCHORED_PROXY).section("not_a_real_section") is None

    def test_silence_no_html_returns_empty_mapping(self):
        """A proxy whose HTML cannot be fetched -> empty mapping + None, not a crash."""
        proxy = _proxy(None)
        assert proxy.sections == {}
        assert proxy.section("corporate_governance") is None


# --- network: pinned real-filing ground truth --------------------------------

AppleDEF14A = Filing(
    form='DEF 14A',
    filing_date='2025-01-10',
    company='Apple Inc.',
    cik=320193,
    accession_no='0001308179-25-000008',
)


@pytest.mark.network
def test_apple_proxy_sections_ground_truth():
    proxy = AppleDEF14A.obj()
    assert isinstance(proxy, ProxyStatement)
    keys = set(proxy.sections)
    # Apple's 2025 proxy resolves 12 labeled sections; assert the governance /
    # compensation / ownership spine (hand-verified against the filing). Apple
    # nests its audit disclosure under governance, so audit_matters is absent —
    # the assertion deliberately does not require it.
    assert {"proxy_summary", "corporate_governance",
            "compensation_discussion_and_analysis", "executive_compensation",
            "security_ownership"} <= keys, f"missing core proxy sections (have {keys})"
    cda = proxy.section("compensation_discussion_and_analysis")
    assert cda is not None
    # CD&A is a substantial narrative section (~52K chars), not a sliver.
    assert len(cda.text()) > 5000
