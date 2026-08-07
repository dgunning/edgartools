"""edgartools-fhk1 — a two-column TOC read the left column's page number as the
right column's item number.

Ambac's FY2022 10-K (`0000874501-23-000040`) lays its table of contents out in two
side-by-side columns, and one HTML row carries both columns' cells::

    ['', 'Available Information', '10', '', '', 'Non-GAAP Financial Measures', '54']

``_extract_preceding_item_label`` scans *every* preceding cell in the row, so the
right column's title reached back past the gap and took "10" — the page number of
the left column's entry — for its item label. That produced a `part_ii_item_10`
section (a 10-K's Part II has no Item 10) anchored at the "NON-GAAP FINANCIAL
MEASURES" heading *inside* MD&A, which truncated Item 7 there: 158,411 -> 149,459
chars, with the remainder filed under a key no caller will ask for.

The scan now stops at the column boundary, but only on a TOC confirmed
two-column: a conventional single-column row is ['Item', '1', 'Business', '5'],
where the label cell sits in the other half by the same midpoint test and the
scan must cross it to find the label at all.
"""

import pytest

from edgar.documents.utils.toc_analyzer import TOCAnalyzer


def _item_row(left_item, left_title, right_item, right_title):
    """A two-column item row: [label][title][page] twice over."""
    return f"""
    <tr>
      <td><a href="#{left_item}">{left_item.replace('item', 'Item ')}</a></td>
      <td><a href="#{left_item}">{left_title}</a></td>
      <td><a href="#{left_item}">10</a></td>
      <td><a href="#{right_item}">{right_item.replace('item', 'Item ')}</a></td>
      <td><a href="#{right_item}">{right_title}</a></td>
      <td><a href="#{right_item}">99</a></td>
    </tr>
    """


# Ambac's shape: a row listing MD&A *subsections*, no item labels anywhere in it,
# a spacer between the columns, and the left column's page number ("10") as the
# last cell before that spacer.
SUBSECTION_ROW = """
    <tr>
      <td></td>
      <td><a href="#avail_info">Available Information</a></td>
      <td><a href="#avail_info">10</a></td>
      <td></td>
      <td></td>
      <td><a href="#non_gaap">Non-GAAP Financial Measures</a></td>
      <td><a href="#non_gaap">54</a></td>
    </tr>
"""

# The subsection row sits *above* the right column's own "PART III" header, which
# is what gives the phantom its Part: read a column at a time, the right column's
# first links are still governed by the Part the left column ended in. In the real
# filing the leaking link is at ordered position 140 and "PART III" at 151.
TWO_COLUMN_TOC = f"""
<html><body>
<p>TABLE OF CONTENTS</p>
<table>
  <tr><td><a href="#part1">PART I</a></td><td></td><td></td>
      <td></td><td></td><td></td></tr>
  <tr><td><a href="#item3">Item 3</a></td>
      <td><a href="#item3">Legal Proceedings</a></td>
      <td><a href="#item3">10</a></td>
      <td></td><td></td><td></td></tr>
  <tr><td><a href="#part2">PART II</a></td><td></td><td></td>
      <td></td><td></td><td></td></tr>
  {SUBSECTION_ROW}
  <tr><td></td><td></td><td></td>
      <td><a href="#part3">PART III</a></td><td></td><td></td></tr>
  {_item_row('item5', 'Market for Common Equity', 'item10', 'Directors and Officers')}
  {_item_row('item7', 'Management Discussion', 'item11', 'Executive Compensation')}
  {_item_row('item9', 'Changes in Accountants', 'item12', 'Security Ownership')}
</table>
<div id="part1"></div><div id="item3"></div>
<div id="part2"></div><div id="item5"></div><div id="item7"></div>
<div id="item9"></div>
<div id="part3"></div><div id="item10"></div><div id="item11"></div>
<div id="item12"></div>
<div id="avail_info"></div><div id="non_gaap"></div>
</body></html>
"""

