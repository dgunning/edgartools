"""
Regression test for edgartools-llmp.12.1: page-furniture shapes found by the held-out 10-K set.

The filings were retired from the held-out set to ``tests/fixtures/heldout_retired``
so these fixes could be built on them. Each shape left an item boundary on
furniture rather than content:

* TechPrecision (2025) places each item's empty anchor in one ``<div>`` after
  the lines before it. The heading rule read those lines as heading text the
  anchor trailed, so Items 1, 5, 10 and 15 opened on their own "PART I"
  divider and Item 9A on Item 9's heading, which left Item 9 running on to 9C.
* Vasomedical (2013) links Item 1 to an anchor wrapped around "PART I"; the
  slice starts at that block and the furniture pass started at the anchor.
* Plum Creek (2013) prints a "PART II / ITEM 7A" breadcrumb in a running-header
  table on every page; a one-page item never repeats it often enough to count.
* Bright Green (2023) wraps each page number in Word field-code comments,
  and section text printed them: "Field: Sequence; Type: Arabic; Name: PageNo 39".
* Landec (2008) is pattern-detected, and its items ended on "- 22 -" page numbers.
"""
import pytest
from lxml import html as lxml_html

from edgar.documents import HTMLParser, ParserConfig
from edgar.documents.extractors.pattern_section_extractor import SectionExtractor
from edgar.documents.nodes import ContainerNode, ParagraphNode, TextNode
from edgar.documents.utils.section_slicer import heading_block
from tests.paths import FIXTURES_DIR

RETIRED = FIXTURES_DIR / "heldout_retired" / "10-K"


def _sections(accession):
    html = (RETIRED / f"{accession}.html").read_text(errors="ignore")
    return HTMLParser(ParserConfig(form="10-K", detect_sections=True)).parse(html).sections


def _text(section):
    return " ".join(section.text().split())


@pytest.fixture(scope="module")
def techprecision():
    return _sections("0001410578-25-001537")


@pytest.mark.parametrize("name, heading", [
    ("part_i_item_1", "Item 1. Business."),
    ("part_ii_item_5", "Item 5. Market for Registrant"),
    ("part_iii_item_10", "Item 10. Directors, Executive Officers"),
    ("part_iv_item_15", "Item 15. Exhibits and Financial Statement Schedules."),
])
def test_an_item_does_not_open_on_its_own_part_divider(techprecision, name, heading):
    assert _text(techprecision[name]).startswith(heading)  # was "PART I Item 1. Business." etc.


def test_item_9a_does_not_open_on_item_9(techprecision):
    item_9 = _text(techprecision["part_ii_item_9"])
    assert item_9.endswith("Accounting and Financial Disclosure. None.")
    assert "Item 9A" not in item_9  # ran through 9A, 9B and 9C
    assert _text(techprecision["part_ii_item_9a"]).startswith("Item 9A. Controls and Procedures.")


def test_an_anchor_wrapped_around_the_part_divider():
    item_1 = _text(_sections("0001201800-13-000006")["part_i_item_1"])
    assert item_1.startswith("ITEM 1 – BUSINESS Except for historical information")  # was "PART I ITEM 1"


def test_a_part_and_item_breadcrumb_is_furniture():
    sections = _sections("0000849213-13-000007")
    # Was "Table of Contents PART II / ITEM 7A ITEM 7A. ..."
    assert _text(sections["part_ii_item_7a"]).startswith("ITEM 7A. QUANTITATIVE AND QUALITATIVE")
    # Was "... None. PLUM CREEK 2012 FORM 10-K | 143 Table of Contents PART III / ITEM 10"
    assert _text(sections["part_ii_item_9b"]) == "ITEM 9B. OTHER INFORMATION None."


def test_field_code_comments_do_not_print():
    sections = _sections("0001493152-23-012561")
    assert not [n for n, s in sections.items() if "Field: Sequence" in s.text()]
    assert _text(sections["part_i_item_1b"]) == "Item 1B. Unresolved Staff Comments. Not Applicable."
    # Item 8 is the statements at the back and runs to the end of the filing;
    # its last page number ("F-24") is furniture too.
    assert _text(sections["part_ii_item_8"]).endswith("outstanding common stock of Alterola.")


def test_a_pattern_section_ends_before_its_page_number():
    sections = _sections("0001144204-08-044977")
    assert sections["part_i_item_4"].detection_method == "pattern"
    assert _text(sections["part_i_item_4"]).endswith("fiscal year ended May 25, 2008.")  # was "... 2008. - 22 -"
    assert _text(sections["part_ii_item_9b"]) == "Item 9B. Other Information None"


def test_heading_block_ignores_whole_lines_before_the_anchor():
    div = lxml_html.fromstring('<div><p>PART I</p><a id="i1"></a><p>Item 1. Business.</p></div>')
    assert heading_block(div.get_element_by_id("i1")) is None
    # Heading text the anchor trails on its own line still moves the start.
    p = lxml_html.fromstring('<div><p><b>ITEM 2. PROPERTIES.<a id="i2"></a></b></p></div>')
    assert heading_block(p.get_element_by_id("i2")).tag == "p"
    # A heading split across table cells is still one heading.
    t = lxml_html.fromstring('<table><tr><td>ITEM 2.</td><td><a id="i3"></a>PROPERTIES</td></tr></table>')
    assert heading_block(t.get_element_by_id("i3")) is not None


def test_trailing_page_numbers_leave_a_pattern_range():
    def paragraph(text):
        node = ParagraphNode()
        node.add_child(TextNode(content=text))
        return node

    root = ContainerNode()
    for text in ("ITEM 4. SUBMISSION OF MATTERS", "None.", "- 22 -", "Table of Contents"):
        root.add_child(paragraph(text))
    walk = list(root.walk())
    end = SectionExtractor._retreat_past_page_furniture(walk, 1, len(walk))
    assert [n.content for n in walk[1:end] if isinstance(n, TextNode)] == ["ITEM 4. SUBMISSION OF MATTERS", "None."]
