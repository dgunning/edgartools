"""Regression test for edgartools-t6z2: nested tables reprocessed by every ancestor.

``_process_table_structure`` collected rows with ``rows_container.findall('.//tr')``
and ``_process_row`` collected cells with ``tr.findall('.//td')``. Both are
descendant-axis scans, so a table picked up the rows of every table nested inside
its own cells. On filing 0000880195-09-000191 (an N-PX with 8207 tables nested up
to 26 deep) that made ``_process_row`` run 1,102,497 times for 97,833 actual
``<tr>`` elements, and ``FilingSGML.text()`` took over three hours.

The cost is only half the problem: the inner tables' cells were silently
duplicated into the outer table's structure, so the extracted data was wrong.
Both traversals are now scoped to the element's own rows and cells.
"""

import lxml.html

from edgar.documents import parse_html
from edgar.documents.config import ParserConfig
from edgar.documents.nodes import NodeType
from edgar.documents.strategies.table_processing import TableProcessor

NESTED_HTML = """<html><body>
<table>
  <tr><td>OUTER_A1</td><td>OUTER_B1</td></tr>
  <tr>
    <td>OUTER_A2</td>
    <td>
      <table>
        <tr><td>MID_A1</td><td>MID_B1</td></tr>
        <tr>
          <td>MID_A2</td>
          <td>
            <table>
              <tr><td>INNER_A1</td><td>INNER_B1</td></tr>
            </table>
          </td>
        </tr>
      </table>
    </td>
  </tr>
  <tr><td>OUTER_A3</td><td>OUTER_B3</td></tr>
</table>
</body></html>"""


def _norm(text):
    """Collapse the whitespace the source HTML's indentation leaves in cell text."""
    return " ".join(text.split())


def _rows_as_text(table):
    return [[_norm(cell.text()) for cell in row.cells] for row in table.rows]


def test_outer_table_keeps_only_its_own_rows():
    doc = parse_html(NESTED_HTML)
    tables = [node for node in doc.root.walk() if node.type == NodeType.TABLE]
    assert len(tables) == 1

    rows = _rows_as_text(tables[0])
    assert len(rows) == 3
    assert rows[0] == ["OUTER_A1", "OUTER_B1"]
    assert rows[2] == ["OUTER_A3", "OUTER_B3"]

    # The nested tables contribute exactly one cell to the outer table: the
    # text of the cell that contains them, not extra rows or extra cells.
    assert len(rows[1]) == 2
    assert rows[1][0] == "OUTER_A2"
    assert rows[1][1] == "MID_A1 MID_B1 MID_A2 INNER_A1 INNER_B1"


def test_inner_rows_are_not_duplicated_into_the_outer_table():
    doc = parse_html(NESTED_HTML)
    table = next(node for node in doc.root.walk() if node.type == NodeType.TABLE)
    rows = _rows_as_text(table)

    # Before the fix the outer table gained rows ['MID_A1', 'MID_B1'],
    # ['MID_A2', 'INNER_A1 INNER_B1'] and ['INNER_A1', 'INNER_B1'], and its
    # OUTER_A2 row grew to six cells.
    assert ["MID_A1", "MID_B1"] not in rows
    assert ["INNER_A1", "INNER_B1"] not in rows

    # Each outer label appears in exactly one cell of the outer structure.
    flat = [text for row in rows for text in row]
    for label in ("OUTER_A1", "OUTER_B1", "OUTER_A2", "OUTER_A3", "OUTER_B3"):
        assert flat.count(label) == 1, f"{label} appears {flat.count(label)} times"


def test_nested_tables_are_still_parsed_as_their_own_tables():
    """Callers that enumerate every <table> (e.g. Section._get_tables_from_toc_section
    uses ``tree.xpath('.//table')``) must still get complete inner tables."""
    processor = TableProcessor(ParserConfig())
    elements = lxml.html.fromstring(NESTED_HTML).xpath(".//table")
    assert len(elements) == 3

    outer, mid, inner = (processor.process(element) for element in elements)

    assert len(_rows_as_text(outer)) == 3
    assert _rows_as_text(mid) == [
        ["MID_A1", "MID_B1"],
        ["MID_A2", "INNER_A1 INNER_B1"],
    ]
    assert _rows_as_text(inner) == [["INNER_A1", "INNER_B1"]]


def test_row_processing_is_not_repeated_per_nesting_level():
    """Each <tr> is processed exactly once by the table that owns it."""
    processor = TableProcessor(ParserConfig())
    processed = []
    original = processor._process_row

    def counting_process_row(tr, is_header):
        processed.append(tr)
        return original(tr, is_header)

    processor._process_row = counting_process_row
    processor.process(lxml.html.fromstring(NESTED_HTML).find(".//table"))

    # Three own rows, none of the four rows belonging to the nested tables.
    assert len(processed) == 3
    assert len({id(tr) for tr in processed}) == 3


def test_thead_tbody_and_tfoot_rows_are_scoped_to_their_own_table():
    html = """<table>
      <thead><tr><th>H1</th><th>H2</th></tr></thead>
      <tbody>
        <tr><td>D1</td><td>
          <table><thead><tr><th>NESTED_H</th></tr></thead>
                 <tbody><tr><td>NESTED_D</td></tr></tbody>
                 <tfoot><tr><td>NESTED_F</td></tr></tfoot></table>
        </td></tr>
      </tbody>
      <tfoot><tr><td>F1</td><td>F2</td></tr></tfoot>
    </table>"""
    table = TableProcessor(ParserConfig()).process(lxml.html.fromstring(html))

    assert [[_norm(c.text()) for c in header] for header in table.headers] == [["H1", "H2"]]
    assert _rows_as_text(table) == [["D1", "NESTED_H NESTED_D NESTED_F"]]
    assert [[_norm(c.text()) for c in row.cells] for row in table.footer] == [["F1", "F2"]]


def test_deep_nesting_stays_linear():
    """26-deep nesting is real (filing 0000880195-09-000191); it must not blow up."""
    depth = 26
    html = "<td>LEAF</td>"
    for level in reversed(range(depth)):
        html = f"<table><tr><td>L{level}</td><td><table><tr>{html}</tr></table></td></tr></table>"

    processor = TableProcessor(ParserConfig())
    call_count = 0
    original = processor._process_row

    def counting_process_row(tr, is_header):
        nonlocal call_count
        call_count += 1
        return original(tr, is_header)

    processor._process_row = counting_process_row
    table = processor.process(lxml.html.fromstring(html))

    # The outermost table owns exactly one row regardless of nesting depth.
    assert call_count == 1
    assert _norm(table.rows[0].cells[0].text()) == "L0"
    assert len(table.rows[0].cells) == 2
