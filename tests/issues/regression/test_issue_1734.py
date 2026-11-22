"""
Document.to_dataframe() keeps column names unique when a generated duplicate
suffix collides with a literal header.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1734

``_flatten_table_frame`` renamed the second ``Revenue`` header to ``Revenue.1``
without reserving the literal ``Revenue.1`` header that followed, so two columns
shared a name and concatenating a second, differently shaped table raised
``InvalidIndexError``. Suffixes now skip every name already present, giving
``Revenue, Revenue.2, Revenue.1``.

The colliding tables are SYNTHETIC (the issue claims no filed occurrence).
The real-filing check below pins that the fix changes nothing where suffixes
never collide: the checked-in Morgan Stanley 10-K fixture, whose tables carry
duplicate headers and a row-label column that repeats a header.
"""
from pathlib import Path

import pytest

from edgar.documents import parse_html
from edgar.documents.document import _flatten_table_frame

FIRST = """<table><tr><th>Item</th><th>Revenue</th><th>Revenue</th><th>Revenue.1</th></tr>
<tr><td>alpha</td><td>10</td><td>20</td><td>30</td></tr></table>"""
SECOND = """<table><tr><th>Item</th><th>2023</th></tr>
<tr><td>beta</td><td>40</td></tr></table>"""


def _doc(*tables):
    return parse_html("<html><body>" + "".join(tables) + "</body></html>")


@pytest.mark.fast
def test_generated_suffix_skips_a_literal_header():
    df = _doc(FIRST).to_dataframe()
    assert list(df.columns[:4]) == ['Item', 'Revenue', 'Revenue.2', 'Revenue.1']
    assert df.iloc[0, 1:4].astype(float).tolist() == [10.0, 20.0, 30.0]
    assert df.columns.is_unique


@pytest.mark.fast
@pytest.mark.parametrize("tables", [(FIRST, SECOND), (SECOND, FIRST)], ids=["first-second", "second-first"])
def test_two_tables_concatenate(tables):
    df = _doc(*tables).to_dataframe()
    assert df.columns.is_unique
    assert len(df) == 2
    alpha = df[df['Item'] == 'alpha'].iloc[0]
    assert [float(alpha[c]) for c in ('Revenue', 'Revenue.2', 'Revenue.1')] == [10.0, 20.0, 30.0]
    assert float(df[df['Item'] == 'beta'].iloc[0]['2023']) == 40.0


@pytest.mark.fast
def test_literal_header_first():
    html = """<table><tr><th>Item</th><th>Revenue</th><th>Revenue.1</th><th>Revenue</th></tr>
<tr><td>alpha</td><td>10</td><td>20</td><td>30</td></tr></table>"""
    df = _doc(html, SECOND).to_dataframe()
    assert list(df.columns[:4]) == ['Item', 'Revenue', 'Revenue.1', 'Revenue.2']
    assert df.columns.is_unique


@pytest.mark.fast
def test_header_named_like_metadata_column_is_kept():
    html = """<table><tr><th>Item</th><th>_table_index</th></tr>
<tr><td>alpha</td><td>7</td></tr></table>"""
    df = _doc(html).to_dataframe()
    assert float(df.iloc[0]['_table_index.1']) == 7.0
    assert df.iloc[0]['_table_index'] == 0


# Morgan Stanley FY2024 10-K, accession 0000895421-25-000304, filed 2025-02-21.
MS_10K = Path(__file__).parents[2] / "fixtures" / "html" / "ms" / "10k" / "ms-10-k-2025-02-21.html"


@pytest.mark.fast
def test_real_filing_names_unchanged_where_nothing_collides():
    doc = parse_html(MS_10K.read_text(encoding="utf-8"))
    # Table 57, the Executive Summary: each year header spans a value cell and a
    # spacer cell, so the duplicates are suffixed exactly as before the fix.
    summary = _flatten_table_frame(doc.tables[57].to_dataframe())
    assert list(summary.columns) == ['$ in millions, except per share data',
                                     '2024', '2024.1', '2023', '2023.1', '2022', '2022.1']
    net_revenues = summary[summary.iloc[:, 0] == 'Net revenues'].iloc[0]
    assert (net_revenues['2024'], net_revenues['2023'], net_revenues['2022']) == ('$61,761', '$54,143', '$53,668')

    df = doc.to_dataframe()
    assert df.columns.is_unique
    assert df.shape == (3629, 741)
