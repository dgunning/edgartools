"""
Regression test: ASGN's 8-K earnings table had 3 header labels for 5 value columns, so
columns were mislabelled, the nine-month columns were dropped and get_key_metrics() was all None.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1777

Causes, all fixed here on top of the grid-position layout from #1775:
- the empty cell over the row labels has rowspan="2", so the month row starts one cell later;
  header placement now honours rowspan, so each year sits under its own month and group;
- a repeated period label ("September 30,") made ``df.iloc[pos][col]`` return several cells,
  so get_key_metrics() and to_facts_dataframe() skipped it; both now read columns by position;
- stacked headers are joined with " - " ("September 30, - 2025"), which the period parser
  did not read, so facts had no period end;
- a negative printed as "(636" with its ")" in the spacer cell after it was left as a value.
"""

import pandas as pd
import pytest

from edgar import find
from edgar.earnings import (
    EarningsRelease,
    FinancialTable,
    Scale,
    StatementType,
    _classify_row_type,
    _extract_clean_dataframe,
    _parse_period_header,
    parse_html,
)

ROWSPAN_TABLE = """<html><body><table>
<tr><td colspan="3" rowspan="2"></td><td colspan="9"><b>Three Months Ended</b></td><td colspan="6"><b>Nine Months Ended</b></td></tr>
<tr><td colspan="6"><b>September 30,</b></td><td colspan="3"><b>June 30,</b></td><td colspan="6"><b>September 30,</b></td></tr>
<tr><td colspan="3"></td><td colspan="3"><b>2025</b></td><td colspan="3"><b>2024</b></td><td colspan="3"><b>2025</b></td><td colspan="3"><b>2025</b></td><td colspan="3"><b>2024</b></td></tr>
<tr><td colspan="3">Revenues</td><td>$</td><td>1,011.4</td><td></td><td>$</td><td>1,031.0</td><td></td><td>$</td><td>1,020.6</td><td></td><td>$</td><td>3,000.3</td><td></td><td>$</td><td>3,114.7</td><td></td></tr>
<tr><td colspan="3">Loss from operations</td><td>(636</td><td>)</td><td></td><td colspan="2">(1,054)</td><td></td><td colspan="2">(10)</td><td></td><td colspan="2">(1,413)</td><td></td><td colspan="2">(1,925)</td><td></td></tr>
</table></body></html>"""


@pytest.mark.regression
def test_rowspan_header_gives_each_value_its_own_period():
    df = _extract_clean_dataframe(parse_html(ROWSPAN_TABLE).tables[0])
    assert list(df.columns) == [
        "Three Months Ended - September 30, - 2025",
        "Three Months Ended - September 30, - 2024",
        "Three Months Ended - June 30, - 2025",
        "Nine Months Ended - September 30, - 2025",
        "Nine Months Ended - September 30, - 2024",
    ]
    assert df.loc["Revenues"].tolist() == [1011.4, 1031.0, 1020.6, 3000.3, 3114.7]
    assert df.loc["Loss from operations"].tolist() == [-636.0, -1054.0, -10.0, -1413.0, -1925.0]


@pytest.mark.regression
def test_stacked_header_period_is_parsed():
    info = _parse_period_header("Nine Months Ended - September 30, - 2024")
    assert info["period_end"].isoformat() == "2024-09-30"
    assert info["duration_months"] == 9


@pytest.mark.regression
def test_repeated_period_label_is_still_read():
    labels = ["Revenues", "Net income"]
    df = pd.DataFrame([[1011.4, 1031.0], [38.1, 47.5]], index=labels,
                      columns=["September 30,", "September 30,"]).astype(object)
    table = FinancialTable(dataframe=df, scale=Scale.MILLIONS,
                           statement_type=StatementType.INCOME_STATEMENT,
                           row_types=[_classify_row_type(label) for label in labels], periods=[])
    release = EarningsRelease.__new__(EarningsRelease)
    release._tables = [table]
    metrics = release.get_key_metrics()
    assert metrics["revenue"] == pytest.approx(1_011_400_000)
    assert metrics["net_income"] == pytest.approx(38_100_000)
    facts = table.to_facts_dataframe()
    assert facts[facts.label == "Revenues"]["value"].tolist() == ["1011.4", "1031.0"]


@pytest.mark.regression
@pytest.mark.network
@pytest.mark.vcr
def test_issue_1777_asgn_q3_2025_columns():
    # ASGN 8-K 0000890564-25-000058, EX-99.1 "Results of Operations" (millions):
    # Revenues 1,011.4 / 1,031.0 / 1,020.6 / 3,000.3 / 3,114.7; Q3 2025 net income 38.1, diluted EPS 0.87
    earnings = find("0000890564-25-000058").obj().earnings
    income = earnings.income_statement
    assert income.dataframe.loc["Revenues"].tolist() == [1011.4, 1031.0, 1020.6, 3000.3, 3114.7]
    metrics = earnings.get_key_metrics()
    assert metrics["revenue"] == pytest.approx(1_011_400_000)
    assert metrics["net_income"] == pytest.approx(38_100_000)
    assert metrics["eps_diluted"] == pytest.approx(0.87)
    facts = income.to_facts_dataframe()
    revenues = facts[facts.label == "Revenues"]
    assert [d.isoformat() for d in revenues["period_end"]] == [
        "2025-09-30", "2024-09-30", "2025-06-30", "2025-09-30", "2024-09-30"]


@pytest.mark.regression
def test_huge_header_span_is_bounded():
    # Filer-written spans: rowspan="10000" colspan="1000" over two header rows used to build
    # ten million occupancy cells (seconds); it must stay fast and still place the next row.
    import time

    from edgar.earnings import _place_header_cells

    class _Cell:
        def __init__(self, content, colspan=1, rowspan=1):
            self.content, self.colspan, self.rowspan = content, colspan, rowspan

    rows = [[_Cell("", 1000, 10000), _Cell("2025"), _Cell("2024")], [_Cell("x"), _Cell("2025")]]
    start = time.perf_counter()
    placed = _place_header_cells(rows)
    assert time.perf_counter() - start < 0.1
    assert placed[0] == [(0, 1000, ""), (1000, 1001, "2025"), (1001, 1002, "2024")]
    assert placed[1] == [(1000, 1001, "x"), (1001, 1002, "2025")]
