"""Regression test for edgartools-grn9e: a table cell stays on its own row in every format.

The grid and simple table formats wrote cell text raw, so a cell holding a
``<br>`` split its row across several lines and the value after it landed in
no column. The pipe format already collapsed whitespace and escaped ``|``; the
pipe cases here pin that behaviour for the same input.
"""

import pytest

from edgar.documents import parse_html
from edgar.documents.nodes import NodeType
from edgar.documents.renderers.markdown import MarkdownRenderer

HTML = """<html><body><table>
<tr><th>Item</th><th>2025</th></tr>
<tr><td>x|y</td><td>1</td></tr>
<tr><td>Line one<br>line two</td><td>2</td></tr>
<tr><td>Other</td><td>3</td></tr>
</table></body></html>"""


def _render(table_format):
    table = [node for node in parse_html(HTML).root.walk() if node.type == NodeType.TABLE][0]
    renderer = MarkdownRenderer()
    renderer.table_format = table_format
    return renderer._render_table(table)


@pytest.mark.parametrize("table_format", ["pipe", "grid", "simple"])
def test_cell_with_line_break_stays_on_its_row(table_format):
    lines = _render(table_format).splitlines()
    row = [line for line in lines if "Line one" in line]
    assert len(row) == 1
    assert "Line one line two" in row[0]
    assert "2" in row[0].split("line two", 1)[1]


def test_grid_and_simple_have_one_line_per_row():
    assert len(_render("grid").splitlines()) == 6  # border, 4 rows, border
    assert [line for line in _render("simple").splitlines() if line] == [
        "Item  2025", "x|y  1", "Line one line two  2", "Other  3",
    ]


def test_pipe_body_cell_escapes_pipe():
    assert "| x\\|y | 1 |" in _render("pipe").splitlines()
