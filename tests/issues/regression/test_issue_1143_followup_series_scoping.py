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


# --- Network -----------------------------------------------------------------

@pytest.mark.network
@pytest.mark.regression
def test_the_latest_report_belongs_to_the_fund_that_was_asked():
    from edgar.funds.core import Fund

    report = Fund("VEXMX").get_latest_report()

    assert report.general_info.series_id == "S000002841", (
        f"VEXMX was handed {report.general_info.series_id}'s report"
    )


@pytest.mark.network
@pytest.mark.regression
def test_a_list_of_years_narrows_the_result():
    from edgar.funds import find_fund

    series = find_fund("VEXMX").series
    everything = len(series.get_filings())
    two_years = len(series.get_filings(year=[2023, 2024]))
    one_year = len(series.get_filings(year=2024))

    assert 0 < one_year < two_years < everything
