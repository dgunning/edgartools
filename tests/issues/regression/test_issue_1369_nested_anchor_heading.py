"""
Regression test for GitHub issue #1369: section slicer drops a section's own heading

On pre-2010 filings the TOC anchor is nested inside the heading it marks
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