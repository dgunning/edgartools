"""Tests for bounded submission downloads (GitHub issue #1985)."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier, Event, Lock

import numpy as np
import pyarrow as pa
import pytest
from httpx2 import Request, Response

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
    # Four distinct accessions let the downloads reach the barrier in pairs.
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
                     disable_progress=True, max_workers=np.int64(2))

    # Check that each distinct filing was requested exactly once.
    expected = {filing.text_url: filing.accession_no for filing in filings}
    assert sorted(requested) == sorted(expected)

    # Check that each file contains the expected data.
    for url, accession in expected.items():
        saved_file = tmp_path / "20241101" / f"{accession}.nc"
        assert saved_file.read_bytes() == url.encode()


@pytest.mark.parametrize("failure", [RuntimeError, KeyboardInterrupt])
def test_concurrent_submissions_stop_after_error(monkeypatch, tmp_path, caplog, failure):
    accessions = [f"0000320193-24-{number:06d}" for number in range(1, 7)]
    filings = Filings(pa.table({
        "accession_number": accessions,
        "filing_date": [date(2024, 11, 1)] * len(accessions),
        "cik": [320193] * len(accessions),
        "form": ["10-K"] * len(accessions),
        "company": ["Apple Inc."] * len(accessions),
    }))
    missing_url = filings[0].text_url
    failing_url = filings[1].text_url
    next_url = filings[2].text_url
    second_started = Event()
    missing_counted = Event()
    next_started = Event()
    shutting_down = Event()
    requested = []

    class TestExecutor(ThreadPoolExecutor):
        def shutdown(self, *args, **kwargs):
            shutting_down.set()
            super().shutdown(*args, **kwargs)

    def fetch(url):
        requested.append(url)
        if url == missing_url:
            return Response(404, request=Request("GET", url))
        if url == failing_url:
            second_started.set()
            assert missing_counted.wait(timeout=5)
            if failure is RuntimeError:
                # The freed slot refills while this download is still in flight.
                assert next_started.wait(timeout=5)
                raise RuntimeError("stop downloading")
            return Response(404, request=Request("GET", url))
        if url == next_url:
            next_started.set()
            # Keep this request in flight until the caller observes the error.
            assert shutting_down.wait(timeout=5)
            return Response(404, request=Request("GET", url))
        return Response(200, content=b"should never be stored")

    def track_progress(results, **kwargs):
        for result in results:
            yield result
            if result == ("not_found", accessions[0]):
                assert second_started.wait(timeout=5)
                missing_counted.set()
                if failure is KeyboardInterrupt:
                    raise KeyboardInterrupt("stop downloading")

    monkeypatch.setattr("edgar.httprequests.get_with_retry", fetch)
    monkeypatch.setattr("edgar.storage._local.tqdm", track_progress)
    monkeypatch.setattr("edgar.storage._local.ThreadPoolExecutor", TestExecutor)

    with pytest.raises(failure, match="stop downloading"):
        download_filings(filings=filings, data_directory=str(tmp_path), compress=False,
                         disable_progress=True, max_workers=2)

    assert not set(requested).intersection(filings[i].text_url for i in range(3, 6))
    if failure is RuntimeError:
        assert next_url in requested
    assert f"1 of 6 filings were not found at SEC: {accessions[0]}" in caplog.text
    assert not list(tmp_path.rglob("*.nc*"))


# Check that invalid worker counts raise a validation error.
@pytest.mark.parametrize("workers", [0, -1, 1.5, True])
def test_max_workers_must_be_a_positive_integer(workers):
    with pytest.raises(ValidationError, match="positive integer"):
        download_filings(max_workers=workers)


# Check that daily feed downloads reject multiple workers.
def test_multiple_workers_require_selected_submissions():
    with pytest.raises(ValidationError, match="requires filings"):
        download_filings(filing_date="2024-11-01", source="feed", max_workers=2)
