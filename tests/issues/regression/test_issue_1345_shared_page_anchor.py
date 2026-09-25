"""Regression: items that start on one printed page no longer return one span.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1345
Bead: edgartools-rc46

When a filer's TOC links page numbers rather than items, every item that
begins on a page resolves to that page's anchor, and every consumer sliced
those keys to the identical span. ``_resolve_anchor_collisions`` (GH #920) can
only re-point a displaced item at a *different* body anchor; on these filings
the body headings sit behind the same page anchor too, so it gave up
("body header shares the same anchor") and, e.g., Southern Co's
``obj['Item 7A']`` returned all 282,239 chars of Item 7.

The fix separates such items by their heading *elements*: a displaced item
starts at its own heading and ends at the next item heading or the next
navigable (link-targeted) anchor, whichever comes first; the owner is cut at
the first displaced heading only when the displaced items tile the rest of
the span. Southern's 7A is a cross-reference inside Item 7's first page with
MD&A resuming on the next page, so 7A stops at that page and Item 7 keeps
its MD&A. The same mechanism admits a missing core item the union-merge
(GH #904) used to refuse because its body anchor was already claimed (Ondas's
Item 1A inside Item 1's span).

Offline (local fixtures):
  SOUTHERN CO 10-K       0000092122-26-000006  tests/fixtures/html/so/10k/
  EVERSOURCE ENERGY 10-K 0000072741-24-000005  tests/fixtures/html/es/10k/
  Ondas Inc. 10-K        0001213900-26-035981  tests/fixtures/html/onds/10k/
  20-F page-anchor TOC   0001062993-21-003193  tests/fixtures/parity_gate/20-F/
"""
from pathlib import Path

import pytest

from edgar.documents.config import ParserConfig
from edgar.documents.parser import HTMLParser

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


def _sections(relpath: str, form: str):
    html = (_FIXTURES / relpath).read_text()
    return HTMLParser(ParserConfig(form=form, detect_sections=True)).parse(html).sections


@pytest.fixture(scope="module")
def southern():
    return _sections("html/so/10k/so-10-k-2026-02-19.html", "10-K")


@pytest.fixture(scope="module")
def eversource():
    return _sections("html/es/10k/es-10-k-2024-02-14.html", "10-K")


@pytest.fixture(scope="module")
def ondas():
    return _sections("html/onds/10k/onds-10-k-2026-03-30.html", "10-K")


@pytest.fixture(scope="module")
def page_anchor_20f():
    return _sections("parity_gate/20-F/0001062993-21-003193.html", "20-F")


# --- Southern Co: interleaved 7A, the case a naive cut gets wrong -------------

def test_southern_item7a_is_its_own_cross_reference(southern):
    item7 = southern["part_ii_item_7"].text()
    item7a = southern["part_ii_item_7a"].text()
    assert item7a != item7
    assert len(item7a) == 347  # was 282,239 — all of Item 7
    assert item7a.startswith("Item 7A.QUANTITATIVE AND QUALITATIVE DISCLOSURES ABOUT MARKET RISK")
    assert '"Market Price Risk" in Item 7 herein' in item7a
    # 7A stops at the end of its page block; MD&A's body is not in it.
    assert "Business Activities" not in item7a


def test_southern_item7_keeps_its_mda(southern):
    item7 = southern["part_ii_item_7"].text()
    # Owner's span is unchanged: the displaced 7A text sits inside Item 7's
    # first page and the MD&A resumes after it.
    assert len(item7) == 282_239
    assert "COMBINED MANAGEMENT'S DISCUSSION AND ANALYSIS" in item7
    assert "Southern Company is a holding company that owns all of the common stock" in item7


def test_southern_other_shared_pages_are_separated(southern):
    item5 = southern["part_ii_item_5"].text()
    item6 = southern["part_ii_item_6"].text()
    item9a = southern["part_ii_item_9a"].text()
    item9b = southern["part_ii_item_9b"].text()
    # Items 5 and 6 tile their page: Item 5 now ends at Item 6's heading.
    assert (len(item5), len(item6)) == (1393, 21)  # both were 1,416
    assert item6 == "Item 6.RESERVED\n\nII-1"
    assert "Item 6." not in item5
    # 9B continues onto the next page (the trading-arrangement table) and
    # still stops at Item 9C.
    assert (len(item9a), len(item9b)) == (2189, 2142)  # both were 4,333
    assert item9a.startswith("Item 9A.CONTROLS AND PROCEDURES")
    assert item9b.startswith("Item 9B.OTHER INFORMATION")
    assert "Item 9B." not in item9a
    assert "Kimberly S. Greene" in item9b
    assert "Item 9C." not in item9b


