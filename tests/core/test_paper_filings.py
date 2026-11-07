import tempfile
from pathlib import Path

import pytest

from edgar import Filing


@pytest.mark.network
def test_filing_document_for_paper_filings_is_the_paper_stub():
    """A paper filing's document is SEC's auto-generated .paper stub.

    SEC used to serve a scanned.pdf beside the stub, and Filing.document still
    prefers one when the index lists it. By 2026-11 SEC had removed the scans:
    scanned.pdf for this filing returns 404, and 18 of 18 paper filings checked
    (Deere, Apple, Microsoft, 2013-2017) list only the stub and the .txt.
    """
    filing = Filing(form='NO ACT', filing_date='2015-12-03', company='DEERE & CO', cik=315189,
                    accession_no='9999999997-15-015684')
    document = filing.document
    assert document.document == '9999999997-15-015684.paper'
    assert 'Document Control Number 15008364' in document.text()
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir) / document.document
        document.download(path=target)
        assert target.exists(), "The paper stub should download"
