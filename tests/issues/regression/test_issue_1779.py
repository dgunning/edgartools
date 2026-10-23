"""
Regression test: a Cardlytics 8-K table captioned "(Amounts in thousands, ...)" was scaled as
millions, so get_key_metrics() revenue was $63.249 billion instead of $63.2 million.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1779

_detect_table_scale looked for a caption only among the table's own siblings. Each Cardlytics
table is the only child of a wrapper <div>, so the caption one level up was never read and the
document-level fallback (millions, from one guidance sentence) won. The lookup now climbs
through one-child wrappers and reads the nearest preceding sibling first.
"""

import pytest

from edgar import find
from edgar.earnings import Scale, _detect_table_scale, _extract_clean_dataframe, parse_html

WRAPPED = """<html><body>
<p>Third quarter guidance (in millions, except for percentage change rates)</p>
<p>CONDENSED CONSOLIDATED STATEMENTS OF OPERATIONS (UNAUDITED)</p>
<p>(Amounts in thousands, except per share amounts)</p>
<div><table>
<tr><td></td><td>Three Months Ended June 30, 2025</td><td>Three Months Ended June 30, 2024</td></tr>
<tr><td>Revenue</td><td>63,249</td><td>69,636</td></tr>
<tr><td>Net loss</td><td>(9,283)</td><td>(4,257)</td></tr>
</table></div>
</body></html>"""


@pytest.mark.regression
def test_caption_before_a_wrapper_div_sets_the_scale():
    document = parse_html(WRAPPED)
    node = document.tables[0]
    assert len(node.parent.children) == 1  # the table sits alone in its wrapper
    df = _extract_clean_dataframe(node)
    assert _detect_table_scale(node, df, Scale.MILLIONS) == Scale.THOUSANDS


@pytest.mark.regression
@pytest.mark.network
@pytest.mark.vcr
def test_issue_1779_cardlytics_thousands():
    # Cardlytics 8-K 0001666071-25-000124, EX-99.1 statement of operations
    # "(Amounts in thousands, except per share amounts)": Revenue 63,249; Net Loss (9,283)
    earnings = find("0001666071-25-000124").obj().earnings
    assert earnings.income_statement.scale == Scale.THOUSANDS
    metrics = earnings.get_key_metrics()
    assert metrics["revenue"] == pytest.approx(63_249_000)
    assert metrics["net_income"] == pytest.approx(-9_283_000)


@pytest.mark.regression
@pytest.mark.network
@pytest.mark.vcr
def test_issue_1779_gartner_millions():
    # Gartner 8-K 0000749251-25-000044, EX-99.1 "(Unaudited; in millions, except per share data)":
    # Total revenues 1,686.5 for the three months ended June 30, 2025
    earnings = find("0000749251-25-000044").obj().earnings
    assert earnings.get_key_metrics()["revenue"] == pytest.approx(1_686_500_000)
