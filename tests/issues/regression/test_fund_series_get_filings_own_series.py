"""A fund series asked for its filings answered with the whole trust's.

`FundSeries.get_filings()` was a one-line delegation to
`self.fund_company.get_filings(**kwargs)`. A trust files one NPORT-P per series
per quarter under a single CIK, so that call returns every sibling series'
filings mixed together and the newest belongs to whichever series filed last.
`series.get_filings(form="NPORT-P")[0]` — the call `docs/examples/user_journeys.md`
recommends — therefore handed back another fund's portfolio.

Vanguard's trust (CIK 36405) shows it: Extended Market Index (S000002841) and
500 Index (S000002839) both answered with 325 filings whose newest was
`0000036405-26-000325`, the 500 Index report. The Extended Market fund excludes
the S&P 500 by construction, so its "holdings" were the index it is defined as
not holding.

This is GH #888's trap on the neighbouring object: that issue fixed
`Fund.get_filings(series_only=True)` by resolving the series through browse-edgar
with the series ID in the CIK slot, and settled that an unresolvable series must
yield nothing rather than the trust. `FundSeries.get_filings` now takes the same
path, and `Fund.get_filings()`'s documented trust-wide default is unchanged.
"""

from unittest.mock import MagicMock, patch

import pytest

from edgar import Fund
from edgar._filings import Filings
from edgar.funds.core import FundSeries


def _series(series_id="S000002841", name="Vanguard Extended Market Index Fund"):
    """A series whose fund company records whether it was asked for filings."""
    company = MagicMock()
    company.get_filings.return_value = "THE WHOLE TRUST"
    return FundSeries(series_id=series_id, name=name, fund_company=company)


def test_series_asks_for_its_own_series_not_its_company():
    series = _series()
    own = MagicMock(name="this series' filings")

    with patch("edgar.funds.core._series_filings", return_value=own) as resolve:
        result = series.get_filings(form="NPORT-P")

    assert result is own
    resolve.assert_called_once_with("S000002841", form="NPORT-P")
    # A fall-back to the trust is the whole defect: it must not happen.
    series.fund_company.get_filings.assert_not_called()


def test_unresolvable_series_yields_nothing_rather_than_the_trust():
    """An empty answer is correct for a series with nothing on file. A sibling's
    filings never are — which is what GH #888 settled for the other path."""
    series = _series()

    with patch("edgar.funds.core._series_filings", return_value=None):
        result = series.get_filings(form="NPORT-P")

    assert isinstance(result, Filings)
    assert len(result) == 0
    series.fund_company.get_filings.assert_not_called()


def test_an_etfs_synthetic_series_still_asks_its_company():
    """`ETF_<cik>` is not a real series ID: it stands for the whole registrant,
    so there is no sibling series to be confused with and nothing to resolve."""
    series = _series(series_id="ETF_1100663", name="An ETF")

    with patch("edgar.funds.core._series_filings") as resolve:
        result = series.get_filings(form="NPORT-P")

    assert result == "THE WHOLE TRUST"
    resolve.assert_not_called()


@pytest.mark.network
@pytest.mark.regression
@pytest.mark.parametrize(
    "ticker,series_id",
    [("VEXMX", "S000002841"), ("VFINX", "S000002839")],
)
def test_the_newest_nport_belongs_to_the_series_that_was_asked(ticker, series_id):
    fund = Fund(ticker)
    series = fund.series
    assert series.series_id == series_id

    filings = series.get_filings(form="NPORT-P")
    assert len(filings) > 0

    report = filings.latest(1).obj()
    assert report.general_info.series_id == series_id, (
        f"{ticker}: the series was handed {report.general_info.series_id}'s report"
    )


@pytest.mark.network
@pytest.mark.regression
def test_the_trust_wide_default_on_fund_is_untouched():
    """`Fund.get_filings()` documents its default as the umbrella trust's
    filings, with `series_only=True` as the narrowing ask. Making FundSeries
    series-aware must not quietly change that."""
    fund = Fund("VEXMX")

    default = fund.get_filings(form="NPORT-P")
    series_only = fund.get_filings(form="NPORT-P", series_only=True)

    assert len(default) > len(series_only)
