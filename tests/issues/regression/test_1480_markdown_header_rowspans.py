"""Retain physical header-row geometry when Markdown omits body spacers.

Eaton's 2024 10-K (0001551182-25-000006, table 28) and 2026 Q1 10-Q
(0001551182-26-000013, tables 22/23) place a blank physical row between
rowspanning equity groups and their Shares/Dollars leaves. The fixtures are
exact table fragments from those primary documents; provenance.json records
their source offsets. The smaller examples below are synthetic boundaries.
"""

from copy import deepcopy
from pathlib import Path

import pytest
from lxml import html
from markdown_it import MarkdownIt

from edgar.documents import Document, HTMLParser, ParserConfig
from edgar.documents.table_nodes import Cell, Row, TableNode
from edgar.richtools import rich_to_text

pytestmark = pytest.mark.fast
EATON = Path(__file__).parents[2] / "fixtures" / "html" / "eaton"
EATON_HEADERS = [
    "(In millions)",
    "Ordinary shares Shares",
    "Ordinary shares Dollars",
    "Ordinary shares Dollars",
    "Capital in excess of par value",
    "Capital in excess of par value",
    "Retained earnings",
    "Retained earnings",
    "Accumulated other comprehensive loss",
    "Accumulated other comprehensive loss",
    "Shares held in trust",
    "Shares held in trust",
    "Total Eaton shareholders' equity",
    "Total Eaton shareholders' equity",
    "Noncontrolling interests",
    "Noncontrolling interests",
    "Total equity",
    "Total equity",
]


def parse(source, form=None):
    return HTMLParser(ParserConfig(form=form, enable_parallel=False, max_workers=1)).parse(source)


def first_table(document: Document) -> TableNode:
    tables = document.tables
    assert tables is not None
    table = tables[0]
    assert table is not None
    return table


def markdown_table(document):
    rendered = MarkdownIt("commonmark").enable("table").render(document.to_markdown())
    table = html.fromstring(rendered).xpath("//table")[0]
    headers = [" ".join(cell.text_content().split()) for cell in table.xpath("./thead/tr/th")]
    rows = [[" ".join(cell.text_content().split()) for cell in row.xpath("./td")] for row in table.xpath("./tbody/tr")]
    return headers, rows


@pytest.mark.parametrize("render_rich_first", [False, True])
@pytest.mark.parametrize(
    ("fixture", "form", "label", "amounts", "body_count", "raw_body_count"),
    [
        (
            "etn-20241231-table-28.html",
            "10-K",
            "Balance at January 1, 2022",
            ["398.8", "$", "4", "$", "12,449", "$", "7,594", "$", "(3,633)", "$", "(1)", "$", "16,413", "$", "38", "$", "16,451"],
            21,
            44,
        ),
        (
            "etn-20260331-table-22.html",
            "10-Q",
            "Balance at January 1, 2026",
            ["387.9", "$", "4", "$", "12,837", "$", "10,702", "$", "(4,118)", "$", "—", "$", "19,425", "$", "44", "$", "19,469"],
            7,
            40,
        ),
        (
            "etn-20260331-table-23.html",
            "10-Q",
            "Balance at January 1, 2025",
            ["392.9", "$", "4", "$", "12,731", "$", "10,096", "$", "(4,342)", "$", "(1)", "$", "18,488", "$", "43", "$", "18,531"],
            8,
            40,
        ),
    ],
)
def test_eaton_equity_shares_and_dollars_keep_their_filed_columns(fixture, form, label, amounts, body_count, raw_body_count, render_rich_first):
    document = parse((EATON / fixture).read_bytes(), form)
    table = first_table(document)
    assert len(table.headers) == 2
    assert len(table.rows) == raw_body_count
    original_headers = [tuple(row) for row in table.headers]
    original_spans = [[(cell.colspan, cell.rowspan) for cell in row] for row in original_headers]
    original_body = table.to_dict()["data"]
    if render_rich_first:
        rich_to_text(table.render(width=500), width=500)
        before = markdown_table(document)
    else:
        before = markdown_table(document)
        rich_to_text(table.render(width=500), width=500)
    headers, rows = markdown_table(document)

    assert (headers, rows) == before
    assert headers == EATON_HEADERS
    assert rows[0] == [label, *amounts]
    # These quarterly fragments contain multiline body labels, whose Markdown
    # line-break handling is separate from header placement. Count source rows.
    assert sum(any(cell.text().strip() for cell in row.cells) for row in table.rows) == body_count
    assert all(len(row) == len(EATON_HEADERS) for row in rows)
    assert table.to_dict()["data"] == original_body
    assert "_header_geometry" not in table.metadata
    assert all(current[index] is cell for current, source in zip(table.headers, original_headers, strict=True) for index, cell in enumerate(source))
    assert [[(cell.colspan, cell.rowspan) for cell in row] for row in original_headers] == original_spans


