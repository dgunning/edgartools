"""SEC XBRL viewer fact rows stay in the table body.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1477

The SEC viewer (R1.htm, R2.htm, ...) renders header rows with ``th`` cells and
every fact row with a ``td class="pl"`` label cell. Apple's cover-page facts
"Document Type | 10-Q" and "Document Period End Date | Mar. 29, 2025" look like
period headers to the generic heuristics, so they were moved into
``table.headers`` and vanished from the body and from the Markdown.

Ground truth: Apple Inc. 10-Q for the quarter ended March 29, 2025, accession
0000320193-25-000057, cover-page report R1.htm (tracked fixture
tests/fixtures/attachments/aapl/20250329/R1.htm).
"""
from pathlib import Path

from edgar.documents import HTMLParser, ParserConfig

FIXTURE = Path(__file__).parents[2] / "fixtures" / "attachments" / "aapl" / "20250329" / "R1.htm"


def _cover_document():
    return HTMLParser(ParserConfig(form="10-Q")).parse(FIXTURE.read_text(encoding="utf-8"))


def test_apple_cover_facts_are_body_rows():
    table = _cover_document().tables[0]

    headers = [[cell.text() for cell in row] for row in table.headers]
    # The label-only abstract row is left to the generic heuristics, as before;
    # the three fact rows that carry a value are no longer headers.
    assert headers == [
        ["Cover Page - shares\n\n\nshares in Thousands", "6 Months Ended", ""],
        ["Mar. 29, 2025", "Apr. 18, 2025"],
        ["Entity Information [Line Items]", "", ""],
    ]

    body = {row.cells[0].text(): row.cells[1].text() for row in table.rows}
    assert body["Document Type"] == "10-Q"
    assert body["Document Quarterly Report"] == "true"
    assert body["Document Period End Date"] == "Mar. 29, 2025"
    assert body["Entity Registrant Name"] == "Apple Inc."


def test_apple_cover_facts_render_in_markdown_body():
    markdown = _cover_document().to_markdown()
    assert "| Document Type | 10-Q |" in markdown
    assert "| Document Period End Date | Mar. 29, 2025 |" in markdown


def test_ordinary_td_rows_still_reach_header_detection():
    # Without the viewer's "pl" label class, a period row in td cells is still a header.
    html = """
    <table>
      <tr><td></td><td>Three Months Ended</td><td>Six Months Ended</td></tr>
      <tr><td>Revenue</td><td>1,000</td><td>2,000</td></tr>
    </table>
    """
    table = HTMLParser(ParserConfig()).parse(html).tables[0]
    assert [[c.text() for c in row] for row in table.headers] == [["", "Three Months Ended", "Six Months Ended"]]
    assert [c.text() for c in table.rows[0].cells] == ["Revenue", "1,000", "2,000"]
