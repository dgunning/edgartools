from edgar import *
import tempfile
from pathlib import Path
import pytest


@pytest.mark.nrtwork
def test_filing_document_for_paper_filings_is_scanned_document():
    filing = Filing(form='NO ACT', filing_date='2015-12-03', company='DEERE & CO', cik=315189, accession_no='9999999997-15-015684')
    document = filing.document
    assert document.document == 'scanned.pdf'
    with tempfile.TemporaryDirectory() as tmpdir:
        document.download(path = Path(tmpdir) / 'scanned.pdf')
        assert (Path(tmpdir) / 'scanned.pdf').exists(), "Scanned document should be downloaded successfully"
