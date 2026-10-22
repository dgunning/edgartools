"""Regression test for GH #1483: literal pipes and backslashes in Markdown table cells.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1483

`Document.to_markdown()` escaped `|` and `\\` only in grouped (multi-row) headers
and in a promoted header row. A flat header and every body cell went out raw, so
a literal pipe opened an extra column and a lone backslash escaped the character
after it. A Markdown reader then saw three header cells over a two-column
delimiter, and rendered the whole table as a paragraph.

AbbVie's FY2024 10-K (accession 0001551152-25-000020) puts a pipe in its page
footer cell, "| 2024 Form 10-K", beside the page number. Of the 85 tracked HTML
fixtures, that is the only filing whose Markdown changes.
"""
from pathlib import Path

import pytest
from lxml import html as lxml_html
from markdown_it import MarkdownIt

from edgar.documents import HTMLParser, ParserConfig

ABBV_10K = Path("tests/fixtures/html/abbv/10k/abbv-10-k-2025-02-14.html")


def _markdown(source: str) -> str:
    return HTMLParser(ParserConfig()).parse(source).to_markdown()


def _read_tables(markdown: str):
    """Every table a Markdown reader finds, as (headers, rows) of cell text."""
    rendered = MarkdownIt("commonmark").enable("table").render(markdown)
    if "<table" not in rendered:
        return []
    tables = []
    for table in lxml_html.fromstring(rendered).xpath("//table"):
        headers = [cell.text_content() for cell in table.xpath("./thead/tr/th")]
        rows = [[cell.text_content() for cell in row.xpath("./td")] for row in table.xpath("./tbody/tr")]
        tables.append((headers, rows))
    return tables


def _table(head: str, body: str) -> str:
    return f"<html><body><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></body></html>"


@pytest.mark.fast
def test_flat_header_escapes_pipe_and_backslash():
    markdown = _markdown(_table(r"<th>Metric</th><th>Revenue | margin\_forecast</th>",
                                "<tr><td>Revenue</td><td>10</td></tr>"))

    assert markdown.strip() == "| Metric | Revenue \\| margin\\\\_forecast |\n| --- | --- |\n| Revenue | 10 |"
    assert _read_tables(markdown) == [(["Metric", r"Revenue | margin\_forecast"], [["Revenue", "10"]])]


@pytest.mark.fast
def test_body_cells_escape_pipe_and_backslash():
    markdown = _markdown(_table("<th>Metric</th><th>Value</th>",
                                r"<tr><td>A | B</td><td>10</td></tr><tr><td>C\D</td><td>20</td></tr>"))

    assert _read_tables(markdown) == [(["Metric", "Value"], [["A | B", "10"], [r"C\D", "20"]])]


@pytest.mark.fast
def test_text_without_pipes_or_backslashes_is_unchanged():
    markdown = _markdown(_table("<th>Metric</th><th>FY2024</th>", "<tr><td>Revenue</td><td>$ 56,334</td></tr>"))

    assert markdown.strip() == "| Metric | FY2024 |\n| --- | --- |\n| Revenue | $ 56,334 |"


def _cells(row: str) -> list:
    """Split one pipe-table row on its unescaped pipes."""
    cells, current, chars = [], "", iter(row.strip()[1:-1])
    for char in chars:
        if char == "\\":
            current += char + next(chars, "")
        elif char == "|":
            cells.append(current.strip())
            current = ""
        else:
            current += char
    cells.append(current.strip())
    return cells


@pytest.mark.fast
def test_abbvie_page_footer_keeps_its_pipe_inside_the_cell():
    """A single-row footer stays a plain row (GH #1484); it must still be two cells."""
    lines = _markdown(ABBV_10K.read_text(encoding="utf-8")).splitlines()

    footer = next(line for line in lines if line.startswith("| 1 |") and "2024 Form 10-K" in line)
    assert footer == "| 1 | \\| 2024 Form 10-K |"
    assert _cells(footer) == ["1", "\\| 2024 Form 10-K"]
