"""GH #924 — a two-column TOC put items under the wrong Part, overflowing Item 7.

Ambac's FY2022 10-K (`0000874501-23-000040`) lays its table of contents out in two
side-by-side columns — Parts I and II down the left, Parts III and IV down the
right — and the HTML interleaves them one row at a time::

    Item 3  Legal Proceedings  | Item 10  Directors, Executive Officers
    Item 4  Mine Safety        | Item 11  Executive Compensation
    PART II                    | Item 12  Security Ownership

A linear scan therefore saw both columns' Part headers in one running context, so
items inherited whichever column last declared a Part: Items 7A-9B came out under
Part I and Items 13-14 under Part II. Wrong Parts scramble the *logical* order
that section boundaries are sorted by, which inverted three spans and ran Item 7
to 538,701 chars — roughly 70% of it Items 8, 9A and 10-15.

The reporter verified this is a residual shape rather than a regression of the
GH #904 fix. Bead edgartools-f3qn.
"""

import pytest

from edgar.documents.utils.toc_analyzer import TOCAnalyzer


def _two_column_row(left_item, left_title, right_item, right_title):
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


TWO_COLUMN_TOC = f"""
<html><body>
<p>TABLE OF CONTENTS</p>
<table>
  <tr><td><a href="#part1">PART I</a></td><td></td><td></td>
      <td><a href="#part3">PART III</a></td><td></td><td></td></tr>
  {_two_column_row('item3', 'Legal Proceedings', 'item10', 'Directors and Officers')}
  {_two_column_row('item4', 'Mine Safety Disclosures', 'item11', 'Executive Compensation')}
  <tr><td><a href="#part2">PART II</a></td><td></td><td></td>
      <td><a href="#item12">Item 12</a></td>
      <td><a href="#item12">Security Ownership</a></td>
      <td><a href="#item12">99</a></td></tr>
  {_two_column_row('item5', 'Market for Common Equity', 'item13', 'Certain Relationships')}
  {_two_column_row('item7', 'Management Discussion', 'item14', 'Principal Accountant Fees')}
</table>
<div id="part1"></div><div id="item3"></div><div id="item4"></div>
<div id="part2"></div><div id="item5"></div><div id="item7"></div>
<div id="part3"></div><div id="item10"></div><div id="item11"></div>
<div id="item12"></div><div id="item13"></div><div id="item14"></div>
</body></html>
"""

# A conventional single-column TOC: [label][title][page] in one row. The label
# and page cells already straddle the row's midpoint, so a naive cell-half test
# reads this as two columns.
SINGLE_COLUMN_TOC = """
<html><body>
<p>TABLE OF CONTENTS</p>
<table>
  <tr><td colspan="3"><a href="#part1">PART I</a></td></tr>
  <tr><td><a href="#item1">Item 1</a></td>
      <td><a href="#item1">Business</a></td>
      <td><a href="#item1">5</a></td></tr>
  <tr><td><a href="#item1a">1A.</a></td>
      <td><a href="#item1a">Risk Factors</a></td>
      <td><a href="#item1a">12</a></td></tr>
  <tr><td colspan="3"><a href="#part2">PART II</a></td></tr>
  <tr><td><a href="#item5">Item 5</a></td>
      <td><a href="#item5">Market for Common Equity</a></td>
      <td><a href="#item5">30</a></td></tr>
</table>
<div id="part1"></div><div id="item1"></div><div id="item1a"></div>
<div id="part2"></div><div id="item5"></div>
</body></html>
"""


def _links(html):
    analyzer = TOCAnalyzer(form="10-K")
    tree = analyzer._ensure_tree(html)
    return analyzer, tree.xpath('//a[@href]')


@pytest.mark.fast
def test_two_column_layout_is_detected():
    analyzer, links = _links(TWO_COLUMN_TOC)
    assert analyzer._detect_two_column_toc(links) is True


@pytest.mark.fast
def test_single_column_layout_is_not_detected():
    """The false positive that matters: mis-detecting a one-column TOC discards
    the Part headers a 10-Q depends on, moving its Part II items under Part I."""
    analyzer, links = _links(SINGLE_COLUMN_TOC)
    assert analyzer._detect_two_column_toc(links) is False


@pytest.mark.fast
def test_split_heading_links_do_not_look_like_two_columns():
    """J&J's TOC splits one heading across several links in a single cell
    ("P" / "art" / "I"). That is several links, but one column."""
    html = """
    <html><body><table>
      <tr><td><a href="#p1">P</a><a href="#p1">art</a><a href="#p1">I</a></td></tr>
      <tr><td><a href="#p2">P</a><a href="#p2">art</a><a href="#p2">II</a></td></tr>
      <tr><td><a href="#p3">P</a><a href="#p3">art</a><a href="#p3">III</a></td></tr>
      <tr><td><a href="#p4">P</a><a href="#p4">art</a><a href="#p4">IV</a></td></tr>
    </table>
    <div id="p1"></div><div id="p2"></div><div id="p3"></div><div id="p4"></div>
    </body></html>
    """
    analyzer, links = _links(html)
    assert analyzer._detect_two_column_toc(links) is False


@pytest.mark.fast
@pytest.mark.parametrize(
    "text, is_bare_label",
    [
        ("Item 1", True), ("Item 1A.", True), ("1", True), ("1A.", True),
        ("7A.", True), ("PART II", True),
        ("Business", False), ("Risk Factors", False),
        ("Legal Proceedings", False), ("Item 1. Business", False),
    ],
)
def test_bare_label_recognition(text, is_bare_label):
    assert bool(TOCAnalyzer._TOC_BARE_LABEL_TEXT.match(text)) is is_bare_label


@pytest.mark.fast
def test_right_column_items_keep_their_own_part():
    """Each column's Part headers govern only that column, and the right column
    continues from the Part the left column ended in — how the layout reads."""
    analyzer = TOCAnalyzer(form="10-K")
    mapping = analyzer._analyze_generic_toc(TWO_COLUMN_TOC)

    assert mapping.get("part_i_item_3"), f"Item 3 missing from {sorted(mapping)}"
    assert mapping.get("part_i_item_4"), f"Item 4 missing from {sorted(mapping)}"
    assert mapping.get("part_ii_item_5"), f"Item 5 missing from {sorted(mapping)}"
    assert mapping.get("part_ii_item_7"), f"Item 7 missing from {sorted(mapping)}"
    # The right column: Part III throughout, never Part I or II.
    for item in ("10", "11", "12", "13", "14"):
        assert f"part_iii_item_{item}" in mapping, (
            f"Item {item} not under Part III: {sorted(mapping)}"
        )


@pytest.mark.network
def test_ambac_item_7_stops_at_item_8():
    """The reported filing: Item 7 is the MD&A, not the back half of the 10-K."""
    from edgar import find

    obj = find("0000874501-23-000040").obj()
    body = obj["Item 7"]

    assert body.replace("\xa0", " ").lstrip().startswith("Item 7.")
    # Was 538,701 chars, ~70% of it later items.
    assert len(body) < 200_000, f"Item 7 is {len(body):,} chars"
    for later in ("Item 8.", "Item 9A.", "Item 10."):
        for variant in (later, later.replace(" ", "\xa0")):
            assert variant not in body, f"{later} leaked into Item 7"

    # Parts I and IV bracket the filing correctly; Item 4 was dropped entirely.
    assert "Item 3" in obj.items
    assert "Item 4" in obj.items
