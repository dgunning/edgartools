"""Regression test for issue #1247.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1247

`XBRL.reporting_periods[*]["days"]` measured every duration one day short.
XBRL 2.1 reads a date-only `endDate` as the end of that day, so the context
runs to 24:00 on it and the last day belongs to the period; subtracting the two
dates drops it. A calendar year of 2023-01-01 to 2023-12-31 reported 364 days,
Apple's 53-week FY2023 reported 370 instead of 371, and a single-day duration
context reported 0.

The fix puts the count in one place, `edgar.xbrl.core.duration_days`, and uses
it for the stored field and for the two places in `period_selector` that
recompute a duration and compare it against that stored field. `periods.py`
keeps its own exclusive count, because its bucket bounds were calibrated
against it and a 53-week year sits exactly on the `<= 370` bound - it no longer
writes that local value back over the public field.

Measured across the 8 filings committed under `data/xbrl/datafiles`: 191
duration periods change their `days` value and nothing else changes - no
`period_type`, `fiscal_period`, `label` or `key`, and no change to the periods
selected for the income statement, balance sheet or cash flow statement.
"""

from datetime import date
from pathlib import Path

import pytest

from edgar.xbrl import XBRL

DATA = Path(__file__).resolve().parents[3] / "data" / "xbrl" / "datafiles"

# `duration_days` is imported inside the tests that use it. It only exists on a
# tree carrying the fix, and a module-level import would turn this file into a
# collection error when run against an unfixed tree - which is exactly when
# someone wants to watch it fail.


# --- the count itself -------------------------------------------------------

@pytest.mark.parametrize("start,end,expected", [
    # Apple's 53-week FY2023, the case in the report.
    (date(2022, 9, 25), date(2023, 9, 30), 371),
    # Netflix Q1 2024, the second case in the report.
    (date(2024, 1, 1), date(2024, 3, 31), 91),
    # A calendar year is 365 days, not 364.
    (date(2023, 1, 1), date(2023, 12, 31), 365),
    # A leap year is 366.
    (date(2024, 1, 1), date(2024, 12, 31), 366),
    # A calendar month.
    (date(2024, 3, 1), date(2024, 3, 31), 31),
    # A duration context covering one day covers one day, not zero.
    (date(2024, 4, 12), date(2024, 4, 12), 1),
])
def test_duration_days_counts_both_endpoints(start, end, expected):
    from edgar.xbrl.core import duration_days

    assert duration_days(start, end) == expected


# --- end to end, on filings committed to the repository ---------------------

def _duration_period(xbrl, start, end):
    return next((p for p in xbrl.reporting_periods
                 if p["type"] == "duration"
                 and p["start_date"] == start and p["end_date"] == end), None)


def test_apple_53_week_fiscal_year_reports_371_days():
    directory = DATA / "aapl"
    assert directory.exists(), f"missing fixture: {directory}"
    xbrl = XBRL.from_directory(directory)

    period = _duration_period(xbrl, "2022-09-25", "2023-09-30")
    assert period is not None, "AAPL FY2023 duration period not found"
    assert period["days"] == 371
    # The classification windows must still place it, which is the thing a
    # one-day shift could have broken.
    assert period["period_type"] == "Annual"
    assert period["fiscal_period"] == "FY"


def test_netflix_quarter_reports_91_days():
    directory = DATA / "nflx" / "2024"
    assert directory.exists(), f"missing fixture: {directory}"
    xbrl = XBRL.from_directory(directory)

    period = _duration_period(xbrl, "2024-01-01", "2024-03-31")
    assert period is not None, "NFLX Q1 2024 duration period not found"
    assert period["days"] == 91
    assert period["period_type"] == "Quarterly"


def test_netflix_calendar_year_reports_365_days():
    directory = DATA / "nflx" / "2024"
    assert directory.exists(), f"missing fixture: {directory}"
    xbrl = XBRL.from_directory(directory)

    period = _duration_period(xbrl, "2023-01-01", "2023-12-31")
    assert period is not None, "NFLX FY2023 duration period not found"
    assert period["days"] == 365
    assert period["period_type"] == "Annual"


def test_rendering_a_statement_does_not_overwrite_the_days_field():
    """`periods.py` used to write its own exclusive count back over the public
    field while bucketing, which would have made `days` mean different things
    depending on whether a statement had been rendered first."""
    directory = DATA / "nflx" / "2024"
    assert directory.exists(), f"missing fixture: {directory}"
    xbrl = XBRL.from_directory(directory)

    def snapshot():
        return {(p["start_date"], p["end_date"]): p["days"]
                for p in xbrl.reporting_periods if p["type"] == "duration"}

    before = snapshot()
    xbrl.statements.income_statement()
    xbrl.statements.balance_sheet()
    assert snapshot() == before


def test_every_committed_duration_period_counts_inclusively():
    """The invariant, across every filing in the fixture tree: the stored count
    is the inclusive one."""
    from edgar.xbrl.core import duration_days

    checked = 0
    for name in ("aapl", "aeon", "gahc", "msft", "nflx/2010", "nflx/2024", "tsla", "unp"):
        directory = DATA / name
        assert directory.exists(), f"missing fixture: {directory}"
        for period in XBRL.from_directory(directory).reporting_periods:
            if period["type"] != "duration":
                continue
            assert period["days"] == duration_days(period["start_obj"], period["end_obj"]), (
                f"{name} {period['key']}"
            )
            checked += 1
    # 191 at the time of the fix. A lower bound so adding a fixture cannot
    # break this, while an empty or broken tree still fails loudly.
    assert checked >= 191, f"only {checked} duration periods checked"


# --- the selector must compare like with like -------------------------------

def test_prior_year_comparative_is_still_seeded_for_an_irregular_quarter():
    """`_seed_prior_year_matches` compares an anchor's duration against each
    candidate's, and both sides have to be counted the same way.

    This also pins the shadowing hazard that made the first draft of this fix
    wrong: `_select_quarterly_periods` binds a local for its bucket bounds, and
    a local named after the helper shadows it for every closure in the
    function. The resulting `TypeError` was swallowed by the `except TypeError`
    around the comparison, so seeding silently stopped happening and the whole
    suite stayed green.
    """
    from edgar.xbrl.period_selector import _select_quarterly_periods

    # A 105-day quarter, outside the 80-100 bucket, so the prior-year
    # comparative can only arrive through anchor seeding.
    periods = [
        {"key": "cur", "label": "Cur", "start_date": "2023-12-18",
         "end_date": "2024-03-31", "days": 105},
        {"key": "prior", "label": "Prior", "start_date": "2022-12-19",
         "end_date": "2023-03-31", "days": 103},
    ]
    selected = [key for key, _ in
                _select_quarterly_periods(periods, 4, period_of_report="2024-03-31")]
    assert selected == ["cur", "prior"]