def test_southern_combined_part_iii_is_left_alone(southern):
    """Items 11-13 have no heading of their own (one paragraph incorporates
    Items 10-14 by reference), so their extent is unknown and the group is
    deliberately left as one span rather than guessed at."""
    texts = {k: southern[k].text() for k in
             ("part_iii_item_10", "part_iii_item_11", "part_iii_item_12", "part_iii_item_13")}
    assert {len(t) for t in texts.values()} == {2917}


# --- Eversource: three consecutive items on one page -------------------------

@pytest.mark.parametrize("key,length,heading", [
    ("part_ii_item_9", 227, "Item 9.\xa0\xa0\xa0\xa0Changes in and Disagreements"),
    ("part_ii_item_9a", 3635, "Item 9A.\xa0\xa0\xa0\xa0Controls and Procedures"),
    ("part_ii_item_9b", 508, "Item 9B.\xa0\xa0\xa0\xa0Other Information"),
])
def test_eversource_items_9_9a_9b_are_distinct(eversource, key, length, heading):
    text = eversource[key].text()
    assert len(text) == length  # all three were 4,374
    assert text.startswith(heading)


def test_eversource_items_do_not_overlap(eversource):
    item9 = eversource["part_ii_item_9"].text()
    item9a = eversource["part_ii_item_9a"].text()
    assert "Item 9A." not in item9
    assert "Item 9B." not in item9a


# --- Ondas: union-merge admits a missing item by its heading position --------

def test_ondas_item1_ends_at_item1a(ondas):
    item1 = ondas["part_i_item_1"].text()
    item1a = ondas["part_i_item_1a"].text()
    assert len(item1) == 68_092  # was 190,306 — Business plus all Risk Factors
    assert "Item 1A. Risk Factors" not in item1
    assert len(item1a) == 122_212
    assert item1a.startswith("Item 1A. Risk Factors\n\nInvesting in our common")


# --- 20-F with page-number-only TOC links (bead edgartools-rc46, shape A) ----

_20F_EXPECTED = {
    # page_6
    "part_i_item_1": 3016, "part_i_item_2": 124, "part_i_item_3": 66728,
    # page_29
    "part_i_item_4a": 1105, "part_i_item_5": 10431,
    # page_59
    "part_i_item_12": 1544, "part_ii_item_13": 94, "part_ii_item_14": 123,
    "part_ii_item_15": 4888,
    # page_61
    "part_ii_item_16a": 2890, "part_ii_item_16b": 428, "part_ii_item_16c": 474,
    # page_62
    "part_ii_item_16d": 1865, "part_ii_item_16e": 118, "part_ii_item_16f": 671,
    # page_63
    "part_ii_item_17": 2506, "part_ii_item_18": 181349,
}


def test_20f_page_anchor_collision_groups_are_resolved(page_anchor_20f):
    texts = {k: page_anchor_20f[k].text() for k in _20F_EXPECTED}
    assert {k: len(t) for k, t in texts.items()} == _20F_EXPECTED
    # Before: six groups of identical spans (69,904 / 11,554 / 6,704 / 3,828
    # / 2,690 / 183,873 chars). Now every key's text is distinct.
    assert len(set(texts.values())) == len(texts)
    assert texts["part_ii_item_16e"].startswith("ITEM 16E.")
    assert "ITEM 18." not in texts["part_ii_item_17"]


def test_ondas_risk_factors_friendly_name_still_resolves(ondas):
    """The TOC now keys Item 1A as part_i_item_1a; the pattern extractor used
    to supply it as ``risk_factors``. Both spellings must reach one section."""
    by_name = ondas["risk_factors"].text()
    assert len(by_name) == 122_212
    assert ondas["Item 1A"].text() == by_name
    assert ondas.get_item("1A").text() == by_name
    assert ondas.get("risk_factors").text() == by_name
    assert "risk_factors" in ondas


# --- markdown()/HTML honour the heading bound when the heading is nested -----

