"""
Regression test: an 8-K earnings table whose header sits in its data rows dropped the
"% Change" headers, so a percent change sat under the year-ago period.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1780

Home Bancorp's tables have no detected header rows. The fallback kept only the header cells
holding a date, but the "% Change" cells stayed in the data, so values filled the three date
labels left to right: 3/31/2024 got the percent change and the year-ago value went to Col_3.
The date row is now used as a header row for the grid-position layout from #1775, so "% Change"
is a column of its own; the caption row is no longer kept as data; and to_facts_dataframe()
no longer reports percent-change columns as USD amounts.
"""

import pytest

from edgar import find
from edgar.earnings import (
    FinancialTable,
    Scale,
    StatementType,
    _classify_row_type,
    _extract_clean_dataframe,
    parse_html,
)

NO_HEADER_TABLE = """<html><body><table>
<tr><td colspan="15">CONDENSED STATEMENTS OF INCOME</td></tr>
<tr><td colspan="3">(dollars in thousands, except per share data)</td><td colspan="3">3/31/2025</td><td colspan="3">12/31/2024</td><td colspan="3">% Change</td><td colspan="3">3/31/2024</td></tr>
<tr><td colspan="3">Total interest income</td><td colspan="3">47,201</td><td colspan="3">47,804</td><td colspan="3">(1)</td><td colspan="3">44,126</td></tr>
<tr><td colspan="3">Net income</td><td>$</td><td colspan="2">10,964</td><td>$</td><td colspan="2">9,673</td><td colspan="2">13</td><td>%</td><td>$</td><td colspan="2">9,199</td></tr>
</table></body></html>"""


@pytest.mark.regression
def test_percent_change_header_keeps_its_column():
    node = parse_html(NO_HEADER_TABLE).tables[0]
    assert not node.headers
    df = _extract_clean_dataframe(node)
    assert list(df.columns) == ["3/31/2025", "12/31/2024", "% Change", "3/31/2024"]
    assert list(df.index) == ["Total interest income", "Net income"]
    assert df.loc["Total interest income"].tolist() == [47201.0, 47804.0, -1.0, 44126.0]
    assert df.loc["Net income"].tolist() == [10964.0, 9673.0, 13.0, 9199.0]


@pytest.mark.regression
def test_percent_change_column_is_not_a_fact():
    df = _extract_clean_dataframe(parse_html(NO_HEADER_TABLE).tables[0])
    table = FinancialTable(dataframe=df, scale=Scale.THOUSANDS,
                           statement_type=StatementType.INCOME_STATEMENT,
                           row_types=[_classify_row_type(str(label)) for label in df.index])
    facts = table.to_facts_dataframe()
    assert facts[facts.label == "Net income"]["numeric_value"].tolist() == [10_964_000, 9_673_000, 9_199_000]


@pytest.mark.regression
@pytest.mark.network
@pytest.mark.vcr
def test_issue_1780_home_bancorp_year_ago_column():
    # Home Bancorp 8-K 0001436425-25-000016, EX-99.1 condensed income statement (thousands):
    # Total interest income 47,201 / 47,804 / (1)% / 44,126 / 7%; Net income 10,964 / 9,673 / 13% / 9,199 / 19%
    earnings = find("0001436425-25-000016").obj().earnings
    df = earnings.income_statement.dataframe
    assert list(df.columns) == ["3/31/2025", "12/31/2024", "% Change", "3/31/2024", "% Change"]
    assert df.loc["Total interest income"].tolist() == [47201.0, 47804.0, -1.0, 44126.0, 7.0]
    assert df.loc["Net income"].tolist() == [10964.0, 9673.0, 13.0, 9199.0, 19.0]


PERCENT_OF_SALES = """<html><body><table>
<tr><td></td><td colspan="4">Three Months Ended September 30,</td></tr>
<tr><td></td><td colspan="2">2025</td><td colspan="2">2024</td></tr>
<tr><td></td><td>Amount</td><td>%</td><td>Amount</td><td>%</td></tr>
<tr><td>Net sales</td><td>1,000</td><td>100.0</td><td>900</td><td>100.0</td></tr>
<tr><td>Net income</td><td>100</td><td>10.0</td><td>90</td><td>10.0</td></tr>
</table></body></html>"""


@pytest.mark.regression
def test_percent_column_under_a_year_is_not_a_fact():
    # "... - 2025 - %" carries a year but holds percent of sales, not an amount for 2025
    df = _extract_clean_dataframe(parse_html(PERCENT_OF_SALES).tables[0])
    table = FinancialTable(dataframe=df, scale=Scale.MILLIONS,
                           statement_type=StatementType.INCOME_STATEMENT,
                           row_types=[_classify_row_type(str(label)) for label in df.index])
    facts = table.to_facts_dataframe()
    sales = facts[facts.label == "Net sales"]
    assert sales["numeric_value"].tolist() == [1_000_000_000, 900_000_000]


@pytest.mark.regression
@pytest.mark.parametrize("label,expected", [
    ("% Change 2025 vs 2024", True),
    ("Three Months Ended September 30, - 2025 - %", True),
    ("vs. Q4 2024", True),
    ("% Change", True),
    ("Three Months Ended September 30, - 2025 - Amount", False),
    ("3/31/2025", False),
])
def test_change_column_detection(label, expected):
    from edgar.earnings import _is_change_column
    assert _is_change_column(label) is expected
