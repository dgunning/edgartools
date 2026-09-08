"""Regression test for issue #1253.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1253

`get_period_views("CashFlowStatement")` returned `[]` even for a filing whose
cash flow statement had been resolved and whose ordinary period selector had
already chosen comparable duration columns. `CashFlowStatement` was simply
absent from `STATEMENT_TYPE_CONFIG`, so the named views other primary
statements offer were unreachable, and `to_dataframe(period_view=...)` had no
name to accept.

`determine_periods_to_display` already handles cash flow and income statements
in one branch, so the entry mirrors the income statement's: duration periods,
three of them, with the same two named views.
"""

from pathlib import Path

import pytest

from edgar.xbrl import XBRL

DATA = Path(__file__).resolve().parents[3] / "data" / "xbrl" / "datafiles"
FIXTURES = ["aapl", "aeon", "aes", "gahc", "msft", "nflx", "tsla", "unp"]


@pytest.mark.parametrize("fixture", FIXTURES)
def test_cash_flow_offers_the_same_named_views_as_the_income_statement(fixture):
    """The two statements select from the same periods, so they must agree."""
    xbrl = XBRL.from_directory(DATA / fixture)

    income = [view["name"] for view in xbrl.get_period_views("IncomeStatement")]
    cash_flow = [view["name"] for view in xbrl.get_period_views("CashFlowStatement")]

    assert cash_flow == income


def test_a_named_view_can_be_passed_to_to_dataframe():
    xbrl = XBRL.from_directory(DATA / "aapl")

    views = xbrl.get_period_views("CashFlowStatement")
    assert views, "expected named cash-flow views for the AAPL fixture"
    assert "Three Recent Periods" in [view["name"] for view in views]

    statement = xbrl.statements.cash_flow_statement()
    frame = statement.to_dataframe(period_view=views[0]["name"])

    period_columns = [column for column in frame.columns if "20" in str(column)]
    assert period_columns, "the named view produced no period columns"
    assert len(period_columns) <= views[0].get("max_periods", 3) + 1

    # A view is only useful if the numbers come with it.
    operating = frame.loc[frame["concept"] == "us-gaap_NetCashProvidedByUsedInOperatingActivities"]
    assert not operating.empty
    assert operating[period_columns].notna().any().any()


def test_every_view_reports_the_period_keys_it_selected():
    xbrl = XBRL.from_directory(DATA / "aapl")

    for view in xbrl.get_period_views("CashFlowStatement"):
        assert view["name"]
        assert view["description"]
        assert view["period_keys"], f"{view['name']} selected no periods"
        assert all(key.startswith("duration_") for key in view["period_keys"])
