"""
Simulation test for GitHub Issue #674: Full end-to-end fallback verification.

Forces the homepage fallback path on a real filing and verifies that all major
APIs still produce correct results by comparing against the normal (SGML) path.

Strategy:
  1. Load a filing normally (SGML path) and capture baseline values
  2. Force fallback by patching FilingSGML.from_filing to raise ValueError
  3. Verify that the fallback path produces the same results as the baseline

Every test also asserts that FilingSGML.from_homepage ran. That guard exists
because two of these tests used to pass without the fallback running at all.
Filing hashes by accession number and html(), text(), xml() and parse() are
lru_cache'd methods, so the fresh Filing built for the fallback hit the cache
entries the baseline had just filled: test_fallback_html_available returned
the SGML-path HTML without calling sgml(), and test_fallback_text_available
rendered that same cached HTML. The caches are now cleared before each test.

With the caches cleared, the fallback HTML is the SGML-path HTML plus one
<script> tag that SEC's web server appends before </body> on documents served
from /Archives (its src path changes on every request). The SGML path reads
the document out of the full submission .txt, which carries no such tag.

GitHub Issue: https://github.com/dgunning/edgartools/issues/674
"""
import re
from contextlib import contextmanager
from unittest.mock import patch

import pytest

from edgar._filings import Filing
from edgar.sgml.sgml_common import FilingSGML

ACCESSION = '0001045810-21-000064'

# The filer's documents, as listed on the filing's index page, plus the full
# submission text file. The SGML path has these 13 documents and SEC's
# generated viewer files (R*.htm, FilingSummary.xml, ...), 86 in all.
FALLBACK_DOCUMENTS = [
    'nvda-20210502.htm', 'ex102globalrsuagreement-20.htm',
    'nvda2022q1ex311.htm', 'nvda2022q1ex312.htm',
    'nvda2022q1ex321.htm', 'nvda2022q1ex322.htm',
    'nvda-20210502_g1.jpg', f'{ACCESSION}.txt',
    'nvda-20210502.xsd', 'nvda-20210502_cal.xml', 'nvda-20210502_def.xml',
    'nvda-20210502_lab.xml', 'nvda-20210502_pre.xml', 'nvda-20210502_htm.xml',
]

# The tag SEC's web server injects into HTML it serves from /Archives.
_SEC_INJECTED_SCRIPT = re.compile(
    r'<script type="text/javascript"\s+src="/[^"]*"></script>(?=</body></html>\s*$)')


def _make_filing():
    """The NVIDIA filing that triggered issue #672.

    Described here and in the #672 tests as the "2021 10-K"; accession
    0001045810-21-000064 is in fact NVIDIA's 10-Q for the quarter ended
    2021-05-02, filed 2021-05-26. The form and filing_date passed below are
    the fixture's own metadata and do not change what is fetched, so the
    label has been harmless — but the figures asserted in this file come
    from that quarter, not from a fiscal year.
    """
    return Filing(form='10-K', company='NVIDIA CORP', cik=1045810,
                  filing_date='2021-06-28', accession_no=ACCESSION)


def _clear_filing_method_caches():
    for method in (Filing.html, Filing.text, Filing.xml, Filing.parse):
        method.cache_clear()


@contextmanager
def _forced_fallback():
    """Make the SGML fetch fail as in #674, and yield a spy on the fallback."""
    with patch.object(FilingSGML, 'from_filing',
                      side_effect=ValueError("SEC returned an empty or truncated response (0 bytes)")), \
         patch.object(FilingSGML, 'from_homepage', wraps=FilingSGML.from_homepage) as spy:
        yield spy


@pytest.mark.network
class TestFallbackSimulation:
    """End-to-end simulation: force homepage fallback on a real filing."""

    @pytest.fixture(scope="class")
    def baseline(self):
        """Capture baseline values from the normal SGML path."""
        _clear_filing_method_caches()
        filing = _make_filing()
        return {
            'period_of_report': filing.period_of_report,
            'attachments': [a.document for a in filing.attachments],
            'primary_doc_name': filing.document.document,
            'html': filing.html(),
            'text': filing.text(),
            # Captured on the SGML path so the fallback can be compared with it
            # rather than merely checked for non-emptiness.
            'fact_count': len(filing.xbrl().facts.to_dataframe()),
        }

    @pytest.fixture(autouse=True)
    def fresh_caches(self, baseline):
        """Run after the baseline, so no fallback test reads its cached results."""
        _clear_filing_method_caches()
        yield
        _clear_filing_method_caches()

    def test_fallback_attachments_available(self, baseline):
        """The fallback lists the filer's documents from the index page."""
        filing = _make_filing()

        with _forced_fallback() as spy:
            names = [a.document for a in filing.attachments]

        assert spy.call_count == 1
        assert names == FALLBACK_DOCUMENTS
        # Every filer document the fallback lists is one the SGML path has too.
        assert set(names) - set(baseline['attachments']) == {f'{ACCESSION}.txt'}

    def test_fallback_primary_document_available(self, baseline):
        """Primary document should be accessible under fallback."""
        filing = _make_filing()

        with _forced_fallback() as spy:
            doc = filing.document

        assert spy.call_count == 1
        assert baseline['primary_doc_name'] == 'nvda-20210502.htm'
        assert doc.document == baseline['primary_doc_name']

    def test_fallback_period_of_report(self, baseline):
        """period_of_report should be available via homepage fallback."""
        filing = _make_filing()

        with _forced_fallback() as spy:
            period = filing.period_of_report

        assert spy.call_count == 1
        assert baseline['period_of_report'] == '2021-05-02'
        assert period == baseline['period_of_report']

    def test_fallback_html_available(self, baseline):
        """The fallback downloads the primary document: the same HTML as the
        SGML path once SEC's injected <script> tag is removed."""
        filing = _make_filing()

        with _forced_fallback() as spy:
            html = filing.html()

        assert spy.call_count == 1
        assert _SEC_INJECTED_SCRIPT.sub('', html).rstrip('\n') == baseline['html']

    def test_fallback_xbrl_available(self, baseline):
        """XBRL under fallback must carry the same facts as the SGML path.

        GROUND TRUTH, read from the filing (NVIDIA, quarter ended 2021-05-02):
        revenue $5,661M against $3,080M a year earlier, net income $1,912M
        against $917M.
        """
        filing = _make_filing()

        with _forced_fallback() as spy:
            xbrl = filing.xbrl()

        assert spy.call_count == 1
        facts = xbrl.facts.to_dataframe()
        assert len(facts) == baseline['fact_count'], (
            f"fallback parsed {len(facts)} facts, the SGML path "
            f"{baseline['fact_count']}; the two paths must agree"
        )

        def undimensioned(concept):
            rows = facts[(facts['concept'] == concept) & (~facts['is_dimensioned'])]
            return sorted(rows['numeric_value'].dropna())

        assert undimensioned('us-gaap:Revenues') == [3_080_000_000, 5_661_000_000]
        assert undimensioned('us-gaap:NetIncomeLoss') == [917_000_000, 1_912_000_000]

    def test_fallback_text_available(self, baseline):
        """Text under fallback is the same text the SGML path extracts."""
        filing = _make_filing()

        with _forced_fallback() as spy:
            text = filing.text()

        assert spy.call_count == 1
        assert text == baseline['text']
        assert 'NVIDIA' in text
