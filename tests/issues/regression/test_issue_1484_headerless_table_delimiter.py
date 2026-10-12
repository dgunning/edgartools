"""A headerless table keeps its delimiter row in pipe markdown.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1484

``Document.to_markdown()`` dropped the delimiter row for tables without
headers, because the header row and separator were only emitted inside the
``if expanded_headers:`` branch. A legitimate headerless table has empty
expanded headers, so the separator was skipped and the pipe table lost its
column structure. This test pins the exact markdown for a headerless
two-column table.
"""

import pytest

from edgar.documents import Document
from edgar.documents.table_nodes import Cell, Row, TableNode

pytestmark = pytest.mark.fast


def test_headerless_table_keeps_delimiter_row():
    table = TableNode(
        headers=[],
        rows=[
            Row([Cell("10"), Cell("20")]),
            Row([Cell("30"), Cell("40")]),
        ],
    )
    document = Document(root=table)
    assert document.to_markdown() == "|  |  |\n| --- | --- |\n| 10 | 20 |\n| 30 | 40 |"


def test_headerless_single_column_table_keeps_delimiter_row():
    table = TableNode(
        headers=[],
        rows=[
            Row([Cell("alpha")]),
            Row([Cell("beta")]),
        ],
    )
    document = Document(root=table)
    assert document.to_markdown() == "|  |\n| --- |\n| alpha |\n| beta |"
