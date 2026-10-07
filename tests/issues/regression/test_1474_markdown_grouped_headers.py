"""Document Markdown must retain grouped duration and date headers.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1474

Apple's 10-Q, accession 0000320193-25-000057, puts two dates beneath each
3 Months Ended and 6 Months Ended group. Markdown dropped the group/date
association and labelled $90,753 million of comparative net sales with the
current-year date. R2/R3 below assert the filed labels and values; R6 guards
the existing equity-component headers. The smaller HTML examples are
synthetic boundaries, including the original Business/Revenue reproduction.
"""

from pathlib import Path

import pytest
from lxml import html as lxml_html
from markdown_it import MarkdownIt

from edgar.documents import HTMLParser, ParserConfig
from edgar.documents.table_nodes import Cell, Row
from edgar.documents.utils.table_matrix import TableMatrix
from edgar.richtools import rich_to_text

pytestmark = pytest.mark.fast

APPLE_REPORTS = Path(__file__).parents[2] / "fixtures" / "attachments" / "aapl" / "20250329"
PERIODS = [
    "3 Months Ended Mar. 29, 2025",
    "3 Months Ended Mar. 30, 2024",
    "6 Months Ended Mar. 29, 2025",
    "6 Months Ended Mar. 30, 2024",
]


def parse_document(source):
    return HTMLParser(ParserConfig(form="10-Q")).parse(source)


def first_markdown_table(document):
    """Read the emitted table with a Markdown table parser, including escapes."""
    rendered = MarkdownIt("commonmark").enable("table").render(document.to_markdown())
    table = lxml_html.fromstring(rendered).xpath("//table")[0]
    headers = [" ".join(cell.text_content().split()) for cell in table.xpath("./thead/tr/th")]
    rows = [[" ".join(cell.text_content().split()) for cell in row.xpath("./td")] for row in table.xpath("./tbody/tr")]
    return headers, rows


@pytest.mark.parametrize(
    ("report", "label", "amounts", "row_count"),
    [
        ("R2", "Net sales", ["$ 95,359", "$ 90,753", "$ 219,659", "$ 210,328"], 24),
        ("R3", "Net income", ["$ 24,780", "$ 23,636", "$ 61,110", "$ 57,552"], 17),
    ],
)
def test_apple_duration_date_headers_match_the_filed_amounts(report, label, amounts, row_count):
    document = parse_document((APPLE_REPORTS / f"{report}.htm").read_text(encoding="utf-8"))
    headers, rows = first_markdown_table(document)

    assert headers[1:] == PERIODS
    # R2 repeats Net sales for total/products/services: the first is the total.
    assert next(row for row in rows if row[0] == label) == [label, *amounts]
    assert len(rows) == row_count
    assert len(headers) == 5
    assert all(len(row) == 5 for row in rows)


@pytest.mark.parametrize("report", ["R2", "R3"])
def test_rich_header_padding_does_not_add_a_markdown_column(report):
    document = parse_document((APPLE_REPORTS / f"{report}.htm").read_text(encoding="utf-8"))
    before = first_markdown_table(document)
    rich_to_text(document.tables[0].render(width=500), width=500)
    after = first_markdown_table(document)

    assert after == before
    assert after[0][1:] == PERIODS
    assert len(after[0]) == 5


@pytest.mark.parametrize("render_rich_first", [False, True])
def test_apple_equity_component_headers_and_values_are_preserved(render_rich_first):
    document = parse_document((APPLE_REPORTS / "R6.htm").read_text(encoding="utf-8"))
    if render_rich_first:
        rich_to_text(document.tables[0].render(width=500), width=500)
    headers, rows = first_markdown_table(document)

    assert headers[0].startswith("CONDENSED CONSOLIDATED STATEMENTS OF SHAREHOLDERS' EQUITY")
    assert headers[1:] == [
        "Total",
        "Common stock and additional paid-in capital",
        "Retained earnings/(Accumulated deficit)",
        "Accumulated other comprehensive income/(loss)",
    ]
    assert rows[0] == ["Beginning balances at Sep. 30, 2023", "$ 62,146", "$ 73,812", "$ (214)", "$ (11,452)"]
    assert len(rows) == 47
    assert all(len(row) == 5 for row in rows)


