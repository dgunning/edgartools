"""Quarter suffix one too high for quarters that end in a month's first week.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1738

52/53-week filers pin quarter ends to a weekday, so a quarter can end on day
1-7 of the month after the calendar quarter (Apple 2023-07-01, General
Dynamics 2023-07-02). `Statement.to_dataframe()` and the rendered header built
the (Qn) suffix from the bare end month, so those columns were labeled one
quarter too high. The parser's `_quarter_for_date()` already treats a
first-week end as the previous month (GH #816); both label paths now use it.

Ground truth: Apple 10-Q for the quarter ended 2023-07-01, accession
0000320193-23-000077 (fixture tests/fixtures/xbrl/aapl/10q_2023). The filing's
own dei:DocumentFiscalPeriodFocus is Q3 and it reports net sales of $81,797
million for the three months. Before the fix that column was "2023-07-01 (Q4)".
"""
from pathlib import Path

import pytest

from edgar.xbrl import XBRL
from edgar.xbrl.rendering import _format_period_labels

pytestmark = pytest.mark.fast

AAPL_10Q = Path("tests/fixtures/xbrl/aapl/10q_2023")
NET_SALES = "us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax"


@pytest.fixture(scope="module")
def income_statement():
    return XBRL.from_directory(AAPL_10Q).statements.income_statement()


def test_dataframe_labels_first_week_quarter_as_filed(income_statement):
    df = income_statement.to_dataframe()
    assert "2023-07-01 (Q3)" in df.columns
    assert "2023-07-01 (Q4)" not in df.columns
    row = df[df.concept == NET_SALES].iloc[0]
    assert row["2023-07-01 (Q3)"] == 81_797_000_000


def test_rendered_header_labels_first_week_quarter_as_filed(income_statement):
    text = str(income_statement.render())
    assert "Jul 1, 2023 (Q3)" in text
    assert "(Q4)" not in text


def test_december_year_end_first_week_quarter():
    # General Dynamics: three months ended 2023-07-02, December fiscal year end -> Q2
    periods = [("duration_2023-04-03_2023-07-02", "Three Months Ended")]
    formatted, _ = _format_period_labels(periods, {"fiscal_year_end_month": 12}, "IncomeStatement")
    assert formatted[0].quarter == "Q2"  # the end month alone gave Q3
