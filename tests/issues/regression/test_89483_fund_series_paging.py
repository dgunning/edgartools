"""A fund series or class with more than 100 filings lost its 101st filing.

Bead: edgartools-89483

`direct_get_fund_with_filings()` pages through browse-edgar 100 filings at a
time. It fetched the first page with `start=0&count=100` and then continued at
`start=101`. browse-edgar's `start` is zero-based, so the filing at position 100
was never requested, and every series or class with more than 100 filings came
back one short with nothing to say so.

Ground truth, from the SEC pages committed under
tests/fixtures/funds/browse_edgar_series_paging/ (VEXMX's series, S000002841,
saved 2026-11-22): walking start=0, 100, ..., 600 yields 540 rows and 486
unique accession numbers. The page at start=100 begins with
0001104659-23-037487, a 24F-2NT filed by VANGUARD INDEX FUNDS (CIK 36405) on
2023-03-28. It is on neither the start=0 page nor the start=101 page, and the
library returned 485 accessions without it.
"""
import re
from pathlib import Path
from unittest.mock import patch

import pytest

from edgar.funds.data import direct_get_fund_with_filings

pytestmark = pytest.mark.fast

PAGES = Path(__file__).parents[2] / "fixtures" / "funds" / "browse_edgar_series_paging"
SERIES = "S000002841"
RECORDED_STARTS = (0, 100, 200, 300, 400, 500, 600)
THE_101ST_FILING = "0001104659-23-037487"


def _serve_recorded_pages(requested):
    """Stand in for SEC: answer recorded offsets, and an empty page for any other."""
    empty = (PAGES / f"{SERIES}-start600.html").read_text(encoding="utf-8")

    def _download_text(url, *args, **kwargs):
        start = int(re.search(r"[?&]start=(\d+)", url).group(1))
        requested.append(start)
        page = PAGES / f"{SERIES}-start{start}.html"
        # An offset nobody recorded gets an empty page, which ends the walk,
        # so a wrong offset shows up as missing filings rather than a crash.
        return page.read_text(encoding="utf-8") if page.is_file() else empty

    return _download_text


@pytest.fixture
def series_filings():
    requested = []
    with patch("edgar.funds.data.download_text", side_effect=_serve_recorded_pages(requested)):
        series = direct_get_fund_with_filings(SERIES)
    assert series is not None, "the recorded pages should resolve to a series"
    accessions = series.filings.data.column("accession_number").to_pylist()
    return requested, accessions


def test_the_recorded_pages_are_present():
    """Absent is not passing."""
    for start in RECORDED_STARTS:
        assert (PAGES / f"{SERIES}-start{start}.html").is_file(), start


def test_pages_are_requested_without_a_gap(series_filings):
    requested, _ = series_filings
    assert requested == list(RECORDED_STARTS)


def test_the_101st_filing_is_kept(series_filings):
    _, accessions = series_filings
    assert THE_101ST_FILING in accessions


def test_every_filing_in_the_series_is_returned_once(series_filings):
    _, accessions = series_filings
    assert len(accessions) == 486
    assert len(set(accessions)) == 486
