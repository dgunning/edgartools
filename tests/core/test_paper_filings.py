import tempfile
from pathlib import Path

import pytest

from edgar import Filing


@pytest.mark.network
def test_filing_document_for_paper_filings_is_the_scanned_pdf():
    """A paper filing's document is SEC's scan of it when the index lists one.

    SEC's history here has moved twice. It used to serve scanned.pdf beside the
    .paper stub; by early 2026-11 the scans were gone and the index listed only
    the stub (GH #1873, #1879). By 2026-11-15 the index lists "Scanned paper
    document" again, now pointing into the Virtual Public Reference Room
    (/Archives/edgar/vprr/), and that URL serves the PDF. Filing.document has
    preferred the scan throughout, so it follows SEC back.
    """
    filing = Filing(form='NO ACT', filing_date='2015-12-03', company='DEERE & CO', cik=315189,
                    accession_no='9999999997-15-015684')
    document = filing.document
    assert document.document == 'scanned.pdf'
    assert document.url == 'https://www.sec.gov/Archives/edgar/vprr/1500/15008364.pdf'
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir) / document.document
        document.download(path=target)
        assert target.read_bytes()[:5] == b'%PDF-'
        assert target.stat().st_size == 1_546_303

    # The stub is still the SGML's primary document, and it names the same control number.
    stub = filing.sgml().attachments.primary_html_document
    assert stub.document == '9999999997-15-015684.paper'
    assert 'Document Control Number 15008364' in stub.text()