@pytest.mark.parametrize(
    ("source", "headers", "rows"),
    [
        pytest.param(
            '<tr><th rowspan="2">Business</th><th colspan="2">Revenue</th></tr>'
            "<tr><th>2026</th><th>2025</th></tr>"
            "<tr><td>Cloud</td><td>10</td><td>8</td></tr>"
            "<tr><td>Other</td><td>3</td><td>4</td></tr>",
            ["Business", "Revenue 2026", "Revenue 2025"],
            [["Cloud", "10", "8"], ["Other", "3", "4"]],
            id="original-business-revenue",
        ),
        pytest.param(
            "<tr><th>Business</th><th>Revenue 2026</th><th>Revenue 2025</th></tr><tr><td>Cloud</td><td>10</td><td>8</td></tr>",
            ["Business", "Revenue 2026", "Revenue 2025"],
            [["Cloud", "10", "8"]],
            id="flat-control",
        ),
        pytest.param(
            '<tr><th rowspan="3">Business</th><th colspan="4">Equity</th></tr>'
            '<tr><th colspan="2">Common stock</th><th colspan="2">Preferred stock</th></tr>'
            "<tr><th>Shares</th><th>Amount</th><th>Shares</th><th>Amount</th></tr>"
            "<tr><td>Company</td><td>100</td><td>200</td><td>300</td><td>400</td></tr>",
            [
                "Business",
                "Equity Common stock Shares",
                "Equity Common stock Amount",
                "Equity Preferred stock Shares",
                "Equity Preferred stock Amount",
            ],
            [["Company", "100", "200", "300", "400"]],
            id="three-level-equity-synthetic",
        ),
        pytest.param(
            '<tr><th rowspan="2"></th><th colspan="2">Revenue</th></tr>'
            "<tr><th>2026</th><th>2025</th></tr>"
            "<tr><td>Cloud</td><td>10</td><td>8</td></tr>",
            ["", "Revenue 2026", "Revenue 2025"],
            [["Cloud", "10", "8"]],
            id="blank-stub",
        ),
        pytest.param(
            '<tr><th rowspan="2">Business</th><th colspan="2">Year Ended</th></tr>'
            "<tr><th>2026</th><th>2025</th></tr>"
            "<tr><td>Cloud</td><td>10</td><td>8</td></tr>",
            ["Business", "Year Ended 2026", "Year Ended 2025"],
            [["Cloud", "10", "8"]],
            id="numeric-year-keeps-duration",
        ),
        pytest.param(
            '<tr><th rowspan="3">Business</th><th colspan="2">Revenue</th><th rowspan="3">Profit</th></tr>'
            '<tr><th colspan="2">Revenue</th></tr>'
            "<tr><th>2026</th><th>2025</th></tr>"
            "<tr><td>Cloud</td><td>10</td><td>8</td><td>2</td></tr>",
            ["Business", "Revenue Revenue 2026", "Revenue Revenue 2025", "Profit"],
            [["Cloud", "10", "8", "2"]],
            id="distinct-equal-labels-and-vertical-span",
        ),
        pytest.param(
            '<tr><th rowspan="2">Business</th><th colspan="4">Revenue</th><th rowspan="2">Other</th></tr>'
            '<tr><th colspan="2">2026</th><th colspan="2">2025</th></tr>'
            '<tr><td>Cloud</td><td colspan="2">10</td><td colspan="2">8</td><td>2</td></tr>',
            ["Business", "Revenue 2026", "Revenue 2025", "Other"],
            [["Cloud", "10", "8", "2"]],
            id="spans-do-not-retain-spacing-columns",
        ),
        pytest.param(
            '<tr><th rowspan="2">Business</th><th colspan="2">Revenue</th><th></th></tr>'
            "<tr><th>2026</th><th>2025</th><th>Margin</th></tr>"
            "<tr><td>Cloud</td><td>10</td><td>8</td><td>2</td></tr>",
            ["Business", "Revenue 2026", "Revenue 2025", "Margin"],
            [["Cloud", "10", "8", "2"]],
            id="blank-outside-group-does-not-inherit-label",
        ),
        pytest.param(
            '<tr><th rowspan="2">Business</th><th colspan="2">Revenue | margin</th></tr>'
            "<tr><th>2026\\_forecast</th><th>2025</th></tr>"
            "<tr><td>Cloud</td><td>10</td><td>8</td></tr>",
            ["Business", "Revenue | margin 2026\\_forecast", "Revenue | margin 2025"],
            [["Cloud", "10", "8"]],
            id="header-pipes-and-backslashes",
        ),
        pytest.param(
            '<tr><th colspan="2">Revenue</th></tr><tr><th>2026</th><th>2025</th></tr><tr><td>10</td><td>8</td></tr>',
            ["Revenue 2026", "Revenue 2025"],
            [["10", "8"]],
            id="no-row-label-column",
        ),
        pytest.param(
            '<tr><th colspan="2">Type</th></tr><tr><th>Region</th><th>Product</th></tr><tr><td>North</td><td>Cloud</td></tr>',
            ["Type Region", "Type Product"],
            [["North", "Cloud"]],
            id="first-column-hierarchy-is-preserved",
        ),
        pytest.param(
            '<tr><th rowspan="3">Business</th><th colspan="4">Threshold</th></tr>'
            '<tr><th colspan="2">Count</th><th colspan="2">Other</th></tr>'
            '<tr><th colspan="2">1,000</th><th colspan="2">2,000</th></tr>'
            "<tr><td>Cloud</td><td>10</td><td>11</td><td>8</td><td>9</td></tr>",
            ["Business", "Threshold Count 1,000", "Threshold Count 1,000", "Threshold Other 2,000", "Threshold Other 2,000"],
            [["Cloud", "10", "11", "8", "9"]],
            id="comma-numeric-third-level-header",
        ),
        pytest.param(
            '<tr><th>Entity</th><th rowspan="2">Revenue</th></tr><tr><th>Region</th></tr><tr><td>North</td><td>10</td></tr>',
            ["Entity Region", "Revenue"],
            [["North", "10"]],
            id="stub-leaf-beside-vertical-header",
        ),
        pytest.param(
            "<tr><th>Entity</th><th>Revenue</th></tr><tr><th>Region</th><th></th></tr><tr><td>North</td><td>10</td></tr>",
            ["Entity Region", "Revenue"],
            [["North", "10"]],
            id="stub-leaf-beside-explicit-blank",
        ),
    ],
)
def test_synthetic_header_span_boundaries(source, headers, rows):
    document = parse_document(f"<html><body><table>{source}</table></body></html>")
    assert first_markdown_table(document) == (headers, rows)


