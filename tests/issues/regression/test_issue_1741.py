"""Stitched 10-Q columns are year-to-date; the guide called them quarterly.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1741

The default stitched 10-Q DataFrame keys each filing's year-to-date column by
bare end date, so three-, six- and nine-month amounts share one key form, and
docs/xbrl/guides/multi-period-analysis.md labeled that call a "Quarterly income
statement" without mentioning include_quarterly=True. The guide now says what
the default returns and how to get discrete quarters; these tests pin the
behaviour it documents. Renaming the default keys is left to the maintainer
(it would change the columns of every stitched 10-Q frame).

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
