"""
Simulation test for GitHub Issue #674: Full end-to-end fallback verification.

Forces the homepage fallback path on a real filing and verifies that all major
APIs still produce correct results by comparing against the normal (SGML) path.

Strategy:
  1. Load a filing normally (SGML path) and capture baseline values
  2. Force fallback by patching FilingSGML.from_filing to raise ValueError
  3. Verify that the fallback path produces equivalent or acceptable results

GitHub Issue: https://github.com/dgunning/edgartools/issues/674
"""
from unittest.mock import patch

import pytest

from edgar._filings import Filing
from edgar.sgml.sgml_common import FilingSGML


@pytest.mark.network
class TestFallbackSimulation:
    """End-to-end simulation: force homepage fallback on a real filing."""

    @pytest.fixture(scope="class")
    def nvidia_10k(self):
        """The NVIDIA filing that triggered issue #672.

        Described here and in the #672 tests as the "2021 10-K"; accession
        0001045810-21-000064 is in fact NVIDIA's 10-Q for the quarter ended
        2021-05-02, filed 2021-05-26. The form and filing_date passed below are
        the fixture's own metadata and do not change what is fetched, so the
        label has been harmless — but the figures asserted in this file come
        from that quarter, not from a fiscal year.
        """
        return Filing(form='10-K', company='NVIDIA CORP', cik=1045810,
                      filing_date='2021-06-28', accession_no='0001045810-21-000064')

    @pytest.fixture(scope="class")
    def baseline(self, nvidia_10k):
        """Capture baseline values from the normal SGML path."""
        filing = nvidia_10k
        return {
            'period_of_report': filing.period_of_report,
            'has_html': filing.html() is not None,
            'has_attachments': len(filing.attachments) > 0,
            'attachment_count': len(filing.attachments),
            'has_primary_doc': filing.document is not None,
            'primary_doc_name': filing.document.document if filing.document else None,
            # Captured on the SGML path so the fallback can be compared with it
            # rather than merely checked for non-emptiness.
            'fact_count': len(filing.xbrl().facts.to_dataframe()),
        }

    def _make_fallback_filing(self):
        """Create a fresh filing instance (no cached _sgml) that will use fallback."""
        return Filing(form='10-K', company='NVIDIA CORP', cik=1045810,
                      filing_date='2021-06-28', accession_no='0001045810-21-000064')

    def test_fallback_attachments_available(self, baseline):
        """Attachments should be available via homepage fallback."""
        filing = self._make_fallback_filing()

        with patch.object(FilingSGML, 'from_filing',
                          side_effect=ValueError("SEC returned an empty or truncated response (0 bytes)")):
            attachments = filing.attachments

        assert len(attachments) > 0
        # Homepage lists the actual filing documents (typically 10-20),
        # while SGML includes generated viewer files (R1.htm, R2.htm, etc.) so count is much higher.
        # The key documents (primary doc, XBRL files, exhibits) should all be present.
        assert len(attachments) >= 5

    def test_fallback_primary_document_available(self, baseline):
        """Primary document should be accessible under fallback."""
        filing = self._make_fallback_filing()

        with patch.object(FilingSGML, 'from_filing',
                          side_effect=ValueError("SEC returned an empty or truncated response (0 bytes)")):
            doc = filing.document

        assert doc is not None
        # The primary document name should match
        if baseline['primary_doc_name']:
            assert doc.document == baseline['primary_doc_name']

    def test_fallback_period_of_report(self, baseline):
        """period_of_report should be available via homepage fallback."""
        filing = self._make_fallback_filing()

        with patch.object(FilingSGML, 'from_filing',
                          side_effect=ValueError("SEC returned an empty or truncated response (0 bytes)")):
            period = filing.period_of_report

        assert period is not None
        assert period == baseline['period_of_report']

    def test_fallback_html_available(self, baseline):
        """HTML content should be downloadable under fallback."""
        filing = self._make_fallback_filing()

        with patch.object(FilingSGML, 'from_filing',
                          side_effect=ValueError("SEC returned an empty or truncated response (0 bytes)")):
            html = filing.html()

        assert html is not None
        assert len(html) > 100  # Should be substantial HTML content

    def test_fallback_xbrl_available(self, baseline):
        """XBRL under fallback must carry the same facts as the SGML path.

        `xbrl is not None` and `xbrl.facts is not None` were the assertions, and
        a fallback that downloaded the attachments but parsed nothing usable
        satisfies both -- an empty facts container is not None. This is the one
        test in the file where "equivalent results", the stated strategy at the
        top, was never actually compared against the baseline.

        GROUND TRUTH, read from the filing (NVIDIA, quarter ended 2021-05-02):
        revenue $5,661M against $3,080M a year earlier, net income $1,912M
        against $917M.
        """
        filing = self._make_fallback_filing()

        with patch.object(FilingSGML, 'from_filing',
                          side_effect=ValueError("SEC returned an empty or truncated response (0 bytes)")):
            xbrl = filing.xbrl()

        assert xbrl is not None
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
        """Text extraction should work under fallback."""
        filing = self._make_fallback_filing()

        with patch.object(FilingSGML, 'from_filing',
                          side_effect=ValueError("SEC returned an empty or truncated response (0 bytes)")):
            text = filing.text()

        assert text is not None
        assert len(text) > 100
