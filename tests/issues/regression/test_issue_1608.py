"""
Regression test for GitHub Issue #1608:
``download_filings(filings=...)`` downloaded every daily feed file between the
earliest and latest filing dates, and only the save step was filtered.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1608

Three defects in ``edgar/storage/_local.py``:

1. With ``filings=`` the function turned the filings into one date range and
   downloaded every feed file in it. The skip for dates holding none of the
   requested filings sat inside ``if not date_filtered_filings.empty`` and so
   never ran. Snowflake's six 10-Ks (2021-03-31 to 2026-03-20) cost one feed file
   per business day, about 1,250 of them, to keep 6 filings.
2. A date folder that already existed was skipped before the requested filings
   were looked at, so a second call with different filings on a shared date
   downloaded nothing.
3. Even on the right dates, each filing cost its day's whole feed file. SEC
   reports Content-Length 2,892,246,544 bytes for the 2026-03-20 feed, while the
   10-K's own submission file (0001640147-26-000008.txt) is 17,816,574 bytes.

``filings=`` now fetches each filing's submission file (``source='submission'``,
the default). ``source='feed'`` still uses feed files, but only the ones that
hold a requested filing.

Everything here runs offline: the feed listing, the feed download and the
submission request are stubbed.
"""

import gzip
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pytest

import edgar.httprequests as httprequests
import edgar.storage._local as local
from edgar import Filing, Filings
from edgar.storage import download_filings

pytestmark = [pytest.mark.regression]

# Snowflake's 10-Ks, read from data.sec.gov/submissions/CIK0001640147.json
SNOW_CIK = 1640147
SNOW_10KS = {
    "0001640147-21-000073": date(2021, 3, 31),
    "0001640147-22-000023": date(2022, 3, 30),
    "0001640147-23-000030": date(2023, 3, 29),
    "0001640147-24-000101": date(2024, 3, 26),
    "0001640147-25-000052": date(2025, 3, 21),
    "0001640147-26-000008": date(2026, 3, 20),
}

# COMMON SENSE TRUST 24F-2NT: FILED AS OF DATE 1995-12-28, but in the 19951229
# daily feed (edgartools-a3ej). A feed file is keyed by dissemination date.
LATE_ACCESSION = "0000950129-95-001652"
LATE_FILED = date(1995, 12, 28)
LATE_FEED_DAY = date(1995, 12, 29)

# Apple's FY2024 10-K full submission, as SEC serves it.
APPLE_ACCESSION = "0000320193-24-000123"
APPLE_SUBMISSION = Path("data/sgml/0000320193-24-000123.txt")


def _filings(rows):
    """A Filings object from (accession, filing date, cik, form, company) rows."""
    return Filings(pa.table({
        "form": [r[3] for r in rows],
        "company": [r[4] for r in rows],
        "cik": pa.array([r[2] for r in rows], pa.int32()),
        "filing_date": pa.array([r[1] for r in rows], pa.date32()),
        "accession_number": [r[0] for r in rows],
    }))


def _snow_filings():
    return _filings([(acc, d, SNOW_CIK, "10-K", "Snowflake Inc.") for acc, d in SNOW_10KS.items()])


class FakeFeed:
    """Stands in for SEC's feed directory: one file per business day, each holding
    the accessions disseminated that day plus another filer's filing."""

    def __init__(self, homes):
        self.homes = homes          # accession -> the day whose feed holds it
        self.downloaded = []        # feed days requested, in order

    def listing(self, year, quarter):
        start = date(year, 3 * quarter - 2, 1)
        end = (date(year + (quarter == 4), (3 * quarter) % 12 + 1, 1)) - timedelta(days=1)
        days = [d for d in pd.date_range(start, end) if d.weekday() < 5]
        names = [f"{d:%Y%m%d}.nc.tar.gz" for d in days]
        return pd.DataFrame({
            "Name": names,
            "File": [f"https://www.sec.gov/Archives/edgar/Feed/{year}/QTR{quarter}/{n}" for n in names],
        })

    async def download(self, client=None, url=None, data_directory=None, disable_progress=False,
                       preserve_existing_filings=False):
        day = url.rsplit("/", 1)[-1][:8]
        self.downloaded.append(day)
        folder = Path(data_directory) / day
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "9999999999-99-000001.nc").write_text("<SUBMISSION>another filer</SUBMISSION>")
        for accession, home in self.homes.items():
            if f"{home:%Y%m%d}" == day:
                (folder / f"{accession}.nc").write_text(f"<SUBMISSION>{accession}</SUBMISSION>")
        return folder