_NESTED_TOC_ROWS = "".join(
    f'<tr><td><a href="#{anchor}">Item {num}. {title}</a></td></tr>'
    for num, title, anchor in [
        ("1", "Business", "p1"), ("1A", "Risk Factors", "p2"), ("2", "Properties", "p3"),
        ("3", "Legal Proceedings", "p4"), ("5", "Market for Common Equity", "p5"),
        ("7", "Management's Discussion and Analysis", "p6"),
        ("7A", "Quantitative and Qualitative Disclosures", "p7"),
        ("8", "Financial Statements", "p8"),
        ("9", "Changes in and Disagreements with Accountants", "p50"),
        ("9A", "Controls and Procedures", "p50"),
        ("9B", "Other Information", "p50"),
        ("10", "Directors and Executive Officers", "p51"),
    ])


def _body_item(anchor, num, title, filler):
    return (f'<div id="{anchor}"></div><p style="font-weight:bold">Item {num}. {title}</p>'
            f'<p>{filler}</p>')


_NESTED_HTML = (
    "<html><body><table>" + _NESTED_TOC_ROWS + "</table>"
    + _body_item("p1", "1", "Business", "We make widgets. " * 40)
    + _body_item("p2", "1A", "Risk Factors", "Widgets may fail. " * 40)
    + _body_item("p3", "2", "Properties", "We lease a plant. " * 10)
    + _body_item("p4", "3", "Legal Proceedings", "None pending. " * 5)
    + _body_item("p5", "5", "Market for Common Equity", "Listed on NYSE. " * 10)
    + _body_item("p6", "7", "Management's Discussion and Analysis", "Sales rose. " * 60)
    + _body_item("p7", "7A", "Quantitative and Qualitative Disclosures", "Rates matter. " * 10)
    + _body_item("p8", "8", "Financial Statements", "See the statements. " * 40)
    + '<div id="p50"></div>'
    + '<p style="font-weight:bold">Item 9. Changes in and Disagreements with Accountants</p>'
    + "<p>" + "No disagreements occurred. " * 5 + "</p>"
    # 9A's heading and body sit inside a wrapper div: the wrapper starts inside
    # Item 9's range, so a naive HTML slice would serialize all of it.
    + '<div><p style="font-weight:bold">Item 9A. Controls and Procedures</p>'
    + "<p>" + "Controls were effective. " * 10 + "</p></div>"
    + '<p style="font-weight:bold">Item 9B. Other Information</p>'
    + "<p>" + "Nothing further to report. " * 3 + "</p>"
    + _body_item("p51", "10", "Directors and Executive Officers", "See the proxy. " * 5)
    + "</body></html>"
)


def test_nested_heading_bound_holds_in_markdown():
    sections = HTMLParser(ParserConfig(form="10-K", detect_sections=True)).parse(_NESTED_HTML).sections
    item9 = sections["part_ii_item_9"]
    item9a = sections["part_ii_item_9a"]
    assert item9.text().startswith("Item 9. Changes in and Disagreements")
    assert "Item 9A" not in item9.text()
    assert item9a.text().startswith("Item 9A. Controls and Procedures")
    # The end heading is nested in a <div> Item 9's walk entered; markdown
    # used to serialize that whole div, 9A and all.
    md9 = item9.markdown()
    assert "No disagreements occurred" in md9
    assert "Item 9A" not in md9
    assert "Controls were effective" not in md9


# --- gh-878 hard end now also bounds markdown()/tables() ---------------------

def test_prospectus_trailing_section_markdown_stops_at_financial_statements():
    """Honouring SectionBoundary.end_element in the HTML slicer (added for the
    heading bounds above) also applies the existing gh-878 financial-statements
    bound to markdown()/tables(). text() already stopped there; markdown used
    to run on through the F-pages (242,142 chars, 74 tables)."""
    html = (_FIXTURES / "html/abnb/424b4/abnb-424b4-2020-12-09.html").read_text()
    sections = HTMLParser(ParserConfig(form="424B4", detect_sections=True)).parse(html).sections
    section = sections["where_you_can_find_more_information"]
    assert len(section.text()) == 1910
    md = section.markdown()
    assert len(md) == 1934
    assert "Index to Consolidated Financial Statements".upper() not in md.upper()
    # The section has no table of its own; the F-pages index no longer leaks in.
    assert section.tables() == []
