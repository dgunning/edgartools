"""
Regression test for GitHub issue #1369: section slicer drops a section's own heading

On some filings, mostly pre-2010 the TOC anchor is nested inside the heading it marks
(``<p><b><a name="..."></a>ITEM 2. PROPERTIES</b></p>``). The slicer turned
collection on after the anchor, so the heading's own block had already been
passed and every item section came back without its heading. The issue reports
this on Google Inc.'s FY2004 10-K (0001193125-05-065298), where none of the 18
TOC-detected item sections started with its "ITEM N." heading.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1369
"""

import lxml.html

from edgar.documents.utils.section_slicer import extract_section_html

# Pre-2010 layout: each anchor sits inside its heading.
NESTED_ANCHOR_HTML = """<html><body>
<p><b><a name="item1"></a>ITEM 1. BUSINESS</b></p>
<p>Business text.</p>
<p><b><a name="item2"></a>ITEM 2. PROPERTIES</b></p>
<p>Properties text.</p>
<p><b><a name="item3"></a>ITEM 3. LEGAL PROCEEDINGS</b></p>
<p>Legal text.</p>
</body></html>"""

# Modern layout: each anchor is a sibling placed before its heading.
SIBLING_ANCHOR_HTML = """<html><body>
<a name="item1"></a><p><b>ITEM 1. BUSINESS</b></p>
<p>Business text.</p>
<a name="item2"></a><p><b>ITEM 2. PROPERTIES</b></p>
<p>Properties text.</p>
<a name="item3"></a><p><b>ITEM 3. LEGAL PROCEEDINGS</b></p>
<p>Legal text.</p>
</body></html>"""


def test_section_keeps_its_own_heading_when_anchor_is_nested():
    tree = lxml.html.fromstring(NESTED_ANCHOR_HTML)

    html = extract_section_html(tree, "item2", "item3")

    heading = '<p><b><a name="item2"></a>ITEM 2. PROPERTIES</b></p>'
    assert html.startswith("<div>" + heading), f"Item 2 should start with its own heading, got {html!r}"
    assert "<p>Properties text.</p>" in html, f"Item 2 body is missing, got {html!r}"
    assert "ITEM 3. LEGAL PROCEEDINGS" not in html, f"Item 3's heading leaked into Item 2, got {html!r}"


def test_sibling_anchor_layout_is_unchanged():
    tree = lxml.html.fromstring(SIBLING_ANCHOR_HTML)

    html = extract_section_html(tree, "item2", "item3")

    expected = "<div><p><b>ITEM 2. PROPERTIES</b></p>\n<p>Properties text.</p>\n</div>"
    assert html == expected, f"modern layout output changed, got {html!r}"

def test_font_wrapped_heading_reaches_its_paragraph():
    # Google FY2004 10-K Items 1-4: <P><FONT><B><A NAME=...></A>ITEM N. ...</B></FONT></P>
    html = (
        "<html><body><p>Business text.</p>"
        '<p><font><b><a name="item2"></a>ITEM 2. PROPERTIES</b></font></p>'
        "<p>Properties text.</p>"
        '<p><font><b><a name="item3"></a>ITEM 3. LEGAL PROCEEDINGS</b></font></p>'
        "</body></html>"
    )

    result = extract_section_html(lxml.html.fromstring(html), "item2", "item3")

    heading = '<p><font><b><a name="item2"></a>ITEM 2. PROPERTIES</b></font></p>'
    assert result.startswith("<div>" + heading), f"heading should keep its <p> and <font>, got {result!r}"


def test_heading_split_across_table_cells_keeps_both_cells():
    # Google FY2004 10-K Item 15: the anchor is in the first cell, the rest of the heading in the second.
    html = (
        "<html><body><p>Earlier text.</p>"
        '<table><tr><td><font><b><a name="item15"></a>ITEM 15. EXHIBITS</b></font></td>'
        "<td><font><b>AND FINANCIAL STATEMENT SCHEDULES</b></font></td></tr></table>"
        "<p>Exhibit list.</p>"
        '<p><b><a name="signatures"></a>SIGNATURES</b></p>'
        "</body></html>"
    )

    result = extract_section_html(lxml.html.fromstring(html), "item15", "signatures")

    row = (
        '<table><tr><td><font><b><a name="item15"></a>ITEM 15. EXHIBITS</b></font></td>'
        "<td><font><b>AND FINANCIAL STATEMENT SCHEDULES</b></font></td></tr></table>"
    )
    assert result.startswith("<div>" + row), f"both cells of the heading should be kept, got {result!r}"


def test_heading_already_in_its_own_tags_is_left_alone():
    # Modern layout: an empty anchor followed by sibling tags that hold the heading. Nothing is dropped
    # here, so the start must not move (it would only re-flow the heading's lines).
    html = (
        "<html><body><div><p>Earlier text.</p></div>"
        '<div><span id="item9c"></span><span>Item 9C.</span><span>DISCLOSURE</span></div>'
        "<p>Not applicable.</p>"
        '<div><span id="item10"></span><span>Item 10.</span></div>'
        "</body></html>"
    )

    result = extract_section_html(lxml.html.fromstring(html), "item9c", "item10")

    assert result.startswith("<div><span>Item 9C.</span><span>DISCLOSURE</span>"), f"got {result!r}"