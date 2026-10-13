"""Document Markdown must keep a multi-line body cell inside its table row.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1486

A body cell with a <br> (or several paragraphs) was emitted with its line
breaks, which ended the pipe row early: Markdown parsers then put the rest of
the cell and the following cells outside the table.
"""

import pytest
from markdown_it import MarkdownIt

from edgar.documents import HTMLParser, ParserConfig

pytestmark = pytest.mark.fast


def _markdown(cell_html: str) -> str:
    html = f"""<html><body><table>
<thead><tr><th>Item</th><th>Value</th></tr></thead>
<tbody><tr><td>{cell_html}</td><td>10</td></tr></tbody>
</table></body></html>"""
    return HTMLParser(ParserConfig()).parse(html).to_markdown()


def _table_cells(markdown: str) -> list[str]:
    """The text of every table cell, as a Markdown parser sees it."""
    tokens = MarkdownIt().enable("table").parse(markdown)
    return [token.content for previous, token in zip(tokens, tokens[1:])
            if previous.type in ("th_open", "td_open") and token.type == "inline"]


@pytest.mark.parametrize("cell_html", [
    "First<br>second",
    "First<br/><br/>second",
    "<p>First</p><p>second</p>",
])
def test_multiline_body_cell_stays_in_its_row(cell_html):
    markdown = _markdown(cell_html)

    assert "| First second | 10 |" in markdown
    assert _table_cells(markdown) == ["Item", "Value", "First second", "10"]
