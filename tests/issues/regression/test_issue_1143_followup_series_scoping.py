"""Follow-up to GH #1143, on top of the fix in #1144.

#1144 made `FundSeries.get_filings()` answer for its own series. Two paths were
left reachable, both verified still broken on `main` after that merge:

1. `Fund.get_latest_report()` and `Fund.get_portfolio()` chain through
   `get_filings()` without `series_only`, so they take the trust-wide path.
   `Fund("VEXMX").get_latest_report()` returned S000002846's report — the same
   harm #1143 describes, through the documented holdings entry point, which
   also backs MCP `edgar_fund(action="portfolio")`.

2. `year`/`quarter` as a list is untranslatable in `_series_filter_kwargs`,
   which drops it and logs at debug. The caller then receives the series'
   entire unfiltered history, indistinguishable from a filter that legitimately
   matched everything:

       series.get_filings(year=[2023, 2024])  -> 485   # == no filter at all
       series.get_filings()                   -> 485

GitHub Issue: https://github.com/dgunning/edgartools/issues/1143
"""
import pytest

from edgar._filings import Filings

# --- The report accessors must ask for their own series ---------------------

def test_latest_report_is_series_scoped_when_the_fund_names_a_series():
    """get_portfolio() chains through this, so it carries the original harm."""
    from edgar.funds.core import Fund

    fund = Fund.__new__(Fund)
    fund._target_series_id = "S000002841"
    seen = {}

    def _capture(**kwargs):
        seen.update(kwargs)
        return Filings([])

    fund.get_filings = _capture
    fund.get_latest_report()

    assert seen.get('series_only') is True


def test_latest_report_stays_trust_wide_without_a_series():
    """A Fund built from a multi-series trust CIK names no series."""
    from edgar.funds.core import Fund

    fund = Fund.__new__(Fund)
    fund._target_series_id = None
    seen = {}

    def _capture(**kwargs):
        seen.update(kwargs)
        return Filings([])

    fund.get_filings = _capture
    fund.get_latest_report()

    assert seen.get('series_only') is False


# --- Filters must not silently widen into the whole history -----------------

def test_a_list_of_years_becomes_one_range_each():
    from edgar.funds.core import _year_quarter_ranges

    assert _year_quarter_ranges(2024, None) == ["2024-01-01:2024-12-31"]
    assert _year_quarter_ranges([2023, 2024], None) == [
        "2023-01-01:2023-12-31", "2024-01-01:2024-12-31",
    ]
    assert _year_quarter_ranges(2024, [1, 2]) == [
        "2024-01-01:2024-03-31", "2024-04-01:2024-06-30",
    ]


def test_an_untranslatable_year_raises_instead_of_returning_everything():
    """The failure being pinned is a wrong answer, not an exception.

    A dropped filter returned the entire unfiltered history, which cannot be
    told apart from a filter that matched everything.
    """
    from edgar.funds.core import _apply_series_filters

    with pytest.raises(ValueError, match="Cannot filter a fund series"):
        _apply_series_filters(Filings([]), {'year': "2024"})


def test_no_filter_is_still_no_filter():
    from edgar.funds.core import _apply_series_filters

    empty = Filings([])
    assert _apply_series_filters(empty, {}) is empty


# --- Against SEC's own pages, offline ----------------------------------------
#
# browse-edgar pages for VEXMX's series S000002841, saved verbatim on 2026-11-22
# under tests/fixtures/funds/ (see the READMEs there). The Fund is built with the
# series already named, so no ticker lookup is involved: the question here is
# which series the answer belongs to, not how a ticker resolves.
#
# Ground truth, read without edgartools:
# * The newest NPORT-P on S000002841's own listing is 0000036405-26-000478
#   (period 2026-06-30, filed 2026-08-28). Its SEC header lists exactly one
#   series, S000002841.
# * The series' unfiltered listing holds 486 unique filings: 22 filed in 2023
#   and 29 in 2024, counted from the page HTML.

VEXMX_SERIES = "S000002841"
VEXMX_LATEST_NPORT = "0000036405-26-000478"


class _TrustWide:
    """The umbrella trust. Reaching it from a series question is the bug."""

    def get_filings(self, **kwargs):
        raise AssertionError(f"asked the whole trust instead of the series: {kwargs}")


@pytest.fixture
def sec_pages(monkeypatch):
    from tests._browse_edgar_pages import serve_recorded_pages

    requested = []
    monkeypatch.setattr("edgar.funds.data.download_text", serve_recorded_pages(requested))
    return requested


def test_the_recorded_pages_are_present():
    """Absent is not passing."""
    from tests._browse_edgar_pages import FORM_PAGES, SERIES_PAGES

    for name in ("S000002841-NPORT-P-start0.html", "S000002841-NPORT-P-start100.html"):
        assert (FORM_PAGES / name).is_file(), name
    for start in range(0, 700, 100):
        assert (SERIES_PAGES / f"S000002841-start{start}.html").is_file(), start


def test_the_latest_report_belongs_to_the_fund_that_was_asked(sec_pages, monkeypatch):
    from edgar._filings import Filing
    from edgar.funds.core import Fund

    fund = Fund.__new__(Fund)
    fund._target_series_id = VEXMX_SERIES
    fund._entity = fund._company = _TrustWide()
    fund._series = fund._class = None
    # Parsing the 3 MB NPORT document is not what is under test; which filing
    # get_latest_report() picked is.
    monkeypatch.setattr(Filing, "obj", lambda self: self.accession_no)

    assert fund.get_latest_report() == VEXMX_LATEST_NPORT
    assert all(f"CIK={VEXMX_SERIES}&type=NPORT-P" in url for url in sec_pages)


def test_a_list_of_years_narrows_the_result(sec_pages):
    from edgar.funds.core import FundSeries

    series = FundSeries(VEXMX_SERIES, "Vanguard Extended Market Index Fund", fund_company=_TrustWide())

    assert len(series.get_filings()) == 486
    assert len(series.get_filings(year=[2023, 2024])) == 51
    assert len(series.get_filings(year=2024)) == 29