@pytest.mark.parametrize(
    ("source", "header_count"),
    [
        ('<tr><th rowspan="3">Business</th><th colspan="2" rowspan="2">Revenue</th></tr><tr><td></td></tr><tr><th>2026</th><th>2025</th></tr>', 2),
        ('<tr><th rowspan="3">Business</th><th colspan="2" rowspan="2">Revenue</th></tr><tr></tr><tr><th>2026</th><th>2025</th></tr>', 2),
        (
            '<tr><th rowspan="4">Business</th><th colspan="2" rowspan="3">Revenue</th></tr>'
            "<tr><td></td></tr><tr></tr><tr><th>2026</th><th>2025</th></tr>",
            2,
        ),
        (
            '<tr><td></td></tr><tr><th rowspan="3">Business</th><th colspan="2" rowspan="2">Revenue</th></tr>'
            "<tr><td></td></tr><tr><th>2026</th><th>2025</th></tr>",
            2,
        ),
        ('<tr><th rowspan="2">Business</th><th colspan="2">Revenue</th></tr><tr><th>2026</th><th>2025</th></tr><tr><td></td></tr>', 2),
        (
            '<thead><tr><th rowspan="3">Business</th><th colspan="2" rowspan="2">Revenue</th></tr>'
            "<tr><th></th></tr><tr><th>2026</th><th>2025</th></tr></thead>",
            3,
        ),
        ('<tr><th rowspan="0">Business</th><th colspan="2" rowspan="2">Revenue</th></tr><tr><td></td></tr><tr><th>2026</th><th>2025</th></tr>', 2),
    ],
    ids=["empty-td", "no-cells", "multiple-omitted-rows", "before-origin", "after-span-end", "kept-thead-blank", "zero-rowspan"],
)
def test_blank_physical_rows_preserve_header_spans(source, header_count):
    document = parse(f"<html><body><table>{source}<tr><td>Cloud</td><td>10</td><td>8</td></tr></table></body></html>")
    table = first_table(document)
    assert len(table.headers) == header_count
    spans = [[cell.rowspan for cell in row] for row in table.headers]
    assert markdown_table(document) == (["Business", "Revenue 2026", "Revenue 2025"], [["Cloud", "10", "8"]])
    assert [[cell.rowspan for cell in row] for row in table.headers] == spans


def test_an_empty_origin_cell_with_its_own_rowspan_reserves_a_column():
    document = parse(
        '<table><tr><th rowspan="3">Business</th><th colspan="3">Revenue</th></tr>'
        '<tr><td rowspan="2"></td><td></td><td></td></tr>'
        "<tr><th>Current</th><th>Prior</th></tr>"
        "<tr><td>Cloud</td><td>99</td><td>10</td><td>8</td></tr></table>"
    )
    assert len(first_table(document).headers) == 2
    assert markdown_table(document) == (["Business", "Revenue", "Revenue Current", "Revenue Prior"], [["Cloud", "99", "10", "8"]])


