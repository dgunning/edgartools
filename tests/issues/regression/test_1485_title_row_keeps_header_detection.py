"""A title row before a header must not end header detection.

Issue #1485. JPMorgan's 10-Q credit-card loan-modification table files an empty
row, then a lone spanning title (``Loan modifications``), then the period row
(``Three months ended June 30, 2026`` / ``Six months ended June 30, 2026``), then
the metric row. ``_process_table_structure`` marks data as started on the first
non-header-related row, so the title row latched ``data_rows_started`` and the
period and metric rows were never offered to ``_is_header_row``, which returns
True for both. ``table.headers`` came back ``[]`` and the filed column labels
were rendered as body rows. Offline.
"""
import pytest

from edgar.documents import HTMLParser, ParserConfig

pytestmark = pytest.mark.fast

# Row shapes copied from jpm-20260630.htm table 206: empty row, spanning title,
# period row, metric row, then two data rows.
HTML = b"""<html><body><table>
<tr><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr>
<tr><td colspan="7">Loan modifications</td></tr>
<tr><td></td><td colspan="3">Three months ended June 30, 2026</td><td></td><td colspan="2">Six months ended June 30, 2026</td></tr>
<tr><td>(in millions, except ratios)</td><td>Amortized cost basis</td><td></td><td>% of loan modifications to total retained credit card loans</td><td></td><td>Financial effect of loan modifications</td><td>Amortized cost basis</td></tr>
<tr><td></td><td>648</td><td></td><td>10.2</td><td></td><td>120</td><td>1,262</td></tr>
<tr><td></td><td>700</td><td></td><td>11.1</td><td></td><td>130</td><td>1,300</td></tr>
</table></body></html>"""


@pytest.fixture(scope="module")
def table():
    document = HTMLParser(ParserConfig(enable_parallel=False, max_workers=1)).parse(HTML)
    return document.tables[0]


def test_period_and_metric_rows_are_headers(table):
    headers = [' '.join(c.text().split()) for row in table.headers for c in row]
    assert "Three months ended June 30, 2026" in headers
    assert "Six months ended June 30, 2026" in headers
    assert "Amortized cost basis" in headers


def test_title_and_amounts_stay_body_rows(table):
    body = [' '.join(c.text().split()) for row in table.rows for c in row.cells]
    assert "Loan modifications" in body            # the spanning title is a body row
    assert "648" in body and "1,262" in body       # the filed amounts are retained


# The guard must only accept header evidence, not invent a header: a table whose
# first row is a lone spanning label and whose next row is data has no header.
HTML_NO_HEADER = b"""<html><body><table>
<tr><td colspan="5">Assets</td></tr>
<tr><td></td><td>Cash</td><td>$ 1,000</td><td>$ 900</td></tr>
</table></body></html>"""

# ...and a label does not suppress a real header that follows it.
HTML_LABEL_THEN_HEADER = b"""<html><body><table>
<tr><td colspan="3">Loan modifications</td></tr>
<tr><th>Item</th><th>FY2025</th><th>FY2024</th></tr>
<tr><td></td><td>648</td><td>1,262</td></tr>
</table></body></html>"""

# Known limitation, kept out of the guard: a single-cell, text-only row naming
# two years carries no figures and no prose, so it is still treated as a header.
# Whether the year branch should require a header-shaped row is left to review.
HTML_TEXT_ONLY_YEARS = b"""<html><body><table>
<tr><td colspan="5">Assets</td></tr>
<tr><td colspan="3">12 Months Ended Dec 31, 2025 and Dec 31, 2024</td></tr>
<tr><td></td><td>Cash</td><td>$ 1,000</td><td>$ 900</td></tr>
</table></body></html>"""


def parse_table(html):
    document = HTMLParser(ParserConfig(enable_parallel=False, max_workers=1)).parse(html)
    return document.tables[0]


def test_label_then_amounts_without_a_header_row_has_no_headers():
    table = parse_table(HTML_NO_HEADER)
    assert table.headers == []


def test_label_does_not_suppress_a_real_header_row():
    table = parse_table(HTML_LABEL_THEN_HEADER)
    headers = [' '.join(c.text().split()) for row in table.headers for c in row]
    assert "Item" in headers and "FY2025" in headers and "FY2024" in headers
    body = [' '.join(c.text().split()) for row in table.rows for c in row.cells]
    assert "648" in body and "1,262" in body


def test_text_only_year_row_is_still_treated_as_a_header():
    """Pins the known limitation named in review; not a behaviour we endorse."""
    table = parse_table(HTML_TEXT_ONLY_YEARS)
    headers = [' '.join(c.text().split()) for row in table.headers for c in row]
    assert "12 Months Ended Dec 31, 2025 and Dec 31, 2024" in headers
