"""Replay SEC submissions through the concurrent downloader (GitHub issue #1985)."""

from datetime import date

import pyarrow as pa
import pytest

from edgar import httpclient
from edgar._filings import Filings


@pytest.mark.network
@pytest.mark.vcr
def test_downloads_known_submissions_with_two_workers(monkeypatch, tmp_path):
    submissions = [
        ("0000077476-17-000050", date(2017, 10, 13), "pepsicoform8-koctober2017.htm"),
        ("0000077476-26-000042", date(2026, 9, 17), "pep-20260917.htm"),
    ]
    filings = Filings(pa.table({
        "accession_number": [accession for accession, _, _ in submissions],
        "filing_date": [filing_date for _, filing_date, _ in submissions],
        "cik": [77476, 77476],
        "form": ["8-K", "8-K"],
        "company": ["PEPSICO INC", "PEPSICO INC"],
    }))
    # Use the real client and rate limiter while bypassing any existing HTTP cache.
    monkeypatch.setattr(httpclient, "HTTP_MGR", httpclient.get_http_mgr(cache_enabled=False))

    filings.download(data_directory=str(tmp_path), compress=False, disable_progress=True,
                     source="submission", max_workers=2)

    for accession, filing_date, primary_document in submissions:
        saved = tmp_path / filing_date.strftime("%Y%m%d") / f"{accession}.nc"
        content = saved.read_bytes()
        assert accession.encode() in content.split(b"<DOCUMENT>", 1)[0]
        assert f"<FILENAME>{primary_document}".encode() in content
        assert content.rstrip().endswith(b"</SEC-DOCUMENT>")
