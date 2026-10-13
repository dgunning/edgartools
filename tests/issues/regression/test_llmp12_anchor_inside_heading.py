"""
Regression test for edgartools-llmp.12 (phase B): a TOC anchor placed INSIDE
its heading, after the heading text, shifted every section by one heading.

Two 2010 Bowne-style 10-Ks in the boundary corpus put the ``<a name>`` as the
last child of the heading block (``<h2>ITEM 2. PROPERTIES.<a name="item2"></a></h2>``)
or in the middle of its last word (``Prope<a name="2">rties</a>``). Both the
text walk and the markdown slicer started collecting after the anchor and
stopped at the next anchor, so each section lost its own heading and ended
with the NEXT item's heading inside it: 25 of the two filings' 40 item
sections embedded a later heading on the self-consistency ratchet. A modern
filer (915358, Certent 2025) has the same shape with the anchor after the
item number, so every section opened one word short of its label.

GH #1369 fixed the mirror case, an anchor nested FIRST in its heading, for the
slicer only. ``Section.text()`` never went through the slicer. One rule now
serves both: ``section_slicer.heading_block`` moves a boundary from an anchor
inside a heading to the heading's block, at the start and at the end.
"""

import lxml.html
import pytest

from edgar.documents import HTMLParser, ParserConfig
from edgar.documents.utils.section_slicer import extract_section_html, heading_block
from tests.paths import FIXTURES_DIR


def _trailing_anchor_10k(anchor_style: str) -> str:
    """A minimal 10-K whose body anchors sit inside the headings.

    ``anchor_style`` 'trailing' puts the empty anchor after the heading text;
    'midword' wraps the last letters of the title, as the second Bowne filing
    does.
    """
    items = [
        ("1", "BUSINESS"), ("1A", "RISK FACTORS"), ("1B", "UNRESOLVED STAFF COMMENTS"),
        ("2", "PROPERTIES"), ("3", "LEGAL PROCEEDINGS"), ("4", "MINE SAFETY DISCLOSURES"),
        ("5", "MARKET FOR REGISTRANT'S COMMON EQUITY"), ("6", "SELECTED FINANCIAL DATA"),
        ("7", "MANAGEMENT'S DISCUSSION AND ANALYSIS"), ("7A", "QUANTITATIVE AND QUALITATIVE DISCLOSURES"),
        ("8", "FINANCIAL STATEMENTS AND SUPPLEMENTARY DATA"), ("9", "CHANGES IN AND DISAGREEMENTS"),
    ]
    toc_rows = "".join(
        f'<tr><td><a href="#item{n.lower()}">ITEM {n}.</a></td>'
        f'<td><a href="#item{n.lower()}">{title.title()}</a></td><td>{i + 3}</td></tr>'
        for i, (n, title) in enumerate(items)
    )
    body = []
    for i, (n, title) in enumerate(items):
        if i == 4:
            body.append("<p><b>PART II</b></p>")
        if anchor_style == "trailing":
            heading = f'<h2><b>ITEM {n}.</b> {title}<a name="item{n.lower()}"></a></h2>'
        else:
            heading = f'<h2><b>ITEM {n}.</b> {title[:-3]}<a name="item{n.lower()}">{title[-3:]}</a></h2>'
        body.append(heading)
        body.append(f"<p>Body of item {n}, sentence one. Body of item {n}, sentence two.</p>")
    return (
        "<html><body><p><b>FORM 10-K</b></p><p><b>TABLE OF CONTENTS</b></p>"
        f"<table>{toc_rows}</table><p><b>PART I</b></p>{''.join(body)}"
        "<p><b>SIGNATURES</b></p><p>Signed.</p></body></html>"
    )


@pytest.mark.parametrize("anchor_style", ["trailing", "midword"])
def test_section_text_keeps_own_heading_and_excludes_the_next(anchor_style):
    doc = HTMLParser(ParserConfig(form="10-K", detect_sections=True)).parse(_trailing_anchor_10k(anchor_style))

    section = doc.sections["part_i_item_2"]
    assert section.detection_method == "toc", f"fixture must be TOC-detected, got {section.detection_method}"
    text = section.text()

    assert text.startswith("ITEM 2. PROPERTIES"), f"Item 2 lost its own heading: {text[:80]!r}"
    assert "Body of item 2, sentence two." in text
    assert "ITEM 3" not in text, f"Item 3's heading leaked into Item 2: {text[-120:]!r}"
    assert "Body of item 3" not in text