def test_intervening_body_content_keeps_occupancy_without_becoming_a_header():
    document = parse(
        '<table><tr><th rowspan="3">Business</th><th colspan="2" rowspan="2">Revenue</th></tr>'
        "<tr><td>$</td></tr><tr><th>2026</th><th>2025</th></tr>"
        "<tr><td>Cloud</td><td>10</td><td>8</td></tr></table>"
    )
    assert markdown_table(document) == (["Business", "Revenue 2026", "Revenue 2025"], [["$", "", ""], ["Cloud", "10", "8"]])


@pytest.mark.parametrize("span", [0, 5])
def test_rowspans_end_at_the_actual_html_row_group(span):
    document = parse(
        f'<table><thead><tr><th rowspan="{span}">Business</th><th colspan="2">Revenue</th></tr>'
        "<tr><th>2026</th><th>2025</th></tr></thead><tbody>"
        '<tr><td colspan="3"></td></tr><tr><th>Metric</th><th>Current</th><th>Prior</th></tr>'
        "<tr><td>Cloud</td><td>10</td><td>8</td></tr></tbody><tfoot><tr><td></td></tr></tfoot></table>"
    )
    assert first_table(document).headers[0][0].rowspan == span
    assert markdown_table(document) == (["Business Metric", "Revenue 2026 Current", "Revenue 2025 Prior"], [["Cloud", "10", "8"]])


def test_nested_and_sibling_blank_rows_do_not_change_the_outer_header_grid():
    document = parse(
        '<table><tr><th rowspan="2">Business<table><tr></tr><tr><td></td></tr></table></th>'
        '<th colspan="2">Revenue</th></tr><tr><th>2026</th><th>2025</th></tr>'
        "<tr><td>Cloud</td><td>10</td><td>8</td></tr></table><table><tr></tr><tr><td></td></tr></table>"
    )
    assert markdown_table(document) == (["Business", "Revenue 2026", "Revenue 2025"], [["Cloud", "10", "8"]])


@pytest.mark.parametrize("copy_headers", [False, True])
def test_replaced_public_headers_use_the_direct_table_fallback(copy_headers):
    document = parse(
        '<table><tr><th rowspan="3">Business</th><th colspan="2" rowspan="2">Revenue</th></tr>'
        "<tr><td></td></tr><tr><th>2026</th><th>2025</th></tr>"
        "<tr><td>Cloud</td><td>10</td><td>8</td></tr></table>"
    )
    headers = [[Cell("Category", rowspan=2), Cell("Amount", colspan=2)], [Cell("Current"), Cell("Prior")]]
    if copy_headers:
        first_table(document).headers = headers
    else:
        first_table(document).headers[:] = headers
    assert markdown_table(document) == (["Category", "Amount Current", "Amount Prior"], [["Cloud", "10", "8"]])


def test_cell_content_edits_and_deepcopy_keep_source_geometry():
    document = parse(
        '<table><tr><th rowspan="3">Business</th><th colspan="2" rowspan="2">Revenue</th></tr>'
        "<tr><td></td></tr><tr><th>2026</th><th>2025</th></tr>"
        "<tr><td>Cloud</td><td>10</td><td>8</td></tr></table>"
    )
    copied = deepcopy(document)
    first_table(copied).headers[0][1].content = "Sales"
    assert markdown_table(copied) == (["Business", "Sales 2026", "Sales 2025"], [["Cloud", "10", "8"]])
    assert first_table(document).headers[0][1].text() == "Revenue"


def test_directly_constructed_table_has_no_parser_geometry_requirement():
    table = TableNode(
        headers=[[Cell("Business", rowspan=2), Cell("Revenue", colspan=2)], [Cell("2026"), Cell("2025")]],
        rows=[Row([Cell("Cloud"), Cell("10"), Cell("8")])],
    )
    document = Document(root=table)
    assert markdown_table(document) == (["Business", "Revenue 2026", "Revenue 2025"], [["Cloud", "10", "8"]])
