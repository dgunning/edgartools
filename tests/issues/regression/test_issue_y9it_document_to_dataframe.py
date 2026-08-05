"""Document.to_dataframe() has to survive a real filing's tables.

It raised on every actual annual/quarterly report tried — 10 of 11 filings in
the 6.0 perf corpus — from inside pandas and numpy, with three different
messages depending on which pair of frames pandas happened to align first::

    ValueError: cannot join with no overlapping index names
    TypeError:  Cannot cast array data from dtype('float64') to dtype('int64')
                according to the rule 'safe'
    ValueError: Index data must be 1-dimensional

One cause underneath. A 10-K's tables do not share a schema: Meta's FY2024 10-K
has 71 tables whose column indexes are 1, 2, 3, 4, 10 and 17 levels deep, and
pandas cannot align a flat Index with a MultiIndex, or two MultiIndexes of
different depths. The only corpus entry that worked was an ABS-15G — a single
flat 25MB table, the degenerate case.

Three separate defects were behind the three messages, and each is pinned below:

1. Column indexes of mixed depth reached ``pd.concat`` unflattened.
2. A table whose first header text repeats had its row index built from *every*
   matching column by ``set_index(df.columns[0])`` — a label lookup — producing
   None-padded tuples like ``('Total', None, None)``, and raising outright when
   the match came back 2-D (Tesla's FY2023 10-K).
3. Restoring the row-label column collided with an identically-named data
   column, which is ordinary in filings: Citigroup's and Morgan Stanley's 10-Ks
   both caption a table with the same text they use as a column header.

The perf corpus is gitignored, so the end-to-end reproduction is not available
here; these fixtures pin the contract and the three causes instead. After the
fix all 11 corpus filings convert, and the 300-odd pandas PerformanceWarnings a
single document used to emit are gone (bead edgartools-y9it).
"""
import pandas as pd
import pytest

from edgar.documents import HTMLParser
from edgar.documents.config import ParserConfig
from edgar.documents.document import _flatten_column_name, _flatten_table_frame

# Tables of deliberately different header depth, the shape that broke concat.
MIXED_DEPTH_HTML = """<html><body>
<table>
  <tr><th>Item</th><th>2024</th></tr>
  <tr><td>Revenue</td><td>100</td></tr>
  <tr><td>Cost</td><td>40</td></tr>
</table>
<table>
  <tr><th>Segment</th><th>North America</th><th>North America</th><th>Europe</th></tr>
  <tr><th></th><th>Fiscal 2024</th><th>Fiscal 2023</th><th>Fiscal 2024</th></tr>
  <tr><th></th><th>(unaudited)</th><th>(unaudited)</th><th>(audited)</th></tr>
  <tr><td>Retail</td><td>10</td><td>9</td><td>4</td></tr>
</table>
<table>
  <tr><th>($ in millions)</th><th>($ in millions)</th><th>2024</th></tr>
  <tr><td>Total</td><td></td><td>5</td></tr>
</table>
</body></html>"""


def parse(html):
    return HTMLParser(ParserConfig(form='10-K')).parse(html)


class TestFlattenColumnName:
    """Header tuples become one readable string."""

    def test_blank_levels_are_dropped(self):
        assert _flatten_column_name(('Revenue', '')) == 'Revenue'
        assert _flatten_column_name(('Revenue', None)) == 'Revenue'

    def test_repeated_levels_collapse(self):
        """A header spanning two rows repeats; 'Revenue Revenue' helps nobody."""
        assert _flatten_column_name(('Revenue', 'Revenue')) == 'Revenue'

    def test_distinct_levels_are_joined(self):
        assert _flatten_column_name(('Revenue', '2024')) == 'Revenue 2024'

    def test_scalars_and_non_strings_survive(self):
        assert _flatten_column_name('Revenue') == 'Revenue'
        assert _flatten_column_name(0) == '0'

    def test_whitespace_is_normalised(self):
        assert _flatten_column_name(('($ in millions)\nYear Ended',)) == '($ in millions) Year Ended'


