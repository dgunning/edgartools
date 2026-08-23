"""A wide table keeps every meaningful column (fast_table 8-column cap).

``FastTableRenderer._identify_meaningful_columns`` scored each column, sorted the
scores DESCENDING, then stopped after eight. Because of that ordering the cap did
not trim the right-hand edge of a wide table -- it discarded whichever columns
scored lowest, wherever they sat, and on real financial tables those are ordinary
data columns.

Two shapes found in the edgartools-3dp Group A comparison over 6-K exhibits:

* a 21-column segment table (0001213900-25-059683 EX-99.2) rendered 8 columns, so
  the "Logistics and other solution services", "Corporate and unallocated" and
  "Total" headers were absent from ``text()`` while present in ``to_dataframe()``;
* a 10-column voting table (0001641172-25-017205 EX-99.1) lost the "% Withheld"
  VALUE -- 6.45 was in the model and nowhere in the text.

Per-column width is bounded separately by ``style.max_col_width``, so dropping
columns bought nothing that the width limit does not already provide.
"""
import pytest

from edgar.documents import parse_html

pytestmark = pytest.mark.fast


def _wide_table_html(n_cols: int) -> str:
    """A table with n_cols distinctly-labelled data columns plus a row label."""
    headers = "".join(f"<td>Col{i}</td>" for i in range(n_cols))
    cells = "".join(f"<td>{1000 + i}</td>" for i in range(n_cols))
    return f"""
    <html><body><table>
      <tr><td>Segment</td>{headers}</tr>
      <tr><td>Revenue</td>{cells}</tr>
    </table></body></html>
    """


def test_wide_table_keeps_every_column():
    """A 12-column table renders all 12 headers, not the 8 best-scoring ones."""
    text = parse_html(_wide_table_html(12)).text(table_max_col_width=200)

    for i in range(12):
        assert f"Col{i}" in text, f"header Col{i} was dropped from text()"
        assert str(1000 + i) in text, f"value {1000 + i} was dropped from text()"


def test_narrow_table_is_unaffected():
    """The threshold still removes spacing-only columns."""
    html = """
    <html><body><table>
      <tr><td>Segment</td><td> </td><td>Revenue</td></tr>
      <tr><td>Nursing</td><td> </td><td>1,654,567</td></tr>
    </table></body></html>
    """
    text = parse_html(html).text(table_max_col_width=200)

    assert "Segment" in text
    assert "1,654,567" in text


def test_column_count_beyond_the_old_cap_survives():
    """The old cap kept exactly 8; anything past that is the regression under test."""
    text = parse_html(_wide_table_html(15)).text(table_max_col_width=200)

    present = sum(1 for i in range(15) if f"Col{i}" in text)
    assert present == 15, f"only {present}/15 columns survived rendering"
