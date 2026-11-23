"""Replay SEC submissions through the concurrent downloader (GitHub issue #1985)."""

from datetime import date

import pyarrow as pa
import pytest

from edgar import httpclient
from edgar._filings import Filings
from edgar.storage import download_filings


@pytest.fixture
def uncached_http_manager(monkeypatch):
    # Use the real client and rate limiter while bypassing any existing HTTP cache.
    manager = httpclient.get_http_mgr(cache_enabled=False)
    monkeypatch.setattr(httpclient, "HTTP_MGR", manager)
    try:
        yield
    finally:
        manager.close()


@pytest.mark.network
@pytest.mark.vcr
def test_downloads_known_submissions_with_two_workers(uncached_http_manager, tmp_path):
    submissions = [
        ("0000077476-17-000050", date(2017, 10, 13), "pepsicoform8-koctober2017.htm"),
        ("0000077476-26-000042", date(2026, 9, 17), "pep-20260917.htm"),
    ]
    entries = [*submissions, submissions[0]]
    filings = Filings(pa.table({
        "accession_number": [accession for accession, _, _ in entries],
        "filing_date": [filing_date for _, filing_date, _ in entries],
        "cik": [77476] * len(entries),
        "form": ["8-K"] * len(entries),
        "company": ["PEPSICO INC"] * len(entries),
    }))
    download_filings(filings=filings, data_directory=str(tmp_path), compress=False,
                     disable_progress=True, overwrite_existing=True, max_workers=2)

    for accession, filing_date, primary_document in submissions:
        saved = tmp_path / filing_date.strftime("%Y%m%d") / f"{accession}.nc"
        content = saved.read_bytes()
        assert accession.encode() in content.split(b"<DOCUMENT>", 1)[0]
        assert f"<FILENAME>{primary_document}".encode() in content
        assert content.rstrip().endswith(b"</SEC-DOCUMENT>")
