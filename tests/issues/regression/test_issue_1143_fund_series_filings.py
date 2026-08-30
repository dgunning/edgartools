"""Regression test for GitHub Issue #1143.

``FundSeries.get_filings()`` delegated straight to the fund company:

    return self.fund_company.get_filings(**kwargs)

A trust files one report per series under a single CIK, so that returned every
sibling series' filings interleaved, and ``filings[0]`` — the idiom for "the
latest one" — belonged to whichever series filed most recently. Two different
series of Vanguard's trust (CIK 36405) returned identical counts and the same
top accession, which belonged to a third sibling entirely. The Extended Market
Index fund, which excludes the S&P 500 by construction, was handed the 500 Index
fund's portfolio.

Nothing about the result looked wrong: real filings, from the right trust, that
parse cleanly and sum to 100%.

Fix: FundSeries resolves its own series through SEC browse-edgar via
``_resolve_series_filings`` — the path ``Fund.get_filings(series_only=True)``
already used (GH #888) — and returns empty rather than falling back to the
trust, because the fallback is the bug.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1143
"""
import httpx
import pytest

from edgar._filings import Filings
from edgar.funds.core import FundSeries


@pytest.fixture
def series():
    """A FundSeries with a trust attached, built without touching the network."""

    class _Trust:
        def get_filings(self, **kwargs):
            raise AssertionError(
                "FundSeries.get_filings() delegated to the trust. That is the "
                "bug in GH #1143: the trust's filings belong to every sibling "
                "series, so the caller receives another fund's portfolio."
            )

    return FundSeries("S000002841", "Vanguard Extended Market Index Fund",
                      fund_company=_Trust())


# --- Offline: the series path is taken, and the trust fallback is gone --------

def test_series_filings_never_fall_back_to_the_trust(monkeypatch, series):
    """An unresolvable series returns empty, not the trust's filings.

    The fixture's trust raises if it is consulted, so this asserts the absence
    of the fallback rather than merely the presence of a filter.
    """
    monkeypatch.setattr("edgar.funds.core._resolve_series_filings",
                        lambda series_id, **kwargs: None)

    result = series.get_filings(form="NPORT-P")

    assert isinstance(result, Filings)
    assert len(result) == 0


def test_the_requested_series_id_is_the_one_resolved(monkeypatch, series):
    """The series' own ID reaches the resolver, with the caller's filters."""
    seen = {}

    def _capture(series_id, **kwargs):
        seen['series_id'] = series_id
        seen['kwargs'] = kwargs
        return Filings([])

    monkeypatch.setattr("edgar.funds.core._resolve_series_filings", _capture)
    series.get_filings(form="NPORT-P", year=2025)

    assert seen['series_id'] == "S000002841"
    assert seen['kwargs'] == {'form': 'NPORT-P', 'year': 2025}


def test_a_transport_failure_is_not_reported_as_no_filings(monkeypatch, series):
    """An outage must surface, not become an empty series (cf. edgartools-tg7y).

    This path has no fallback, so an empty result during an outage is
    indistinguishable from a series that has filed nothing.
    """
    def _raise(*args, **kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr("edgar.funds.data.download_text", _raise)

    with pytest.raises(httpx.ConnectError):
        series.get_filings(form="NPORT-P")


def test_synthetic_etf_series_still_use_the_trust(monkeypatch):
    """ETF_* IDs are not SEC series and browse-edgar cannot resolve them.

    Those funds file under the trust CIK directly, so the delegation is correct
    there and must survive the fix.
    """
    class _Trust:
        def get_filings(self, **kwargs):
            return "trust filings"

    etf = FundSeries("ETF_36405", "An ETF", fund_company=_Trust())
    monkeypatch.setattr("edgar.funds.core._resolve_series_filings",
                        lambda *a, **k: pytest.fail("resolved a synthetic ID"))

    assert etf.get_filings(form="NPORT-P") == "trust filings"


# --- Network: the real defect, stated as the property that failed ------------

@pytest.mark.network
@pytest.mark.parametrize("ticker,series_id", [
    ("VEXMX", "S000002841"),   # Extended Market Index — excludes the S&P 500
    ("VFINX", "S000002839"),   # 500 Index
])
def test_each_series_gets_its_own_newest_nport(ticker, series_id):
    """The filing a series hands back must actually be that series' filing.

    Asserted on the series ID inside the document rather than on a count or an
    accession number: both drift every quarter, while this property is the one
    the bug violated.
    """
    from edgar.funds import find_fund

    filings = find_fund(ticker).series.get_filings(form="NPORT-P")
    assert len(filings) > 0, f"{ticker} returned no NPORT-P filings"

    report = filings[0].obj()
    assert report.general_info.series_id == series_id, (
        f"{ticker} ({series_id}) was handed a filing belonging to "
        f"{report.general_info.series_id}"
    )


@pytest.mark.network
def test_siblings_do_not_share_a_newest_filing():
    """Two series of one trust must not return the same top accession.

    This is the shape the report was written against: identical counts and an
    identical newest filing for two funds with different mandates.
    """
    from edgar.funds import find_fund

    vexmx = find_fund("VEXMX").series.get_filings(form="NPORT-P")
    vfinx = find_fund("VFINX").series.get_filings(form="NPORT-P")

    assert len(vexmx) > 0 and len(vfinx) > 0, (
        f"expected both series to have NPORT-P filings; got {len(vexmx)} and "
        f"{len(vfinx)}. An empty result here says nothing about the bug."
    )
    assert vexmx[0].accession_number != vfinx[0].accession_number


# --- The reachable harm: get_portfolio()/get_latest_report() -----------------

def test_latest_report_is_series_scoped_when_the_fund_names_a_series(monkeypatch):
    """``get_latest_report`` must not take the trust-wide path.

    ``get_portfolio()`` chains through it and is the documented entry point for
    holdings, so leaving it on the default path would have kept the exact harm
    the fix was written for: a fund handed a sibling's portfolio.
    """
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


# --- Filters must not silently widen into the whole history ------------------

def test_a_list_of_years_is_applied_rather_than_dropped():
    from edgar.funds.core import _year_quarter_ranges

    assert _year_quarter_ranges(2024, None) == ["2024-01-01:2024-12-31"]
    assert _year_quarter_ranges([2023, 2024], None) == [
        "2023-01-01:2023-12-31", "2024-01-01:2024-12-31",
    ]
    assert _year_quarter_ranges(2024, [1, 2]) == [
        "2024-01-01:2024-03-31", "2024-04-01:2024-06-30",
    ]


def test_an_untranslatable_year_raises_instead_of_returning_everything():
    """The failure mode being pinned is a *wrong answer*, not an exception.

    A dropped filter returned the series' entire unfiltered history, which is
    indistinguishable from a filter that legitimately matched everything.
    """
    from edgar.funds.core import _apply_series_filters

    with pytest.raises(ValueError, match="Cannot filter a fund series"):
        _apply_series_filters(Filings([]), {'year': "2024"})