@pytest.mark.parametrize("anchor_style", ["trailing", "midword"])
def test_section_markdown_matches_text_boundaries(anchor_style):
    doc = HTMLParser(ParserConfig(form="10-K", detect_sections=True)).parse(_trailing_anchor_10k(anchor_style))

    md = doc.sections["part_i_item_2"].markdown()

    # The boundary is what is under test. The mid-word anchor itself renders as
    # "PROPERT IES" in markdown (the renderer pads inline <a> elements), which is
    # a renderer spacing defect, not a boundary one, so only the label is checked.
    assert md.startswith("# ITEM 2. PROPERT"), f"markdown lost Item 2's heading: {md[:120]!r}"
    assert "Body of item 2, sentence two" in md
    assert "ITEM 3" not in md, f"markdown leaked Item 3's heading: {md[-160:]!r}"
    assert "Body of item 3" not in md


def test_every_item_opens_on_its_own_heading():
    doc = HTMLParser(ParserConfig(form="10-K", detect_sections=True)).parse(_trailing_anchor_10k("trailing"))

    wrong = {}
    for name, section in doc.sections.items():
        if section.item is None:
            continue
        head = section.text()[:40]
        if not head.startswith(f"ITEM {section.item.upper()}."):
            wrong[name] = head
    assert not wrong, f"sections not opening on their own heading: {wrong}"


def test_slicer_ends_at_the_next_heading_block():
    html = (
        "<html><body><p>Earlier text.</p>"
        '<h2>ITEM 2. PROPERTIES.<a name="item2"></a></h2>'
        "<p>Properties text.</p>"
        '<h2>ITEM 3. LEGAL PROCEEDINGS.<a name="item3"></a></h2>'
        "<p>Legal text.</p></body></html>"
    )

    result = extract_section_html(lxml.html.fromstring(html), "item2", "item3")

    assert result == (
        '<div><h2>ITEM 2. PROPERTIES.<a name="item2"></a></h2>'
        "<p>Properties text.</p></div>"
    ), f"got {result!r}"


def test_anchor_after_body_text_does_not_move_the_boundary():
    # An anchor dropped at the end of a long paragraph is not inside a heading.
    # Moving the start there would pull the previous section's last paragraph
    # in, so the 200-char prefix guard leaves such a boundary alone.
    long_paragraph = "Previous section prose. " * 20
    html = (
        f'<html><body><p>{long_paragraph}<a name="item2"></a></p>'
        "<p><b>ITEM 2. PROPERTIES</b></p><p>Properties text.</p>"
        '<a name="item3"></a><p><b>ITEM 3.</b></p></body></html>'
    )
    tree = lxml.html.fromstring(html)

    assert heading_block(tree.xpath('//a[@name="item2"]')[0]) is None
    result = extract_section_html(tree, "item2", "item3")
    assert "Previous section prose" not in result
    assert result.startswith("<div><p><b>ITEM 2. PROPERTIES</b></p>")


def test_certent_2025_sections_open_on_their_item_label():
    # Tracked fixture: the anchor follows the item number ("ITEM 2.<a .../> PROPERTIES"),
    # so before the fix every section opened one word short of its label.
    path = FIXTURES_DIR / "html" / "915358" / "10k" / "915358-10-k-2025-08-27.html"
    doc = HTMLParser(ParserConfig(form="10-K", detect_sections=True)).parse(path.read_text())

    assert doc.sections["part_i_item_2"].text().startswith("ITEM 2.  PROPERTIES")
    assert doc.sections["part_ii_item_9b"].text().startswith("ITEM 9B.  OTHER INFORMATION")
    item_1a = doc.sections["part_i_item_1a"].text()
    assert item_1a.startswith("ITEM 1A. RISK FACTORS")
    assert "ITEM 1B" not in item_1a
