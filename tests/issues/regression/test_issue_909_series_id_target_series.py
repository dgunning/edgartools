"""
Regression test for GitHub Issue #909 (follow-on to #888):
Fund.get_filings(series_only=True) filtered correctly when the Fund was built
from a ticker, but not when it was built from a series ID or class ID.

Root cause: Fund.__init__ only populated ``_target_series_id`` on the ticker
resolution path. For Fund("S000026864") / Fund("C000080858") it stayed None, so
the series_only branch in get_filings was skipped entirely and the call fell
through to the entity delegation — the umbrella trust's filings, i.e. a sibling
series' data, which is exactly the harm #888 fixed for tickers.

Fix: backfill ``_target_series_id`` from the resolved hierarchy (self._series)
when the ticker path did not set it, so all three identifier forms for the same
fund behave identically.

GitHub Issue: https://github.com/dgunning/edgartools/issues/909
"""
import pytest

from edgar import Fund

# VCLT: ticker / series ID / class ID all name the same Vanguard series.
VCLT_TICKER = "VCLT"
VCLT_SERIES = "S000026864"
VCLT_CLASS = "C000080858"


@pytest.mark.network
@pytest.mark.regression
@pytest.mark.parametrize("identifier", [VCLT_TICKER, VCLT_SERIES, VCLT_CLASS])
def test_target_series_resolved_for_every_identifier_form(identifier):
    """A series ID and a class ID identify the target series just as a ticker
    does. Before the fix, only the ticker form populated it."""
    fund = Fund(identifier)
    assert fund.series is not None
    assert fund.series.series_id == VCLT_SERIES
    assert fund._target_series_id == VCLT_SERIES


@pytest.mark.network
@pytest.mark.regression
@pytest.mark.parametrize("identifier", [VCLT_TICKER, VCLT_SERIES, VCLT_CLASS])
def test_series_only_filters_regardless_of_identifier_form(identifier):
    """series_only=True returns only this series' filings for ticker, series ID
    and class ID alike — the reported failure was the latter two returning the
    trust's filings."""
    fund = Fund(identifier)
    want = fund.series.series_id

    series_only = fund.get_filings(form=["N-PORT", "NPORT-P"], series_only=True)
    trust_wide = fund.get_filings(form=["N-PORT", "NPORT-P"])

    assert len(series_only) > 0
    # Series filtering must actually narrow the trust-wide result.
    assert len(series_only) < len(trust_wide)

    latest_report = series_only.latest(1).obj()
    assert latest_report.series_id == want, (
        f"{identifier}: series_only returned a filing for {latest_report.series_id}, "
        f"expected {want}"
    )


@pytest.mark.network
@pytest.mark.regression
@pytest.mark.parametrize("identifier", [VCLT_TICKER, VCLT_SERIES, VCLT_CLASS])
def test_get_series_reuses_resolved_hierarchy(identifier):
    """Populating _target_series_id must not send get_series() off to re-resolve
    the series by ID — the hierarchy built at construction already holds it, and
    get_fund_object's lru_cache is only 16 entries deep, so a miss would cost two
    HTTP calls to rebuild an equivalent object."""
    fund = Fund(identifier)
    series = fund.get_series()

    assert series is not None
    assert series.series_id == VCLT_SERIES
    # The already-resolved object itself, not a rebuilt copy.
    assert series is fund._series


@pytest.mark.network
@pytest.mark.regression
def test_identifier_forms_agree_on_filing_set():
    """The three identifier forms are three names for one series, so they must
    return the same filings."""
    accessions = []
    for identifier in (VCLT_TICKER, VCLT_SERIES, VCLT_CLASS):
        filings = Fund(identifier).get_filings(form=["N-PORT", "NPORT-P"], series_only=True)
        accessions.append(set(filings.data['accession_number'].to_pylist()))

    assert accessions[0] == accessions[1] == accessions[2]
    assert len(accessions[0]) > 0
