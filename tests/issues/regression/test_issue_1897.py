"""Balance-sheet (instant) facts get a fiscal_period.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1897

``xbrl().facts.to_dataframe()`` left ``fiscal_period`` empty on every instant
fact while ``fiscal_year`` was set: the period enrichment classified durations
only. On Microsoft's Q1 FY2027 10-Q (0001193125-26-436133) all 722 instant
facts had no fiscal period, so ``facts.get_facts_by_fiscal_period(2027, 'Q1')``
returned the 290 income and cash flow facts and none of the balance sheet.

An instant on the fiscal year end is now 'FY', one on another quarter end is
that quarter, and any other date (a cover-page share count date) stays empty.
After the fix the same query returns 701 facts.

Ground truth, read from the tracked fixtures:

* Apple 10-Q for the quarter ended 2023-07-01, accession 0000320193-23-000077
  (tests/fixtures/xbrl/aapl/10q_2023). Total assets $335,038,000,000 at
  2023-07-01 (Q3 FY2023; a 52/53-week quarter end that drifts into July) and
  $352,755,000,000 at 2022-09-24 (the FY2022 year end).
* Microsoft 10-K for FY2024, accession 0000950170-24-087843
  (tests/fixtures/xbrl/msft/10k_2024). Total assets $512,163,000,000 at
  2024-06-30 and $411,976,000,000 at 2023-06-30, both fiscal year ends.
"""

from datetime import date
from pathlib import Path

import pytest

from edgar.xbrl import XBRL
from edgar.xbrl.parsers.instance import _fiscal_period_for_instant

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "xbrl"


def _assets(fixture: str):
    df = XBRL.from_directory(FIXTURES / fixture).facts.to_dataframe()
    rows = df[(df["concept"] == "us-gaap:Assets") & (df["is_dimensioned"] != True)]  # noqa: E712
    return {
        row.period_instant: (row.numeric_value, row.fiscal_period, row.fiscal_year)
        for row in rows.itertuples()
    }


def test_apple_10q_balance_sheet_has_quarter_and_year_end_periods():
    assets = _assets("aapl/10q_2023")

    assert assets["2023-07-01"] == (335_038_000_000, "Q3", 2023)
    assert assets["2022-09-24"] == (352_755_000_000, "FY", 2022)


def test_microsoft_10k_balance_sheet_dates_are_fiscal_years():
    assets = _assets("msft/10k_2024")

    assert assets["2024-06-30"] == (512_163_000_000, "FY", 2024)
    assert assets["2023-06-30"] == (411_976_000_000, "FY", 2023)


def test_fiscal_period_query_returns_balance_sheet_facts():
    facts = XBRL.from_directory(FIXTURES / "aapl/10q_2023").facts

    q3 = facts.get_facts_by_fiscal_period(2023, "Q3")

    assert "us-gaap:Assets" in set(q3["concept"])


@pytest.mark.parametrize(
    "instant, fy_end, expected",
    [
        (date(2026, 9, 30), (6, 30), "Q1"),    # MSFT Q1 FY2027
        (date(2026, 12, 31), (6, 30), "Q2"),
        (date(2027, 3, 31), (6, 30), "Q3"),
        (date(2026, 6, 30), (6, 30), "FY"),
        (date(2026, 3, 28), (9, 26), "Q2"),    # AAPL 52/53-week quarter end
        (date(2023, 1, 1), (1, 1), "FY"),      # Sprouts: December year closing 01-01
        (date(2023, 4, 2), (1, 1), "Q1"),
        (date(2026, 10, 22), (6, 30), None),   # MSFT cover-page share count date
        (date(2024, 9, 16), (6, 30), None),    # mid-month date
        (date(2026, 8, 31), (6, 30), None),    # month end that closes no quarter
    ],
)
def test_fiscal_period_for_instant(instant, fy_end, expected):
    assert _fiscal_period_for_instant(instant, *fy_end) == expected
