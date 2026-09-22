"""Regression test for issue #1228.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1228

`to_dataframe(include_point_in_time=True)` returned `None` for Apple's cash-flow
beginning and ending balances, and `include_unit=True` returned NaN for the same
rows, even though the row metadata said `instant` and `usd` for every period it
had.

Both lookups walked the *displayed* period keys. A cash flow statement displays
duration columns while those two rows are instant facts, so their maps shared no
key with the columns at all and the loop fell out with nothing. Unit and period
type are properties of the concept -- an element's `periodType` is fixed by its
declaration -- so `edgar.xbrl.core.row_metadata_value` prefers a displayed
column and then falls back to anything the row has. The rule was written out
twice, in `Statement.to_dataframe` and in `RenderedStatement.to_dataframe`, and
both now call it.
"""

from pathlib import Path

import pytest

from edgar.xbrl import XBRL
from edgar.xbrl.core import row_metadata_value

DATA = Path(__file__).resolve().parents[3] / "data" / "xbrl" / "datafiles"
ROLE = "http://www.apple.com/role/CONSOLIDATEDSTATEMENTSOFCASHFLOWS"
CONCEPT = "us-gaap_CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"
ROWS = ("Cash, cash equivalents and restricted cash, beginning balances",
        "Cash, cash equivalents and restricted cash, ending balances")


def test_row_metadata_value_prefers_a_displayed_column_then_falls_back():
    displayed = ["duration_2022-09-25_2023-09-30"]

    # The case that was returning None: no overlap with the displayed columns.
    assert row_metadata_value({"instant_2023-09-30": "instant"}, displayed) == "instant"
    # A displayed column still wins over the rest of the map.
    assert row_metadata_value({"instant_2023-09-30": "instant",
                               "duration_2022-09-25_2023-09-30": "duration"},
                              displayed) == "duration"
    # Nothing to report stays None rather than becoming a guess.
    assert row_metadata_value({}, displayed) is None
    assert row_metadata_value(None, displayed) is None


@pytest.fixture(scope="module")
def aapl_cash_flow():
    directory = DATA / "aapl"
    assert directory.exists(), f"missing fixture: {directory}"
    return XBRL.from_directory(directory).statements[ROLE]


def test_instant_balances_report_point_in_time_and_unit(aapl_cash_flow):
    frame = aapl_cash_flow.to_dataframe(standard=False, view="standard",
                                        include_point_in_time=True,
                                        include_unit=True, presentation=False)

    rows = frame.loc[frame["concept"] == CONCEPT]
    assert len(rows) == 2, "expected the beginning and ending balance rows"
    assert set(rows["label"]) == set(ROWS)

    assert list(rows["point_in_time"]) == [True, True]
    assert list(rows["unit"]) == ["usd", "usd"]

    # The values these rows carry are the point of the statement; the fix must
    # not have moved them.
    ending = rows.loc[rows["label"] == ROWS[1]].iloc[0]
    assert ending["2023-09-30 (FY)"] == 30_737_000_000


def test_the_rendered_frame_agrees(aapl_cash_flow):
    frame = aapl_cash_flow.render().to_dataframe(include_point_in_time=True,
                                                 include_unit=True)

    rows = frame.loc[frame["concept"] == CONCEPT]
    assert list(rows["point_in_time"]) == [True, True]
    assert list(rows["unit"]) == ["usd", "usd"]


def test_duration_rows_are_still_reported_as_durations(aapl_cash_flow):
    frame = aapl_cash_flow.to_dataframe(standard=False, view="standard",
                                        include_point_in_time=True)

    operating = frame.loc[frame["concept"] == "us-gaap_NetCashProvidedByUsedInOperatingActivities"]
    assert len(operating) >= 1
    assert set(operating["point_in_time"]) == {False}
