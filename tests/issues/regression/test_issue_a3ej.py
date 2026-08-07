"""
Regression test for edgartools-a3ej: local-storage write/read date-folder mismatch.

``download_filings()`` buckets feed files by the SEC dissemination (acceptance) date,
but the read side keys lookups off the FILED AS OF DATE. For boundary filings (after-hours
submissions, or historic dissemination lag) these differ, so a correctly-downloaded bundle
landed in an adjacent day's folder and was silently not found — triggering a network fetch.

``resolve_local_filing_path`` fixes this with an additive read-side fallback: it checks the
FILED AS OF DATE folder first, then scans a small window of adjacent days. Because accession
numbers are globally unique, any folder holding ``<accession>.nc`` is unambiguously the file.

The reference filing is 0000950129-95-001652 (COMMON SENSE TRUST 24F-2NT): FILED AS OF DATE
19951228, but it appears in the 19951229 daily feed. These tests run offline.
"""

import pytest

from edgar.storage._local import resolve_local_filing_path

FIXTURE = "data/sgml/0000950129-95-001652.txt"
ACCESSION = "0000950129-95-001652"
FILED_AS_OF = "1995-12-28"   # the read-side key
FEED_DATE = "19951229"       # where download_filings() actually placed it (+1 day)


def _stage(tmp_path, day_yyyymmdd):
    day_dir = tmp_path / "filings" / day_yyyymmdd
    day_dir.mkdir(parents=True)
    (day_dir / f"{ACCESSION}.nc").write_bytes(open(FIXTURE, "rb").read())


def test_resolves_exact_folder(tmp_path, monkeypatch):
    monkeypatch.setenv("EDGAR_LOCAL_DATA_DIR", str(tmp_path))
    _stage(tmp_path, "19951228")
    path = resolve_local_filing_path(FILED_AS_OF, ACCESSION)
    assert path is not None and path.parent.name == "19951228"


def test_resolves_adjacent_feed_folder(tmp_path, monkeypatch):
    """The bundle is in the +1 feed folder; the read key is the FILED AS OF DATE."""
    monkeypatch.setenv("EDGAR_LOCAL_DATA_DIR", str(tmp_path))
    _stage(tmp_path, FEED_DATE)
    path = resolve_local_filing_path(FILED_AS_OF, ACCESSION)
    assert path is not None
    assert path.parent.name == FEED_DATE


def test_compressed_bundle_in_adjacent_folder(tmp_path, monkeypatch):
    import gzip
    monkeypatch.setenv("EDGAR_LOCAL_DATA_DIR", str(tmp_path))
    day_dir = tmp_path / "filings" / FEED_DATE
    day_dir.mkdir(parents=True)
    with gzip.open(day_dir / f"{ACCESSION}.nc.gz", "wb") as f:
        f.write(open(FIXTURE, "rb").read())
    path = resolve_local_filing_path(FILED_AS_OF, ACCESSION)
    assert path is not None and path.name.endswith(".nc.gz")


def test_missing_filing_returns_none(tmp_path, monkeypatch):
    """A genuinely absent filing returns None so callers fall back to the network."""
    monkeypatch.setenv("EDGAR_LOCAL_DATA_DIR", str(tmp_path))
    _stage(tmp_path, FEED_DATE)
    assert resolve_local_filing_path(FILED_AS_OF, "9999999999-99-999999") is None


def test_out_of_window_returns_none(tmp_path, monkeypatch):
    """No false match when the only copy is far outside the search window."""
    monkeypatch.setenv("EDGAR_LOCAL_DATA_DIR", str(tmp_path))
    _stage(tmp_path, FEED_DATE)
    # Read key 4 weeks away — outside the adjacent-day window.
    assert resolve_local_filing_path("1995-12-01", ACCESSION) is None


@pytest.mark.parametrize("read_key", ["1995-12-28", "19951228"])
def test_accepts_str_and_yyyymmdd_dates(tmp_path, monkeypatch, read_key):
    monkeypatch.setenv("EDGAR_LOCAL_DATA_DIR", str(tmp_path))
    _stage(tmp_path, FEED_DATE)
    assert resolve_local_filing_path(read_key, ACCESSION) is not None


def test_filing_sgml_resolves_offline_from_feed_folder(tmp_path, monkeypatch):
    """End-to-end: Filing.text() works offline when the bundle sits in the feed folder."""
    from edgar import Filing, use_local_storage

    _stage(tmp_path, FEED_DATE)
    monkeypatch.setenv("EDGAR_LOCAL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9")
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:9")
    use_local_storage(str(tmp_path), use_local=True, allow_network_fallback=False)
    try:
        filing = Filing(cik=810271, accession_no=ACCESSION, form="24F-2NT",
                        company="COMMON SENSE TRUST", filing_date=FILED_AS_OF)
        text = filing.text()
        assert "FORM 24F-2" in text
    finally:
        use_local_storage(False)
