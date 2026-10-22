"""A headerless table promotes its first data row to a real header.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1484

``Document.to_markdown()`` only wrote the header row and the ``---`` delimiter
row inside the ``if expanded_headers:`` branch, so a headerless table lost its
delimiter row and was not a valid pipe table. Rather than give every layout
table an empty header bar, the renderer now promotes the first non-empty data
row to the header, keeps the delimiter row, and renders the remaining rows as
the body (GH #1524 review). A table with only one non-empty row -- a page
footer or a footnote -- keeps its plain row, since promoting it would leave a
header with a lone delimiter and no body. These tests pin the exact markdown for headerless
two-column and single-column tables.
"""

import pytest
from lxml import html as lxml_html
from markdown_it import MarkdownIt

from edgar.documents import Document, HTMLParser, ParserConfig
from edgar.documents.table_nodes import Cell, Row, TableNode

pytestmark = pytest.mark.fast


def test_headerless_table_promotes_first_row_to_header():
    table = TableNode(
        headers=[],
        rows=[
            Row([Cell("10"), Cell("20")]),
            Row([Cell("30"), Cell("40")]),
        ],
    )
    document = Document(root=table)
    assert document.to_markdown() == "| 10 | 20 |\n| --- | --- |\n| 30 | 40 |"


def test_headerless_single_column_table_promotes_first_row_to_header():
    table = TableNode(
        headers=[],
        rows=[
            Row([Cell("alpha")]),
            Row([Cell("beta")]),
        ],
    )
    document = Document(root=table)
    assert document.to_markdown() == "| alpha |\n| --- |\n| beta |"


def test_headerless_table_skips_blank_leading_rows_when_promoting():
    table = TableNode(
        headers=[],
        rows=[
            Row([Cell(""), Cell("")]),
            Row([Cell("10"), Cell("20")]),
            Row([Cell("30"), Cell("40")]),
        ],
    )
    document = Document(root=table)
    assert document.to_markdown() == "| 10 | 20 |\n| --- | --- |\n| 30 | 40 |"


@pytest.mark.parametrize(
    ("rows", "expected"),
    [
        ([Row([Cell("17"), Cell("Bank of America")])], "| 17 | Bank of America |"),
        (
            [Row([Cell(""), Cell("")]), Row([Cell("(1)"), Cell("Footnote text")]), Row([Cell(""), Cell("")])],
            "| (1) | Footnote text |",
        ),
    ],
    ids=["one-row", "one-non-empty-row"],
)
def test_single_row_headerless_table_is_not_promoted(rows, expected):
    # A page footer or footnote laid out as a one-row table would otherwise
    # become a header with a lone delimiter and no body (bac 10-K: 182 tables).
    document = Document(root=TableNode(headers=[], rows=rows))
    assert document.to_markdown() == expected


def _parsed_cells(document):
    markdown = document.to_markdown()
    parser = MarkdownIt().enable("table")
    assert sum(token.type == "table_open" for token in parser.parse(markdown)) == 1
    rendered = lxml_html.fromstring(parser.render(markdown))
    return [cell.text_content() for cell in rendered.xpath("//th | //td")]


@pytest.mark.parametrize("backslashes", range(5))
def test_promoted_literal_pipe_preserves_backslash_parity(backslashes):
    label = "alpha " + '\\' * backslashes + "| beta"
    table = TableNode(headers=[], rows=[Row([Cell(label), Cell("10")]), Row([Cell("Other"), Cell("20")])])

    assert _parsed_cells(Document(root=table)) == [label, "10", "Other", "20"]


@pytest.mark.parametrize("cell_html", ["First<br>second", "First<br/><br/>second", "<p>First</p><p>second</p>"])
def test_promoted_multiline_cell_remains_one_complete_header(cell_html):
    document = HTMLParser(ParserConfig()).parse(
        f"<html><body><table><tr><td>{cell_html}</td><td>10</td></tr>"
        "<tr><td>Other</td><td>20</td></tr></table></body></html>"
    )

    assert _parsed_cells(document) == ["First second", "10", "Other", "20"]
