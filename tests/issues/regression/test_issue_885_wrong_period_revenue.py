"""
Regression test for GitHub Issue #885:
Financials.get_revenue() (and the other standardized income getters) returned a
prior-year comparative value on 10-Q filings that report multiple duration
periods.

Root cause: the period column was selected positionally as
``period_columns[period_offset]``, assuming index 0 is the most recent period.
RenderedStatement.to_dataframe() does NOT order its columns by recency — for a
10-Q reporting both 3-month and YTD columns for the current and comparative
year, the order mixed current/comparative and 3-month/YTD unpredictably. For
IonQ's FY2025 Q2 10-Q the column order was
['2024-06-30 (Q2)', '2025-06-30', '2024-06-30', '2025-06-30 (Q2)'], so
period_offset=0 resolved to the prior-year Q2 column.

Fix: _order_period_columns() rebuilds the column order from each period's
metadata (end_date/start_date/duration/quarter) — current reporting period
first (shortest duration at the latest end date), then that same-duration
series backwards in time, then other durations, then instants. See
edgar/financials.py.

Ground truth is the value reported in each filing's own Condensed Consolidated
Statements of Operations.
"""
import pytest
from edgar import get_by_accession_number


@pytest.mark.network
@pytest.mark.regression
def test_ionq_q2_2025_revenue_is_current_period():
    """IonQ FY2025 Q2 10-Q: get_revenue() must be the current-quarter
    $20,694,000, NOT the prior-year Q2 comparative $11,381,000."""
    filing = get_by_accession_number("0000950170-25-104066")  # period 2025-06-30
    fin = filing.obj().financials

    assert fin.get_revenue() == 20694000, (
        "get_revenue() returned the wrong period — expected current-year Q2 "
        "(20,694,000), likely got prior-year Q2 (11,381,000)"
    )
    # period_offset=1 should be the prior-year Q2 comparative.
    assert fin.get_revenue(period_offset=1) == 11381000


@pytest.mark.network
@pytest.mark.regression
def test_ionq_q3_2025_revenue_is_current_period():
    """IonQ FY2025 Q3 10-Q: get_revenue() must be the current-quarter
    $39,866,000, NOT the prior-year Q3 comparative $12,400,000."""
    filing = get_by_accession_number("0001193125-25-266942")  # period 2025-09-30
    fin = filing.obj().financials

    assert fin.get_revenue() == 39866000


@pytest.mark.network
@pytest.mark.regression
def test_annual_10k_still_returns_latest_year():
    """No regression on annual filings: get_revenue() returns the latest fiscal
    year, and period_offset=1 the prior year (values strictly decreasing in
    time for Apple's most recent 10-K)."""
    from edgar import Company

    filing = Company("AAPL").get_filings(form="10-K", amendments=False).latest(1)
    fin = filing.obj().financials

    latest = fin.get_revenue()
    prior = fin.get_revenue(period_offset=1)

    assert latest is not None and prior is not None
    # The most recent year must be more recent (and Apple's revenue grew), so
    # latest > prior confirms offset 0 is the current period, not a comparative.
    assert latest > prior


@pytest.mark.network
@pytest.mark.regression
def test_out_of_range_offset_returns_none():
    """Silence check: an offset beyond the available periods returns None rather
    than a wrong-period value."""
    filing = get_by_accession_number("0000950170-25-104066")
    fin = filing.obj().financials

    assert fin.get_revenue(period_offset=99) is None
