"""Financial tables from filing reports (R-files) as DataFrames.

REWRITTEN 2026-09-02 (bead edgartools-yq1l). Every test in this file used to
print and assert nothing, and the two that looked like checks were guarded by
`if not df2.empty:` — so when `extract_statement_dataframe` began returning an
empty DataFrame for every input, the whole file still passed. Half of it also
drove the LEGACY `edgar.files.html.Document`, which is not the parser
`extract_statement_dataframe` uses, so it exercised a path the product does not
take.

Ground-truth values for the Apple income statement live in
`tests/issues/regression/test_yq1l_financial_table_extraction.py`. What this
file covers is the table SHAPES the extractor has to handle.
"""
from pathlib import Path

import pytest

from edgar.sgml.table_to_dataframe import FinancialTableExtractor, extract_statement_dataframe

pytestmark = pytest.mark.fast

FIXTURES = Path(__file__).parent / "fixtures" / "attachments" / "aapl" / "20250329"


def test_income_statement_extracts_typed_numeric_columns():
    """R2 is the ordinary case: a stub column and four period columns."""
    df = extract_statement_dataframe((FIXTURES / "R2.htm").read_text(encoding="utf-8"))

    assert not df.empty
    assert len(df.columns) == 4
    # Every period column is numeric. Before the fix there were no columns at all.
    assert all(str(df[col].dtype) == "float64" for col in df.columns), df.dtypes


def test_multi_level_headers_are_merged_column_wise():
    """A two-row header must produce one label per column carrying both rows.

    The `rowspan`/`colspan` combination below is the standard SEC layout: a stub
    header spanning both rows, and two period groups spanning two columns each.
    Taking only the last header row gives four indistinguishable dates; taking
    only the first gives two labels for four columns.
    """
    html = """
    <html><body><table>
    <tr>
        <th rowspan="2">Line Items</th>
        <th colspan="2">3 Months Ended</th>
        <th colspan="2">6 Months Ended</th>
    </tr>
    <tr>
        <th>Mar 31, 2025</th><th>Mar 31, 2024</th>
        <th>Mar 31, 2025</th><th>Mar 31, 2024</th>
    </tr>
    <tr><td>Revenue</td><td>$1,000</td><td>$900</td><td>$2,100</td><td>$1,800</td></tr>
    <tr><td>Cost of Sales</td><td>($600)</td><td>($500)</td><td>($1,200)</td><td>($1,000)</td></tr>
    </table></body></html>
    """
    df = extract_statement_dataframe(html)

    assert list(df.columns) == [
        "3 Months Ended Mar 31, 2025",
        "3 Months Ended Mar 31, 2024",
        "6 Months Ended Mar 31, 2025",
        "6 Months Ended Mar 31, 2024",
    ]
    assert list(df.index) == ["Revenue", "Cost of Sales"]
    assert df.loc["Revenue", "3 Months Ended Mar 31, 2025"] == 1000.0
    assert df.loc["Revenue", "6 Months Ended Mar 31, 2024"] == 1800.0
    # Parenthesised figures are negative, and the period columns did not shift.
    assert df.loc["Cost of Sales", "3 Months Ended Mar 31, 2025"] == -600.0
    assert df.loc["Cost of Sales", "6 Months Ended Mar 31, 2025"] == -1200.0


def test_period_type_is_read_from_the_header():
    html = """
    <html><body><table>
    <tr><th>Line Items</th><th>Dec. 31, 2024</th></tr>
    <tr><td>Total assets</td><td>$5,000</td></tr>
    </table></body></html>
    """
    # A bare date with no "ended" is a point in time.
    assert extract_statement_dataframe(html).attrs["period_type"] == "instant"


def test_cover_page_is_extracted_as_a_vertical_table():
    """R1 has one label column and value columns rather than periods.

    Narrow assertion on purpose: the values on this layout are identifiers and
    text, and `_parse_financial_value` coerces them to floats — "94-2404110"
    becomes 94.0. That is a real defect and it is filed separately
    (edgartools-wrkc); it is NOT asserted as correct here.
    """
    df = extract_statement_dataframe((FIXTURES / "R1.htm").read_text(encoding="utf-8"))

    assert not df.empty
    assert "Entity Registrant Name" in df.index
    assert df.loc["Entity Registrant Name"].iloc[0] == "Apple Inc."


def test_nested_tables_do_not_raise():
    """R21 nests tables inside tables; the extractor returns a frame or an empty
    one, never an exception, because it runs inside `Report.get_dataframe()`."""
    df = extract_statement_dataframe((FIXTURES / "R21.htm").read_text(encoding="utf-8"))
    assert df is not None


def test_a_page_with_no_financial_table_returns_empty():
    """R6's tables each hold a single "X". Empty is the right answer, and the
    fix must not manufacture a frame out of them."""
    assert extract_statement_dataframe((FIXTURES / "R6.htm").read_text(encoding="utf-8")).empty


def test_extractor_returns_empty_rather_than_raising_on_junk():
    assert extract_statement_dataframe("").empty
    assert extract_statement_dataframe("<html><body><p>no tables</p></body></html>").empty


def test_extract_table_to_dataframe_accepts_a_modern_table_node():
    """The direct entry point, which is what read the legacy-only attribute.

    It is annotated for `edgar.documents.table_nodes.TableNode`, and this is the
    test that says so in a way that fails if it ever reaches for a legacy one
    again.
    """
    from edgar.documents import HTMLParser, ParserConfig

    doc = HTMLParser(ParserConfig()).parse((FIXTURES / "R2.htm").read_text(encoding="utf-8"))
    df = FinancialTableExtractor.extract_table_to_dataframe(doc.tables[0])
    assert not df.empty