@pytest.fixture
def feed(monkeypatch):
    def install(homes):
        fake = FakeFeed(homes)
        monkeypatch.setattr(local, "list_filing_feed_files_for_quarter", fake.listing)
        monkeypatch.setattr(local, "download_bulk_data", fake.download)
        return fake
    return install


# ---------------------------------------------------------------- source='feed'

def test_feed_source_downloads_only_the_days_holding_requested_filings(tmp_path, feed):
    """The #1608 report: 6 Snowflake 10-Ks cost 6 feed files, not one per business day."""
    fake = feed(SNOW_10KS)
    download_filings(filings=_snow_filings(), data_directory=tmp_path, source="feed", disable_progress=True)

    assert sorted(fake.downloaded) == sorted(f"{d:%Y%m%d}" for d in SNOW_10KS.values())
    for accession, filed in SNOW_10KS.items():
        folder = tmp_path / f"{filed:%Y%m%d}"
        assert (folder / f"{accession}.nc.gz").exists()
        assert not (folder / "9999999999-99-000001.nc").exists(), "another filer's filing was kept"


def test_feed_source_finds_a_filing_disseminated_the_next_day(tmp_path, feed):
    """A filing missing from its filing date's feed is looked for in the adjacent days,
    nearest first, and the search stops once it is found."""
    fake = feed({LATE_ACCESSION: LATE_FEED_DAY})
    filings = _filings([(LATE_ACCESSION, LATE_FILED, 883241, "24F-2NT", "COMMON SENSE TRUST")])
    download_filings(filings=filings, data_directory=tmp_path, source="feed", disable_progress=True)

    assert fake.downloaded == ["19951228", "19951229"]
    assert (tmp_path / "19951229" / f"{LATE_ACCESSION}.nc.gz").exists()


def test_feed_source_downloads_new_filings_on_a_date_already_stored(tmp_path, feed):
    """A second call with other filings on a shared date is not skipped because the
    date folder exists."""
    fake = feed(SNOW_10KS)
    folder = tmp_path / "20260320"
    folder.mkdir()
    (folder / "0001640147-99-999999.nc.gz").write_bytes(gzip.compress(b"<SUBMISSION>earlier</SUBMISSION>"))

    filings = _filings([("0001640147-26-000008", date(2026, 3, 20), SNOW_CIK, "10-K", "Snowflake Inc.")])
    download_filings(filings=filings, data_directory=tmp_path, source="feed", disable_progress=True)

    assert fake.downloaded == ["20260320"]
    assert (folder / "0001640147-26-000008.nc.gz").exists()
    assert (folder / "0001640147-99-999999.nc.gz").exists(), "an earlier download was removed"


def test_feed_source_skips_filings_already_stored(tmp_path, feed):
    fake = feed(SNOW_10KS)
    for accession, filed in SNOW_10KS.items():
        folder = tmp_path / f"{filed:%Y%m%d}"
        folder.mkdir()
        (folder / f"{accession}.nc.gz").write_bytes(gzip.compress(b"<SUBMISSION/>"))

    download_filings(filings=_snow_filings(), data_directory=tmp_path, source="feed", disable_progress=True)
    assert fake.downloaded == []


# ----------------------------------------------------------- source='submission'

class FakeResponse:
    def __init__(self, url, content, status_code=200):
        self.url, self.content, self.status_code = url, content, status_code

    def raise_for_status(self):
        import httpx2
        request = httpx2.Request("GET", self.url)
        raise httpx2.HTTPStatusError("not found", request=request,
                                     response=httpx2.Response(self.status_code, request=request))


@pytest.fixture
def submissions(monkeypatch):
    """Serve submission files from a dict of url -> bytes; anything else is a 404."""
    requested = []

    def install(served):
        def get_with_retry(url, **kwargs):
            requested.append(url)
            if url in served:
                return FakeResponse(url, served[url])
            return FakeResponse(url, b"", status_code=404)
        monkeypatch.setattr(httprequests, "get_with_retry", get_with_retry)
        return requested
    return install


def _apple_filing():
    return _filings([(APPLE_ACCESSION, date(2024, 11, 1), 320193, "10-K", "Apple Inc.")])


