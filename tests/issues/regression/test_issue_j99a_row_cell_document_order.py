"""Regression test for edgartools-j99a: a row's cells come out in document order.

``TableProcessor._process_row`` emitted every ``td`` before every ``th``, so a
row written ``<th>Label</th><td>Revenue</td><td>100</td>`` became
``[Revenue, 100, Label]`` and the row label moved to the last column.
"""

from edgar.documents import parse_html
from edgar.documents.nodes import NodeType

MIXED_ROWS = """<html><body><table>
<tr><th>Label</th><td>Revenue</td><td>100</td></tr>
<tr><td>Cost</td><th>Mid</th><td>40</td></tr>
<tr><td>Net</td><td>x</td><td>60</td></tr>
</table></body></html>"""


def _table(html):
    tables = [node for node in parse_html(html).root.walk() if node.type == NodeType.TABLE]
    assert len(tables) == 1
    return tables[0]


def _all_rows(table):
    return [[cell.text() for cell in row] for row in table.headers] + \
           [[cell.text() for cell in row.cells] for row in table.rows]


def test_mixed_th_td_rows_keep_document_order():
    assert _all_rows(_table(MIXED_ROWS)) == [
        ["Label", "Revenue", "100"],
        ["Cost", "Mid", "40"],
        ["Net", "x", "60"],
    ]


def test_th_cells_stay_header_cells_after_reordering():
    table = _table(MIXED_ROWS)
    cells = [cell for row in table.headers for cell in row]
    header_flags = {cell.text(): cell.is_header for cell in cells}
    assert header_flags["Label"] is True
    assert header_flags["Mid"] is True
