"""Stitched 10-Q columns are year-to-date; the guide called them quarterly.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1741

The default stitched 10-Q DataFrame keys each filing's year-to-date column by
bare end date, so three-, six- and nine-month amounts share one key form, and
docs/xbrl/guides/multi-period-analysis.md labeled that call a "Quarterly income
statement" without mentioning include_quarterly=True. The guide now says what
the default returns and how to get discrete quarters; these tests pin the
behaviour it documents. The default keys are unchanged (renaming them would
change the columns of every stitched 10-Q frame); ``to_dataframe(period_columns=
"interval")`` is the opt-in that names each column by its exact dates.

Ground truth: Apple 10-Q for the quarter ended 2023-07-01, accession
0000320193-23-000077 (fixture tests/fixtures/xbrl/aapl/10q_2023): net sales of
$81,797 million for the three months and $293,787 million for the nine months.
"""
from pathlib import Path

import pytest

from edgar.xbrl import XBRL, XBRLS

pytestmark = pytest.mark.fast

GUIDE = Path("docs/xbrl/guides/multi-period-analysis.md")
NET_SALES = "us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax"


@pytest.fixture(scope="module")
def xbrls():
    return XBRLS.from_xbrl_objects([XBRL.from_directory("tests/fixtures/xbrl/aapl/10q_2023")])


def _net_sales(statement):
    df = statement.to_dataframe()
    return df[df.concept == NET_SALES].iloc[0]


def test_default_column_is_year_to_date(xbrls):
    statement = xbrls.statements.income_statement()
    assert statement.statement_data["periods"] == [
        ("duration_2022-09-25_2023-07-01", "Q3 YTD Jul 1, 2023")]
    assert _net_sales(statement)["2023-07-01"] == 293_787_000_000


def test_include_quarterly_adds_the_three_month_column(xbrls):
    row = _net_sales(xbrls.statements.income_statement(include_quarterly=True))
    assert row["Q3 Jul 1, 2023"] == 81_797_000_000
    assert row["Q3 YTD Jul 1, 2023"] == 293_787_000_000


def test_guide_documents_the_default_and_include_quarterly():
    text = GUIDE.read_text(encoding="utf-8")
    section = text[text.index("### Quarterly Analysis"):text.index("### Manual Period Inspection")]
    assert "include_quarterly=True" in section
    assert "year-to-date" in section
    assert "# Quarterly income statement" not in section


# --- Opt-in exact-interval column names --------------------------------------
#
# The default keys stay as they are (renaming them would change every stitched
# 10-Q frame). ``period_columns="interval"`` names each column by its exact
# dates, so a three-, six- or nine-month column says which it is, and a name does
# not change with the other periods selected.

QUARTER = "2023-04-02 to 2023-07-01"
NINE_MONTHS = "2022-09-25 to 2023-07-01"


def _interval_net_sales(statement):
    df = statement.to_dataframe(period_columns="interval")
    return df[df.concept == NET_SALES].iloc[0]


def test_interval_columns_name_the_quarter_and_the_nine_months(xbrls):
    row = _interval_net_sales(xbrls.statements.income_statement(include_quarterly=True))
    assert row[QUARTER] == 81_797_000_000
    assert row[NINE_MONTHS] == 293_787_000_000


def test_interval_name_does_not_depend_on_the_other_columns(xbrls):
    # Default selection drops the quarter; the nine-month column keeps its name,
    # where the end_date format switches between '2023-07-01' and a label
    row = _interval_net_sales(xbrls.statements.income_statement())
    assert row[NINE_MONTHS] == 293_787_000_000
    assert QUARTER not in row.index


def test_interval_instant_column_is_its_date(xbrls):
    df = xbrls.statements.balance_sheet().to_dataframe(period_columns="interval")
    assert df[df.concept == "us-gaap_Assets"].iloc[0]["2023-07-01"] == 335_038_000_000


def test_interval_columns_on_derived_cash_flow_quarter():
    """Apple 10-K 0000320193-23-000106 ($110,543M operating cash flow for FY2023)
    with the Q3 10-Q ($88,945M for nine months): the derived Q4 is named by its own
    dates since GH #1697."""
    stitched = XBRLS.from_xbrl_objects([
        XBRL.from_directory("tests/fixtures/xbrl/aapl/10k_2023"),
        XBRL.from_directory("tests/fixtures/xbrl/aapl/10q_2023"),
    ])
    df = stitched.statements.cash_flow_statement(discrete_quarters=True).to_dataframe(
        period_columns="interval")
    row = df[df.concept == "us-gaap_NetCashProvidedByUsedInOperatingActivities"].iloc[0]
    assert row["2023-07-02 to 2023-09-30"] == 21_598_000_000
    assert row[NINE_MONTHS] == 88_945_000_000


def test_xbrls_to_dataframe_passes_the_option_through(xbrls):
    df = xbrls.to_dataframe("IncomeStatement", period_columns="interval")
    assert df[df.concept == NET_SALES].iloc[0][NINE_MONTHS] == 293_787_000_000


def test_default_column_names_are_unchanged(xbrls):
    statement = xbrls.statements.income_statement(include_quarterly=True)
    default = statement.to_dataframe()
    assert list(default.columns) == statement.to_dataframe(period_columns="end_date").columns.tolist()
    assert "Q3 Jul 1, 2023" in default.columns


def test_unknown_period_columns_value_is_a_useful_error(xbrls):
    with pytest.raises(ValueError, match="period_columns must be one of"):
        xbrls.statements.income_statement().to_dataframe(period_columns="intervals")


def test_malformed_period_id_is_an_error_not_a_guess():
    from edgar.xbrl.stitching.utils import period_column_names

    with pytest.raises(ValueError, match="duration_<start>_<end>"):
        period_column_names([("2023-07-01", "Jul 1, 2023")], "interval")


def test_guide_documents_interval_columns():
    text = GUIDE.read_text(encoding="utf-8")
    section = text[text.index("### Quarterly Analysis"):text.index("### Manual Period Inspection")]
    assert 'period_columns="interval"' in section
    assert QUARTER in section