class TestFlattenTableFrame:
    """The three causes, each at the level it occurs."""

    def test_multiindex_columns_become_flat_strings(self):
        df = pd.DataFrame([[1, 2]], columns=pd.MultiIndex.from_tuples(
            [('North America', 'Fiscal 2024'), ('North America', 'Fiscal 2023')]))
        out = _flatten_table_frame(df)
        assert out.columns.nlevels == 1
        assert list(out.columns) == ['North America Fiscal 2024', 'North America Fiscal 2023']

    def test_duplicate_names_are_disambiguated(self):
        df = pd.DataFrame([[1, 2, 3]], columns=['Amount', 'Amount', 'Amount'])
        out = _flatten_table_frame(df)
        assert list(out.columns) == ['Amount', 'Amount.1', 'Amount.2']

    def test_row_labels_come_back_as_a_column(self):
        """ignore_index=True at the concat would otherwise discard them."""
        df = pd.DataFrame({'2024': [100]}, index=pd.Index(['Revenue'], name='Item'))
        out = _flatten_table_frame(df)
        assert list(out.columns) == ['Item', '2024']
        assert out['Item'].tolist() == ['Revenue']

    def test_label_column_colliding_with_a_data_column_is_kept(self):
        """Cause 3: Citigroup and Morgan Stanley both do exactly this."""
        df = pd.DataFrame({'In millions': [5]},
                          index=pd.Index(['Total'], name='In millions'))
        out = _flatten_table_frame(df)
        assert len(out.columns) == 2
        assert out.iloc[0].tolist() == ['Total', 5]

    def test_multi_level_row_index_is_flattened_not_dropped(self):
        """Cause 2's aftermath: a tuple index cannot be stored as one column."""
        idx = pd.MultiIndex.from_tuples([('Retail', 'US')], names=['Segment', 'Region'])
        out = _flatten_table_frame(pd.DataFrame({'2024': [10]}, index=idx))
        assert out.columns.nlevels == 1
        assert out.iloc[0, 0] == 'Retail US'

    def test_an_already_flat_frame_is_unchanged(self):
        df = pd.DataFrame({'a': [1], 'b': [2]})
        out = _flatten_table_frame(df)
        assert list(out.columns) == ['a', 'b']
        assert out['a'].tolist() == [1]


class TestTableIndexIsScalar:
    """Cause 2, end to end.

    `set_index(df.columns[0])` looked the first column up *by label*. When a
    filing repeats that header across spacer columns — which is ordinary — the
    lookup matched all of them, so the index came back as None-padded tuples and,
    when the match was 2-D, raised. This assertion fails on the unfixed code,
    which returns [('Total', '')].
    """

    def test_repeated_first_header_gives_a_scalar_index(self):
        doc = parse(MIXED_DEPTH_HTML)
        labels = list(doc.tables[2].to_dataframe().index)
        assert labels == ['Total']
        assert not any(isinstance(v, tuple) for v in labels)


class TestSpacerColumns:
    """The empty columns a spanning row-label header leaves behind.

    A filing lays its label column across two or three physical columns sharing
    one header, and only the first holds the label. Once that one becomes the
    index the rest are empty columns named after the index — noise, and 367 of
    the 444 affected tables in the benchmark corpus have nothing else in them.

    They are dropped only when empty. A same-headed column holding a percentage
    or a rate is data, and 77 corpus tables have one.
    """

    def test_empty_spacer_columns_are_dropped(self):
        doc = parse(MIXED_DEPTH_HTML)
        df = doc.tables[2].to_dataframe()
        assert list(df.index) == ['Total']
        # '($ in millions)' spanned two columns; the second is empty and goes.
        assert df.index.name not in list(df.columns)
        assert list(df.columns) == ['2024']

    def test_a_same_headed_column_with_content_is_kept(self):
        """Dropping this one would lose a filed value."""
        html = """<html><body><table>
          <tr><th>Rate</th><th>Rate</th><th>2024</th></tr>
          <tr><td>Effective tax rate</td><td>32.8</td><td>5</td></tr>
        </table></body></html>"""
        df = parse(html).tables[0].to_dataframe()
        values = {str(v).strip() for v in df.to_numpy().ravel()}
        assert '32.8' in values, "a same-headed column holding data must survive"


class TestDocumentToDataFrame:
    """The contract that makes concatenation safe in the first place."""

    def test_tables_of_mixed_header_depth_concatenate(self):
        df = parse(MIXED_DEPTH_HTML).to_dataframe()
        assert len(df) == 4  # 2 + 1 + 1 data rows

    def test_columns_are_always_flat_strings(self):
        """The invariant. A MultiIndex here is what pandas cannot align."""
        df = parse(MIXED_DEPTH_HTML).to_dataframe()
        assert df.columns.nlevels == 1
        assert all(isinstance(c, str) for c in df.columns)

    def test_provenance_identifies_the_source_table(self):
        df = parse(MIXED_DEPTH_HTML).to_dataframe()
        for col in ('_table_index', '_table_type', '_table_caption'):
            assert col in df.columns
        assert df['_table_index'].tolist() == [0, 0, 1, 2]

    def test_row_labels_are_not_lost(self):
        df = parse(MIXED_DEPTH_HTML).to_dataframe()
        values = {str(v) for v in df.to_numpy().ravel()}
        for label in ('Revenue', 'Cost', 'Retail', 'Total'):
            assert label in values, f"row label {label!r} was dropped"

    def test_no_pandas_performance_warnings(self):
        """One document used to emit hundreds of these, from the same label lookup."""
        import warnings

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            parse(MIXED_DEPTH_HTML).to_dataframe()
        assert not [w for w in caught if 'lexsort' in str(w.message)]

    def test_a_document_with_no_tables_gives_an_empty_frame(self):
        """The silence check: empty input, empty frame, no exception."""
        df = parse('<html><body><p>No tables here.</p></body></html>').to_dataframe()
        assert isinstance(df, pd.DataFrame)
        assert df.empty
