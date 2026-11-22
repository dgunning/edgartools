"""Empty ``display:none`` spacer cells no longer take a slot in the table grid.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1847

Workiva-generated filings put empty ``<td colspan="3" style="display:none"/>``
cells inside table rows. A browser gives them no grid slot, but the table
processor counted their colspan, so a row carrying them was wider than the
header above it and every value after the first spacer slid right under the
next period. In JPMorgan's FY2024 10-K the firmwide reported-to-managed
reconciliation put the 2023 managed-basis overhead ratio (54%) under 2022.

Ground truth: JPMorgan Chase & Co. 10-K for the year ended December 31, 2024,
accession 0000019617-25-000270 (tracked fixture
tests/fixtures/html/jpm/10k/jpm-10-k-2025-02-14.html), "Overhead ratio" row:
Reported 52% / 55% / 59% and Managed basis 51% / 54% / 58% for 2024 / 2023 / 2022.
"""
from pathlib import Path

import pytest
from lxml import html as lxml_html

from edgar.documents import parse_html

JPM_10K = Path(__file__).parents[2] / "fixtures" / "html" / "jpm" / "10k" / "jpm-10-k-2025-02-14.html"


def _single_table(html: str):
    document = parse_html(html)
    assert len(document.tables) == 1
    return document.tables[0]


def _cell_lookup(frame, row_label: str):
    """{(year, basis): value} for the row whose first cell is ``row_label``."""
    row = next(i for i in range(len(frame)) if " ".join(str(frame.index[i]).split()) == row_label)
    values = {}
    for column, key in enumerate(frame.columns):
        year, basis = (" ".join(str(part).split()) for part in key)
        value = frame.iat[row, column]
        if basis in ("Reported", "Managed basis") and value not in (None, "", "%"):
            values.setdefault((year, basis), []).append(value)
    return values


@pytest.fixture(scope="module")
def jpm_reconciliation_table():
    root = lxml_html.fromstring(JPM_10K.read_bytes())
    for table in root.iter("table"):
        text = " ".join(table.text_content().split())
        if "Overhead ratio" in text and "Managedbasis" in text and "Fully taxable-equivalent" in text:
            return _single_table(lxml_html.tostring(table, encoding="unicode"))
    raise AssertionError("JPM reported-to-managed reconciliation table not found in fixture")


def test_jpm_overhead_ratio_years_follow_the_header(jpm_reconciliation_table):
    table = jpm_reconciliation_table
    # The hidden spacers no longer widen body rows past the 36-column year header.
    widths = {sum(cell.colspan for cell in row.cells) for row in table.rows}
    assert widths == {36}

    frame = table.to_dataframe()
    values = _cell_lookup(frame, "Overhead ratio")
    assert values == {
        ("2024", "Reported"): [52.0],
        ("2024", "Managed basis"): [51.0],
        ("2023", "Reported"): [55.0],
        ("2023", "Managed basis"): [54.0],
        ("2022", "Reported"): [59.0],
        ("2022", "Managed basis"): [58.0],
    }


def test_hidden_empty_spacer_takes_no_grid_slot():
    html = """
    <table>
      <tr><td></td><td colspan="2">2024</td><td colspan="2">2023</td></tr>
      <tr><td>Revenue</td><td>$</td><td>10</td>
          <td colspan="3" style="display:none"></td><td>$</td><td>20</td></tr>
    </table>
    """
    table = _single_table(html)
    assert [sum(c.colspan for c in row.cells) for row in table.rows] == [5]
    assert [c.text() for c in table.rows[0].cells] == ["Revenue", "$", "10", "$", "20"]


@pytest.mark.parametrize("style", ["visibility:hidden", "display: block", "display:none-ish"])
def test_cells_that_keep_layout_are_kept(style):
    html = f"""
    <table>
      <tr><td>Revenue</td><td style="{style}"></td><td>10</td></tr>
    </table>
    """
    table = _single_table(html)
    assert len(table.rows[0].cells) == 3


def test_hidden_cell_with_text_is_kept():
    # Only empty spacers are dropped: a hidden cell carrying text is filed content.
    html = """
    <table>
      <tr><td>Revenue</td><td style="DISPLAY: NONE">note</td><td>10</td></tr>
    </table>
    """
    table = _single_table(html)
    assert [c.text() for c in table.rows[0].cells] == ["Revenue", "note", "10"]


def test_row_of_only_hidden_spacers_is_kept():
    html = """
    <table>
      <tr><td colspan="3" style="display:none"></td></tr>
      <tr><td>Revenue</td><td>10</td></tr>
    </table>
    """
    table = _single_table(html)
    assert [len(row.cells) for row in table.rows] == [1, 2]
