"""
Regression test: a Cardlytics 8-K table captioned "(Amounts in thousands, ...)" was scaled as
millions, so get_key_metrics() revenue was $63.249 billion instead of $63.2 million.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1779

_detect_table_scale looked for a caption only among the table's own siblings. Each Cardlytics
table is the only child of a wrapper <div>, so the caption one level up was never read and the
document-level fallback (millions, from one guidance sentence) won. The lookup now climbs
through one-child wrappers and reads the nearest preceding sibling first.

Snail (edgartools-57v83) was the remainder. Its statement of operations prints whole dollars
with no caption, and the document-level fallback read "(in millions)" from the header of a
Bookings reconciliation table, so every undeclared table took millions. AMD has the same shape
(one table declares millions, the statement declares nothing) and there millions is right, so
position cannot decide. Magnitude does: an inherited scale that makes a table's largest amount
reach $10 trillion steps down to a smaller scale the document declares, else whole dollars.
The table check also reads every title row before the first row of amounts, not the first 3:
Mueller Water prints "(in millions...)" in its balance sheet's seventh row.
"""

from types import SimpleNamespace

import pytest

from edgar import find
from edgar.earnings import EarningsRelease, Scale, _detect_table_scale, _extract_clean_dataframe, parse_html

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


# A table's own header declares millions; the statement, three paragraphs later as in Snail's
# exhibit, declares nothing and prints whole dollars.
TABLE_LOCAL_DECLARATION = """<html><body>
<p>Snail, Inc. Reports Second Quarter 2025 Results</p>
<table>
<tr><td></td><td>Three Months Ended June 30, 2025</td><td>Three Months Ended June 30, 2024</td></tr>
<tr><td></td><td>(in millions)</td><td>(in millions)</td></tr>
<tr><td>Total net revenue</td><td>22.2</td><td>21.6</td></tr>
<tr><td>Bookings</td><td>27.1</td><td>22.9</td></tr>
</table>
<p>We define EBITDA as net loss before interest, taxes, depreciation and amortization.</p>
<p>About Snail, Inc.</p>
<p>Forward-Looking Statements</p>
<p>Condensed Consolidated Statements of Operations (Unaudited)</p>
<table>
<tr><td></td><td>Three months ended June 30, 2025</td><td>Three months ended June 30, 2024</td></tr>
<tr><td>Revenues, net</td><td>22,185,750</td><td>21,606,650</td></tr>
<tr><td>Net income (loss)</td><td>(16,562,706)</td><td>2,254,616</td></tr>
</table>
</body></html>"""

# The scale caption is the seventh row, after the title block and the period rows.
TITLE_BLOCK = """<html><body><table>
<tr><td></td></tr>
<tr><td>MUELLER WATER PRODUCTS, INC. AND SUBSIDIARIES</td></tr>
<tr><td>CONDENSED CONSOLIDATED BALANCE SHEETS</td></tr>
<tr><td>(UNAUDITED)</td></tr>
<tr><td></td><td>September 30,</td><td>September 30,</td></tr>
<tr><td></td><td>2025</td><td>2024</td></tr>
<tr><td>(in millions, except share amounts)</td></tr>
<tr><td>Cash and cash equivalents</td><td>431.5</td><td>309.9</td></tr>
<tr><td>Receivables, net</td><td>211.9</td><td>207.0</td></tr>
</table></body></html>"""


def _release(html):
    return EarningsRelease(SimpleNamespace(content=html, document="ex99-1.htm"))


@pytest.mark.regression
def test_an_impossible_inherited_scale_reads_whole_dollars():
    release = _release(TABLE_LOCAL_DECLARATION)
    assert release.detected_scale == Scale.MILLIONS
    bookings, operations = release.tables
    assert bookings.scale == Scale.MILLIONS
    assert operations.scale == Scale.UNITS  # 22,185,750 as millions would be $22 trillion


@pytest.mark.regression
def test_a_plausible_inherited_scale_is_kept():
    # AMD's shape: one "(in millions)" declaration, and a statement of 13,377 that declares nothing.
    release = _release(TABLE_LOCAL_DECLARATION.replace("22,185,750", "13,377").replace("21,606,650", "12,000")
                       .replace("(16,562,706)", "(1,243)").replace("2,254,616", "881"))
    assert release.tables[1].scale == Scale.MILLIONS


@pytest.mark.regression
def test_an_impossible_scale_steps_down_to_another_declared_scale():
    # Netflix's shape: the document declares millions and thousands; the statement is in thousands.
    html = TABLE_LOCAL_DECLARATION.replace("<body>", "<body><p>Paid memberships (in thousands) grew 8%.</p>")
    assert _release(html).tables[1].scale == Scale.THOUSANDS


@pytest.mark.regression
def test_scale_caption_after_the_title_rows_sets_the_scale():
    node = parse_html(TITLE_BLOCK).tables[0]
    df = _extract_clean_dataframe(node)
    assert _detect_table_scale(node, df, Scale.UNITS) == Scale.MILLIONS


@pytest.mark.regression
@pytest.mark.network
@pytest.mark.vcr
def test_issue_1779_snail_whole_dollars():
    # Snail 8-K 0001641172-25-024808, EX-99.1 ex99-1.htm statement of operations, no scale caption:
    # Revenues, net $ 22,185,750 and Net income (loss) (16,562,706), three months ended June 30, 2025.
    # The Bookings table, "(in millions)", gives Total net revenue $ 22.2.
    earnings = find("0001641172-25-024808").obj().earnings
    assert earnings.income_statement.scale == Scale.UNITS
    metrics = earnings.get_key_metrics()
    assert metrics["revenue"] == pytest.approx(22_185_750)
    assert metrics["net_income"] == pytest.approx(-16_562_706)
