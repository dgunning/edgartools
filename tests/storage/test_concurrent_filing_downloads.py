"""Tests for bounded submission downloads (GitHub issue #1985)."""

from datetime import date
from threading import Barrier, Lock

import pyarrow as pa
import pytest
from httpx2 import Response

from edgar._filings import Filings
from edgar.exceptions import ValidationError
from edgar.storage import download_filings

pytestmark = pytest.mark.fast


def test_concurrent_submissions_respect_worker_limit_and_skip_duplicates(monkeypatch, tmp_path):
    # Prepare five filing entries, including one duplicate.
    accessions = [
        "0000320193-24-000001",
        "0000320193-24-000002",
        "0000320193-24-000001",
        "0000320193-24-000003",
        "0000320193-24-000004",
    ]
    count = len(accessions)
    filings = Filings(pa.table({
        "accession_number": accessions,
        "filing_date": [date(2024, 11, 1)] * count,
        "cik": [320193] * count,
        "form": ["10-K"] * count,
        "company": ["Apple Inc."] * count,
    }))

    # Track how many fake downloads are active at once.
    lock = Lock()
    pair = Barrier(2, timeout=5)
    active = 0
    requested = []

    def fetch(url):
        nonlocal active
        with lock:
            active += 1
            assert active <= 2, "More than two downloads were active"
            requested.append(url)
        # A sequential downloader times out here waiting for a second worker.
        pair.wait()
        with lock:
            active -= 1
        return Response(200, content=url.encode())

    # Replace the SEC request with the fake download.
    monkeypatch.setattr("edgar.httprequests.get_with_retry", fetch)

    download_filings(filings=filings, data_directory=str(tmp_path), compress=False,
                     disable_progress=True, max_workers=2)

    # Check that each distinct filing was requested exactly once.
    expected = {filing.text_url: filing.accession_no for filing in filings}
    assert sorted(requested) == sorted(expected)

    # Check that each file contains the expected data.
    for url, accession in expected.items():
        saved_file = tmp_path / "20241101" / f"{accession}.nc"
        assert saved_file.read_bytes() == url.encode()


# Check that invalid worker counts raise a validation error.
@pytest.mark.parametrize("workers", [0, -1, 1.5, True])
def test_max_workers_must_be_a_positive_integer(workers):
    with pytest.raises(ValidationError, match="positive integer"):
        download_filings(max_workers=workers)


# Check that daily feed downloads reject multiple workers.
def test_multiple_workers_require_selected_submissions():
    with pytest.raises(ValidationError, match="requires filings"):
        download_filings(filing_date="2024-11-01", source="feed", max_workers=2)
