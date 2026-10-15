"""Document Markdown must keep a multi-line body cell inside its table row.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1486

A body cell with a <br> (or several paragraphs) was emitted with its line
breaks, which ended the pipe row early: Markdown parsers then put the rest of
the cell and the following cells outside the table.
"""

import pytest

from edgar.documents import HTMLParser, ParserConfig

pytestmark = pytest.mark.fast


def _markdown(cell_html: str) -> str:
    html = f"""<html><body><table>
<thead><tr><th>Item</th><th>Value</th></tr></thead>
<tbody><tr><td>{cell_html}</td><td>10</td></tr></tbody>
</table></body></html>"""
    return HTMLParser(ParserConfig()).parse(html).to_markdown()


@pytest.mark.parametrize("cell_html", [
    "First<br>second",
    "First<br/><br/>second",
    "<p>First</p><p>second</p>",
])
def test_multiline_body_cell_stays_in_its_row(cell_html):
    lines = [line for line in _markdown(cell_html).splitlines() if line.strip()]

    # header, separator and one body row, each a complete two-cell pipe row
    assert lines == [
        "| Item | Value |",
        "| --- | --- |",
        "| First second | 10 |",
    ]
    for line in lines:
        assert line.startswith("|") and line.endswith("|")
        assert len(line.strip("|").split("|")) == 2
