"""Sparse label columns and affix columns survive table rendering (y0ri, 3cis).

Two defects in ``FastTableRenderer._identify_meaningful_columns``, both of which
lost content that was present in ``to_dataframe()`` and absent from ``text()``.
They are fixed together because they are two rules in one function and each
would otherwise churn the same pinned baselines.

edgartools-y0ri -- SPARSENESS read as spacing. The filter asked
``avg_score >= 0.5 or total_score >= 5``. A signature block's label column holds
one substantial cell in eight rows: 3 points over 8 rows is an average of 0.375
and a total of 3, so it failed both halves and was discarded. On the 6-K
0001171843-25-004208 primary document that column carried
``Date: June 30, 2025``, and the date vanished from the rendered signature
block while the legacy parser kept it. (The bead described this as the
DataFrame index being dropped; it is not -- nothing promotes a column to an
index and then forgets it. It is the score threshold.)

edgartools-3cis -- AFFIX columns dropped, then unmergeable. SEC filers put the
currency mark, the percent sign and the parenthesis closing a negative number in
cells of their own. Those cells are one character and score 0, so they were
filtered out as spacing before ``_merge_related_columns`` could ever fold them
into the figure they belong to: ``(175,207)`` rendered as ``(175,207`` and
``93.55 %`` as ``93.55``.

Fixing the filter alone is not enough, and the reason is worth keeping. A
suffix column is SPARSE BY NATURE -- only the negative rows carry a ``)`` -- so
a ratio test over rows never reaches any threshold and the paren renders as its
own column instead of merging. The test has to be structural: every non-empty
cell in the column is an affix, which no column of real data ever is.
"""
import pytest

from edgar.documents import parse_html

pytestmark = pytest.mark.fast


def _render(html: str) -> str:
    return parse_html(html).text(table_max_col_width=200)


# --- edgartools-y0ri ---------------------------------------------------------

SIGNATURE_BLOCK = """
<html><body><table>
  <tr><td></td><td></td><td>Addex Therapeutics Ltd</td></tr>
  <tr><td></td><td></td><td>(Registrant)</td></tr>
  <tr><td></td><td></td><td></td></tr>
  <tr><td></td><td></td><td></td></tr>
  <tr><td>Date: June 30, 2025</td><td></td><td>/s/ Tim Dyer</td></tr>
  <tr><td></td><td></td><td>Tim Dyer</td></tr>
  <tr><td></td><td></td><td>Chief Executive Officer</td></tr>
  <tr><td></td><td></td><td></td></tr>
</table></body></html>
"""


def test_sparse_label_column_survives():
    """One real value in eight rows is content, not spacing."""
    text = _render(SIGNATURE_BLOCK)

    assert "Date: June 30, 2025" in text
    assert "/s/ Tim Dyer" in text


def test_truly_empty_column_is_still_dropped():
    """The fix must not turn the spacing filter off."""
    html = """
    <html><body><table>
      <tr><td>Segment</td><td>   </td><td>Revenue</td></tr>
      <tr><td>Nursing</td><td>   </td><td>1,654,567</td></tr>
      <tr><td>Logistics</td><td>   </td><td>2,134,163</td></tr>
    </table></body></html>
    """
    text = _render(html)

    assert "Nursing" in text and "1,654,567" in text
    # The middle column contributes nothing, so the row collapses to two fields.
    assert "Nursing" in text


# --- edgartools-3cis ---------------------------------------------------------

def test_closing_paren_merges_into_its_figure():
    """A negative number keeps the paren that makes it negative."""
    html = """
    <html><body><table>
      <tr><td>Line</td><td>Amount</td><td></td></tr>
      <tr><td>Revenue</td><td>424,071</td><td></td></tr>
      <tr><td>Corporate</td><td>(175,207</td><td>)</td></tr>
      <tr><td>Interest</td><td>(11,643</td><td>)</td></tr>
    </table></body></html>
    """
    text = _render(html)

    assert "(175,207)" in text, "closing paren lost or left in its own column"
    assert "(11,643)" in text


def test_percent_sign_merges_into_its_figure():
    html = """
    <html><body><table>
      <tr><td>Matter</td><td>% For</td><td></td><td>% Withheld</td><td></td></tr>
      <tr><td>Auditors</td><td>93.55</td><td>%</td><td>6.45</td><td>%</td></tr>
    </table></body></html>
    """
    text = _render(html)

    assert "93.55%" in text
    assert "6.45%" in text, "the trailing percentage was dropped entirely"


def test_currency_column_merges_even_when_sparse():
    """The '$' column is structural, not statistical.

    Only the first and last rows of a statement usually carry the mark, so a
    ratio over rows dilutes below any threshold.
    """
    html = """
    <html><body><table>
      <tr><td>Line</td><td></td><td>Amount</td></tr>
      <tr><td>Total assets</td><td>$</td><td>77,507</td></tr>
      <tr><td>Cash</td><td></td><td>10,536</td></tr>
      <tr><td>Receivables</td><td></td><td>4,221</td></tr>
      <tr><td>Total</td><td>$</td><td>92,264</td></tr>
    </table></body></html>
    """
    text = _render(html)

    assert "$77,507" in text
    assert "$92,264" in text
    assert "10,536" in text


def test_a_real_data_column_is_never_treated_as_an_affix():
    """Affix merging keys on the column being ENTIRELY affixes."""
    html = """
    <html><body><table>
      <tr><td>Region</td><td>Share</td><td>Rank</td></tr>
      <tr><td>Americas</td><td>41.2</td><td>1</td></tr>
      <tr><td>EMEA</td><td>33.9</td><td>2</td></tr>
    </table></body></html>
    """
    text = _render(html)

    for token in ("Americas", "41.2", "EMEA", "33.9", "Rank"):
        assert token in text
    assert "41.21" not in text, "adjacent data columns were merged into each other"