def test_headerless_body_rendering_is_unchanged():
    document = parse_document(
        "<html><body><table><tr><td>Cloud</td><td>10</td><td>8</td></tr><tr><td>Other</td><td>3</td><td>4</td></tr></table></body></html>"
    )
    assert document.tables[0].headers == []
    assert document.to_markdown() == "| Cloud | 10 | 8 |\n| Other | 3 | 4 |"


def test_empty_table_does_not_create_markdown_columns():
    document = parse_document("<html><body><table></table></body></html>")
    assert document.to_markdown() == ""


@pytest.mark.parametrize("header_count", [0, 1, 2, 3, 4])
def test_existing_numeric_data_span_placement_is_preserved(header_count):
    headers = [[Cell("Business", is_header=True), Cell("Amount", colspan=2, is_header=True)] for _ in range(header_count)]
    rows = [Row(cells=[Cell(f"row {index}"), Cell("1,000", colspan=2)]) for index in range(3)]
    matrix = TableMatrix().build_from_rows(headers, rows)

    for index in range(3):
        row_index = header_count + index
        number_column = 2 if row_index > 1 else 1
        expanded = matrix.get_expanded_row(row_index)
        assert expanded[number_column].text() == "1,000"
        assert expanded[3 - number_column] is None


@pytest.mark.parametrize(
    ("header_html", "headers", "data_html", "row"),
    [
        (
            '<tr><th rowspan="0">Entity</th><th>Revenue</th></tr>',
            ["Entity", "Revenue"],
            "<tr><td>North</td><td>10</td></tr>",
            ["North", "10"],
        ),
        (
            '<tr><th rowspan="0">Entity</th><th colspan="2">Revenue</th></tr><tr><th>Current</th><th>Comparative</th></tr>',
            ["Entity", "Revenue Current", "Revenue Comparative"],
            "<tr><td>North</td><td>10</td><td>8</td></tr>",
            ["North", "10", "8"],
        ),
    ],
    ids=["flat-zero-rowspan", "grouped-zero-rowspan"],
)
def test_zero_rowspan_headers_preserve_labels_alignment_and_original_cells(header_html, headers, data_html, row):
    document = parse_document(f"<html><body><table><thead>{header_html}</thead><tbody>{data_html}</tbody></table></body></html>")
    table = document.tables[0]
    original = table.headers[0][0]
    cells = [cell for header in table.headers for cell in header] + [cell for data in table.rows for cell in data.cells]
    before = [(id(cell), cell.text(), cell.rowspan, cell.colspan) for cell in cells]

    assert original.rowspan == 0
    assert first_markdown_table(document) == (headers, [row])
    assert first_markdown_table(document) == (headers, [row])
    assert table.headers[0][0] is original
    after_cells = [cell for header in table.headers for cell in header] + [cell for data in table.rows for cell in data.cells]
    assert [(id(cell), cell.text(), cell.rowspan, cell.colspan) for cell in after_cells] == before


@pytest.mark.parametrize(
    ("header_html", "data_html", "headers", "rows"),
    [
        (
            "<tr><th>Metric</th><th>Amount</th></tr>",
            "<tr><td>Cloud</td><td>10</td><td>8</td></tr>",
            ["Metric", "Amount", ""],
            [["Cloud", "10", "8"]],
        ),
        (
            "<tr><th>Metric</th><th>Current</th><th>Comparative</th></tr>",
            "<tr><td>Cloud</td><td>10</td></tr>",
            ["Metric", "Current", "Comparative"],
            [["Cloud", "10", ""]],
        ),
    ],
    ids=["body-wider-than-headers", "body-narrower-than-headers"],
)
def test_unequal_header_body_widths_preserve_amounts_and_padding(header_html, data_html, headers, rows):
    document = parse_document(f"<html><body><table><thead>{header_html}</thead><tbody>{data_html}</tbody></table></body></html>")
    assert first_markdown_table(document) == (headers, rows)
