"""Regression test for edgartools-c7kh: unbounded colspan/rowspan blows up memory.

Filing 0001193125-06-185884 contains a corrupt cell,
``<td valign="bottom" colspan="376967340" align="center">``. ``_process_cell``
accepted any digit string, and ``TableMatrix`` multiplies the span into a real
allocation: ``_calculate_dimensions`` set ``col_count`` to ~377M and
``build_from_rows`` then materialised that many ``MatrixCell`` objects *per row*.
A minimal repro reached 6.3GB RSS in 20 seconds; the reporter saw ~700GB.

Spans are now clamped at parse time (``TableProcessor.MAX_COLSPAN`` /
``MAX_ROWSPAN``) with a hard grid-width cap in ``TableMatrix.MAX_COLUMNS`` as a
backstop for callers that build ``Cell`` objects directly.
"""

import time

import lxml.html
import pytest

from edgar.documents import parse_html
from edgar.documents.config import ParserConfig
from edgar.documents.nodes import NodeType
from edgar.documents.strategies.table_processing import TableProcessor
from edgar.documents.table_nodes import Cell, Row
from edgar.documents.utils.table_matrix import TableMatrix

# The corrupt cell as it appears in filing 0001193125-06-185884.
OVERFLOW_COLSPAN = 376967340

CORRUPT_TABLE_HTML = f"""<html><body>
<table border="0" cellpadding="0" cellspacing="0" width="100%">
<tr>
<td valign="bottom"><font size="2">&#160;</font></td>
<td align="left"><font size="2">&#160;</font></td>
<td valign="bottom" colspan="{OVERFLOW_COLSPAN}" align="center"><font size="2"> </font></td>
<td valign="bottom" colspan="2" align="center"><hr size="1" noshade></td>
</tr>
<tr>
<td width="4%" valign="bottom"><font size="2">&#160;</font></td>
<td valign="bottom" align="left"><font size="2">ProFund VP Asia 30</font></td>
<td width="1%"><font size="2">&#160;</font></td>
</tr>
</table>
</body></html>"""

# Generous relative to the ~5ms the fixed parser takes, tight enough that the
# pre-fix behaviour (tens of seconds and multiple GB) cannot pass.
PARSE_BUDGET_SECONDS = 5.0


def test_corrupt_colspan_is_clamped_at_parse_time():
    start = time.perf_counter()
    doc = parse_html(CORRUPT_TABLE_HTML)
    elapsed = time.perf_counter() - start

    assert elapsed < PARSE_BUDGET_SECONDS, f"parse took {elapsed:.1f}s"

    tables = [node for node in doc.root.walk() if node.type == NodeType.TABLE]
    assert len(tables) == 1

    first_row = tables[0].rows[0]
    assert [cell.colspan for cell in first_row.cells] == [1, 1, TableProcessor.MAX_COLSPAN, 2]

    # The real content survives the clamp.
    assert tables[0].rows[1].cells[1].text() == "ProFund VP Asia 30"


def test_clamped_table_renders_without_allocating_millions_of_columns():
    """The clamped table still goes through TableMatrix at render time."""
    element = lxml.html.fromstring(CORRUPT_TABLE_HTML).find(".//table")
    table = TableProcessor(ParserConfig()).process(element)

    start = time.perf_counter()
    matrix = TableMatrix().build_from_rows(table.headers, table.rows)
    elapsed = time.perf_counter() - start

    assert elapsed < PARSE_BUDGET_SECONDS, f"matrix build took {elapsed:.1f}s"
    assert matrix.col_count <= TableMatrix.MAX_COLUMNS
    assert matrix.row_count == 2

    assert "ProFund VP Asia 30" in table.text()


@pytest.mark.parametrize("attribute", ["colspan", "rowspan"])
def test_span_attributes_are_bounded(attribute):
    html = (
        f'<table><tr><td {attribute}="{OVERFLOW_COLSPAN}">A</td><td>B</td></tr>'
        f"<tr><td>C</td><td>D</td></tr></table>"
    )
    element = lxml.html.fromstring(html)
    table = TableProcessor(ParserConfig()).process(element)

    cell = table.rows[0].cells[0] if table.rows else table.headers[0][0]
    limit = TableProcessor.MAX_COLSPAN if attribute == "colspan" else TableProcessor.MAX_ROWSPAN
    assert getattr(cell, attribute) == limit


def test_table_matrix_caps_width_for_directly_built_cells():
    """Defense in depth: Cells can reach TableMatrix without passing the parser."""
    rows = [Row(cells=[Cell(content="a", colspan=OVERFLOW_COLSPAN), Cell(content="b")])]

    start = time.perf_counter()
    matrix = TableMatrix().build_from_rows([], rows)
    elapsed = time.perf_counter() - start

    assert elapsed < PARSE_BUDGET_SECONDS, f"matrix build took {elapsed:.1f}s"
    assert matrix.col_count == TableMatrix.MAX_COLUMNS


def test_ordinary_spans_are_untouched():
    """The clamp must not disturb the spans real filings actually use."""
    rows = [
        Row(cells=[Cell(content="x", colspan=2), Cell(content="y")]),
        Row(cells=[Cell(content="1"), Cell(content="2"), Cell(content="3")]),
    ]
    matrix = TableMatrix().build_from_rows([], rows)

    assert matrix.col_count == 3
    assert [[c.text() if c else None for c in row] for row in matrix.to_cell_grid()] == [
        ["x", None, "y"],
        ["1", "2", "3"],
    ]
