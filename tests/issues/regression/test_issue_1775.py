"""
Regression test: a scale caption in an 8-K earnings table header shifted every value one
column, so the current-period header returned the prior period.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1775

The header cell over the row labels ("In millions, except per share amounts") was kept as a
column, and header labels and value cells were zipped left to right, so each value sat one
column early. Values are now placed under the header cell above them by grid position, and a
scale caption is never a column. When positions do not line up, the old layout is kept.
"""

import pytest

from edgar import find
from edgar.earnings import _extract_clean_dataframe, _is_scale_caption, parse_html


def _table(html_rows: str):
    return parse_html(f"<html><body><table>{html_rows}</table></body></html>").tables[0]


CAPTIONED = """
<tr><td colspan="3"></td><td colspan="6"><b>Three Months Ended June 30,</b></td><td colspan="6"><b>Six Months Ended June 30,</b></td></tr>
<tr><td colspan="3"><b>In millions, except per share amounts</b></td><td colspan="3"><b>2025</b></td><td colspan="3"><b>2024</b></td><td colspan="3"><b>2025</b></td><td colspan="3"><b>2024</b></td></tr>
<tr><td colspan="3">Net Income</td><td>$</td><td>104</td><td></td><td>$</td><td>190</td><td></td><td>$</td><td>231</td><td></td><td>$</td><td>355</td><td></td></tr>
<tr><td colspan="3">Margin</td><td colspan="2">15.3</td><td>%</td><td colspan="2">18.0</td><td>%</td><td colspan="2">16.2</td><td>%</td><td colspan="2">17.0</td><td>%</td></tr>
"""


@pytest.mark.regression
def test_caption_is_not_a_column_and_values_stay_under_their_period():
    df = _extract_clean_dataframe(_table(CAPTIONED))
    assert list(df.columns) == [
        "Three Months Ended June 30, - 2025", "Three Months Ended June 30, - 2024",
        "Six Months Ended June 30, - 2025", "Six Months Ended June 30, - 2024",
    ]
    assert df.loc["Net Income"].tolist() == [104.0, 190.0, 231.0, 355.0]
    # A "%" printed in its own cell joins its number instead of taking the next column
    assert df.loc["Margin"].tolist() == [15.3, 18.0, 16.2, 17.0]


@pytest.mark.regression
@pytest.mark.parametrize("caption,expected", [
    ("In millions, except per share amounts", True),
    ("(IN THOUSANDS, EXCEPT PER SHARE AND SHARE DATA)", True),
    ("($ In Millions, Except Per Share Amounts)", True),
    ("(dollars in thousands, except per share data)", True),
    ("Three Months Ended June 30,", False),
    ("Increase (Decrease)", False),
])
def test_scale_caption_wording(caption, expected):
    assert _is_scale_caption(caption) is expected


@pytest.mark.regression
@pytest.mark.network
@pytest.mark.vcr
def test_issue_1775_graphic_packaging_net_income_under_its_quarter():
    # Graphic Packaging 8-K 0001408075-25-000020, EX-99.1: Net Income $104 (Q2 2025), $190 (Q2 2024)
    earnings = find("0001408075-25-000020").obj().earnings
    df = earnings.income_statement.dataframe
    row = list(df.index).index("Net Income")
    assert df.iloc[row, :2].tolist() == [104.0, 190.0]
    assert earnings.get_key_metrics()["net_income"] == pytest.approx(104_000_000)


@pytest.mark.regression
@pytest.mark.network
@pytest.mark.vcr
def test_issue_1775_home_depot_current_quarter():
    # Home Depot 8-K 0000354950-26-000026, EX-99.1, quarter ended February 1, 2026 (millions):
    # Net sales 38,198, Net earnings 2,571, Diluted earnings per share 2.58
    metrics = find("0000354950-26-000026").obj().earnings.get_key_metrics()
    assert metrics["revenue"] == pytest.approx(38_198_000_000)
    assert metrics["net_income"] == pytest.approx(2_571_000_000)
    assert metrics["eps_diluted"] == pytest.approx(2.58)