def test_submission_source_is_the_default_and_never_touches_a_feed(tmp_path, feed, submissions):
    fake = feed({})
    url = "https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/0000320193-24-000123.txt"
    requested = submissions({url: APPLE_SUBMISSION.read_bytes()})

    download_filings(filings=_apple_filing(), data_directory=tmp_path, disable_progress=True)

    assert requested == [url]
    assert fake.downloaded == []
    stored = tmp_path / "20241101" / f"{APPLE_ACCESSION}.nc.gz"
    assert gzip.decompress(stored.read_bytes()) == APPLE_SUBMISSION.read_bytes()


def test_a_stored_submission_is_read_offline_like_a_feed_bundle(tmp_path, monkeypatch, submissions):
    """The stored file is what Filing.sgml() reads from local storage, with no network."""
    url = "https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/0000320193-24-000123.txt"
    submissions({url: APPLE_SUBMISSION.read_bytes()})
    download_filings(filings=_apple_filing(), data_directory=tmp_path / "filings", disable_progress=True)

    monkeypatch.setenv("EDGAR_USE_LOCAL_DATA", "1")
    monkeypatch.setenv("EDGAR_LOCAL_DATA_DIR", str(tmp_path))

    def no_network(*args, **kwargs):
        raise AssertionError("Filing.sgml() went to the network")
    monkeypatch.setattr("edgar.sgml.sgml_common.FilingSGML.from_filing", no_network)

    sgml = Filing(form="10-K", company="Apple Inc.", cik=320193, filing_date="2024-11-01",
                  accession_no=APPLE_ACCESSION).sgml()
    assert sgml.header.period_of_report == "2024-09-28"
    assert sgml.header.filers[0].company_information.name == "Apple Inc."
    assert sgml.primary_documents[0].document == "aapl-20240928.htm"


def test_submission_source_skips_a_stored_filing(tmp_path, submissions):
    requested = submissions({})
    folder = tmp_path / "20241101"
    folder.mkdir()
    (folder / f"{APPLE_ACCESSION}.nc.gz").write_bytes(gzip.compress(b"<SEC-DOCUMENT/>"))

    download_filings(filings=_apple_filing(), data_directory=tmp_path, disable_progress=True)
    assert requested == []


def test_submission_source_carries_on_past_a_missing_filing(tmp_path, submissions, caplog):
    """A filing SEC does not have is reported, and the rest are still stored."""
    url = "https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/0000320193-24-000123.txt"
    submissions({url: APPLE_SUBMISSION.read_bytes()})
    filings = _filings([
        ("0000320193-99-999999", date(2024, 11, 1), 320193, "10-K", "Apple Inc."),
        (APPLE_ACCESSION, date(2024, 11, 1), 320193, "10-K", "Apple Inc."),
    ])
    with caplog.at_level("WARNING"):
        download_filings(filings=filings, data_directory=tmp_path, disable_progress=True)

    assert (tmp_path / "20241101" / f"{APPLE_ACCESSION}.nc.gz").exists()
    assert "1 of 2 filings were not found at SEC: 0000320193-99-999999" in caplog.text


def test_filing_date_narrows_the_filings(tmp_path, submissions):
    requested = submissions({})
    download_filings("2025-01-01:", filings=_snow_filings(), data_directory=tmp_path, disable_progress=True)
    assert sorted(u.rsplit("/", 1)[-1] for u in requested) == [
        "0001640147-25-000052.txt", "0001640147-26-000008.txt"]


def test_an_unknown_source_is_an_error():
    with pytest.raises(ValueError, match="source must be 'submission' or 'feed'"):
        download_filings(filings=_snow_filings(), source="ftp")


def test_filings_download_skips_what_is_stored_and_fetches_the_rest(tmp_path, submissions):
    """Filings.download() used overwrite_existing=True to get past the date-folder skip;
    it now downloads only the filings not stored yet."""
    url = "https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/0000320193-24-000123.txt"
    requested = submissions({url: APPLE_SUBMISSION.read_bytes()})
    filings = _filings([
        ("0001640147-25-000052", date(2025, 3, 21), SNOW_CIK, "10-K", "Snowflake Inc."),
        (APPLE_ACCESSION, date(2024, 11, 1), 320193, "10-K", "Apple Inc."),
    ])
    folder = tmp_path / "20250321"
    folder.mkdir()
    (folder / "0001640147-25-000052.nc.gz").write_bytes(gzip.compress(b"<SEC-DOCUMENT/>"))

    filings.download(data_directory=tmp_path, disable_progress=True)
    assert requested == [url]
