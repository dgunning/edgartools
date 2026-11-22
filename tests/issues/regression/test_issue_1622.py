"""Regression: a TOC anchor placed after the item heading it marks.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1622

Of the 50 contents-link targets listed in the issue, 49 already open the section
on the heading their contents row names (47 sit before page furniture that the
#1519 pass skips). BXP's 10-Q 0001037540-26-000034 is the exception: the
filer prints ``<div>ITEM 1—Financial Statements.</div>`` and only then the
empty ``<div id="i0c46…_22">`` its contents row links to, so Part I, Item 1
opened on the balance sheet and its heading fell into no section.
"""
import pytest

from edgar.documents.config import ParserConfig
from edgar.documents.parser import HTMLParser


def _filing(item1_heading_before_anchor: str, item1_body_start: str) -> str:
    return f"""<html><body>
<p>TABLE OF CONTENTS</p>
<table>
<tr><td><a href="#p1">PART I. FINANCIAL INFORMATION</a></td><td>2</td></tr>
<tr><td><a href="#i1">Item 1. Financial Statements</a></td><td>3</td></tr>
<tr><td><a href="#i2">Item 2. Management's Discussion and Analysis</a></td><td>9</td></tr>
<tr><td><a href="#i3">Item 3. Quantitative and Qualitative Disclosures About Market Risk</a></td><td>12</td></tr>
<tr><td><a href="#i4">Item 4. Controls and Procedures</a></td><td>13</td></tr>
</table>
<hr/>
<div id="p1"></div>
<div><span>PART I. FINANCIAL INFORMATION</span></div>
{item1_heading_before_anchor}
<div id="i1"></div>
<div><span><br/></span></div>
{item1_body_start}
<p>Total assets were $26,000 million at the end of the quarter, and the balance sheet is unaudited.</p>
<div id="i2"></div>
<div><span>ITEM 2. Management's Discussion and Analysis.</span></div>
<p>Revenue rose during the quarter because more office space was leased than in the prior year.</p>
<div id="i3"></div>
<div><span>ITEM 3. Quantitative and Qualitative Disclosures About Market Risk.</span></div>
<p>Interest rate risk is described in the annual report and has not changed materially.</p>
<div id="i4"></div>
<div><span>ITEM 4. Controls and Procedures.</span></div>
<p>Disclosure controls and procedures were effective at the end of the period.</p>
</body></html>"""


def _sections(html: str):
    return HTMLParser(ParserConfig(form="10-Q", detect_sections=True)).parse(html).sections


def test_section_starts_at_its_heading_printed_before_the_anchor():
    html = _filing("<div><span>ITEM 1—Financial Statements.</span><span> </span></div>",
                   "<table><tr><td>CONSOLIDATED BALANCE SHEETS</td></tr></table>")
    item1 = _sections(html)["part_i_item_1"].text()
    assert item1.startswith("ITEM 1—Financial Statements.")
    assert "CONSOLIDATED BALANCE SHEETS" in item1
    assert "ITEM 2" not in item1


def test_another_items_heading_before_the_anchor_is_not_taken():
    # The block before Item 1's anchor names a different item: the section
    # keeps its own start.
    html = _filing("<div><span>ITEM 9. Placeholder heading.</span></div>",
                   "<table><tr><td>CONSOLIDATED BALANCE SHEETS</td></tr></table>")
    item1 = _sections(html)["part_i_item_1"].text()
    assert item1.lstrip().startswith("CONSOLIDATED BALANCE SHEETS")


def test_own_heading_after_the_anchor_wins():
    # Heading on both sides of the anchor (a running header above it): the
    # one that follows the anchor is the section's start, as before.
    html = _filing("<div><span>ITEM 1—Financial Statements.</span></div>",
                   "<div><span>ITEM 1. FINANCIAL STATEMENTS</span></div>")
    item1 = _sections(html)["part_i_item_1"].text()
    assert item1.lstrip().startswith("ITEM 1. FINANCIAL STATEMENTS")


@pytest.mark.network
@pytest.mark.vcr
def test_bxp_10q_part_i_item_1_opens_on_its_heading():
    from edgar import find
    tenq = find("0001037540-26-000034").obj()
    item1 = tenq["Part I, Item 1"]
    assert item1.startswith("ITEM 1—Financial Statements.")
    assert len(item1) == 120209
    # The neighbouring item is unchanged (the filer writes "Item\xa02").
    item2 = tenq["Part I, Item 2"]
    assert item2.startswith("Item\xa02—Management’s Discussion and Analysis")
    assert len(item2) == 144854