# The label a single-column TOC hides two cells to the left: ['Item', '1',
# 'Business', '5']. The scan has to cross the row's midpoint to reach "1".
SINGLE_COLUMN_SPLIT_LABEL = """
<html><body>
<p>TABLE OF CONTENTS</p>
<table>
  <tr><td>Item</td><td>1</td>
      <td><a href="#item1">Business</a></td><td>5</td></tr>
  <tr><td>Item</td><td>1A</td>
      <td><a href="#item1a">Risk Factors</a></td><td>12</td></tr>
  <tr><td>Item</td><td>7</td>
      <td><a href="#item7">Management Discussion</a></td><td>30</td></tr>
</table>
<div id="item1"></div><div id="item1a"></div><div id="item7"></div>
</body></html>
"""


def _analyzer_and_link(html, title):
    """Return an analyzer with its column flag set, and the link titled ``title``."""
    analyzer = TOCAnalyzer(form="10-K")
    tree = analyzer._ensure_tree(html)
    links = tree.xpath('//a[@href]')
    analyzer._order_links_by_toc_column(links)  # sets the two-column flag
    link = next(a for a in links if (a.text_content() or '').strip() == title)
    return analyzer, link


@pytest.mark.fast
def test_right_column_title_does_not_take_left_columns_page_number():
    """The defect itself: "10" is a page number in the other column, not Item 10."""
    analyzer, link = _analyzer_and_link(TWO_COLUMN_TOC, "Non-GAAP Financial Measures")
    assert analyzer._toc_two_column is True

    label = analyzer._extract_preceding_item_label(link)
    assert label == "", f"took {label!r} from the left column"


@pytest.mark.fast
def test_no_phantom_item_10_under_part_ii():
    """A 10-K's Part II has no Item 10, so the key is proof of the leak."""
    analyzer = TOCAnalyzer(form="10-K")
    mapping = analyzer._analyze_generic_toc(TWO_COLUMN_TOC)

    assert "part_ii_item_10" not in mapping, (
        f"phantom section survived: {sorted(mapping)}"
    )
    # The real Item 10 — the right column's own, correctly labelled — is untouched.
    assert mapping.get("part_iii_item_10")


@pytest.mark.fast
def test_left_column_still_reads_its_own_label():
    """Scoping the scan must not cost the left column the label beside it."""
    analyzer, link = _analyzer_and_link(TWO_COLUMN_TOC, "Legal Proceedings")
    assert analyzer._extract_preceding_item_label(link) == "Item 3"


@pytest.mark.fast
def test_single_column_label_two_cells_away_is_still_found():
    """The gate: on a one-column TOC the label is across the midpoint by design,
    and refusing to cross it would lose every item number."""
    analyzer, link = _analyzer_and_link(SINGLE_COLUMN_SPLIT_LABEL, "Business")
    assert analyzer._toc_two_column is False
    assert analyzer._extract_preceding_item_label(link) == "Item 1"


@pytest.mark.fast
def test_two_column_items_keep_their_parts():
    """Guard the GH #924 fix this shares its column test with."""
    analyzer = TOCAnalyzer(form="10-K")
    mapping = analyzer._analyze_generic_toc(TWO_COLUMN_TOC)

    assert "part_i_item_3" in mapping, sorted(mapping)
    for item in ("5", "7", "9"):
        assert f"part_ii_item_{item}" in mapping, sorted(mapping)
    for item in ("10", "11", "12"):
        assert f"part_iii_item_{item}" in mapping, sorted(mapping)


@pytest.mark.network
def test_ambac_item_7_includes_its_non_gaap_subsection():
    """The reported filing. Item 7 ran to the Non-GAAP heading and stopped;
    the rest of MD&A was filed under `part_ii_item_10`."""
    from edgar import find

    sections = find("0000874501-23-000040").obj().document.sections

    assert "part_ii_item_10" not in sections, (
        f"phantom section still present: {sorted(sections)}"
    )

    item_7 = sections["part_ii_item_7"].text()
    assert len(item_7) == 158_411, f"Item 7 is {len(item_7):,} chars (was 149,459)"
    assert "NON-GAAP FINANCIAL MEASURES" in item_7
