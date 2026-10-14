"""A headerless table promotes its first data row to a real header.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1484

``Document.to_markdown()`` only wrote the header row and the ``---`` delimiter
row inside the ``if expanded_headers:`` branch, so a headerless table lost its
delimiter row and was not a valid pipe table. Rather than give every layout
table an empty header bar, the renderer now promotes the first non-empty data
row to the header, keeps the delimiter row, and renders the remaining rows as
the body (GH #1524 review). These tests pin the exact markdown for headerless
two-column and single-column tables.
"""

import pytest

from edgar.documents import Document
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
        ],
    )
    document = Document(root=table)
    assert document.to_markdown() == "| 10 | 20 |\n| --- | --- |"
