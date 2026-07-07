"""
Regression test for GitHub Issue #888:
Fund.get_filings(series_only=True) silently returned the whole umbrella trust's
filings instead of filtering to the fund's own series.

Root cause: the series-aware path used EFTS full-text search on the series ID,
which returns nothing (SEC full-text search does not index NPORT series IDs), so
the method fell through to the unfiltered trust delegation and returned a sibling
series' data (e.g. VCLT / S000026864 got a filing whose report.series_id was
S000026865).

Fix: _get_series_filings() resolves the series via SEC browse-edgar (series ID as
the CIK parameter), which returns exactly that series' filings; and series_only
now returns an empty Filings rather than the unfiltered trust when the series
cannot be resolved.
"""
import pytest

from edgar import Fund
from edgar._filings import Filings
from edgar.funds.core import _series_filter_kwargs


# --- Offline: entity-style kwargs are mapped onto the Filings.filter interface
# (regression for the review finding that raw kwargs crashed with TypeError) ---

def test_series_filter_kwargs_defaults_amendments_true():
    # Filings.filter drops amendments by default when a form is given; the
    # entity path includes them, so the series path must too.
    assert _series_filter_kwargs({'form': 'NPORT-P'}) == {'form': 'NPORT-P', 'amendments': True}


def test_series_filter_kwargs_translates_year_and_quarter():
    assert _series_filter_kwargs({'form': 'NPORT-P', 'year': 2024})['filing_date'] == '2024-01-01:2024-12-31'
    assert _series_filter_kwargs({'year': 2024, 'quarter': 2})['filing_date'] == '2024-04-01:2024-06-30'


def test_series_filter_kwargs_drops_unsupported_without_crashing():
    # year/quarter/is_xbrl/file_number are valid on Entity.get_filings but not
    # on Filings.filter; they must be dropped, not forwarded (which raised
    # TypeError before the fix).
    mapped = _series_filter_kwargs({'form': 'NPORT-P', 'is_xbrl': True, 'file_number': '811-1', 'sort_by': 'x'})
    assert mapped == {'form': 'NPORT-P', 'amendments': True}


def test_series_filter_kwargs_respects_explicit_amendments():
    assert _series_filter_kwargs({'form': 'NPORT-P', 'amendments': False})['amendments'] is False


@pytest.mark.network
@pytest.mark.regression
@pytest.mark.parametrize("ticker", ["VCLT", "PFF"])
def test_series_only_filters_to_fund_series(ticker):
    """Every filing returned by series_only=True belongs to the fund's own
    series, and the set is far smaller than the unfiltered trust."""
    fund = Fund(ticker)
    want = fund.series.series_id

    series_only = fund.get_filings(form=["N-PORT", "NPORT-P"], series_only=True)
    trust_wide = fund.get_filings(form=["N-PORT", "NPORT-P"])

    assert len(series_only) > 0
    # Series filtering must actually narrow the result set.
    assert len(series_only) < len(trust_wide)

    # The most recent returned filing must be for THIS series, not a sibling.
    latest_report = series_only.latest(1).obj()
    assert latest_report.series_id == want, (
        f"{ticker}: series_only returned a filing for {latest_report.series_id}, "
        f"expected {want}"
    )


@pytest.mark.network
@pytest.mark.regression
def test_series_only_does_not_return_unfiltered_trust_when_no_matches():
    """When series_only is requested but no filings match, the result is an empty
    Filings — never the unfiltered trust (the original harm)."""
    fund = Fund("VCLT")
    # A form this series does not file should yield empty, not the trust.
    result = fund.get_filings(form="SC 13D", series_only=True)
    assert isinstance(result, Filings)
    assert len(result) == 0


@pytest.mark.network
@pytest.mark.regression
def test_default_get_filings_unchanged():
    """No regression: without series_only, get_filings still returns the broader
    trust filing set."""
    fund = Fund("VCLT")
    series_only = fund.get_filings(form=["N-PORT", "NPORT-P"], series_only=True)
    default = fund.get_filings(form=["N-PORT", "NPORT-P"])
    assert len(default) > len(series_only)
