"""
Regression test for edgartools-llmp.12.1: plain-text filings got no item sections.

A plain-text primary document reaches the parser as one pre-wrap <div>, and the
builder emitted each run of text between two <TABLE>s as a single TextNode.
Section detection finds headers among nodes and bounds items at node edges, so
headings buried in those runs were invisible and nothing could end an item
before them. BriteSmile's 2001 10-K held Items 8-14 in one 76k-character node
and got a single section, 'mda', which ran to the end of the filing. Blank
lines are that format's paragraph breaks; each block is now a paragraph, and
the rendered text is unchanged.
"""

from edgar.documents import HTMLParser, ParserConfig
from edgar.documents.extractors.text_extractor import TextExtractor
from edgar.documents.nodes import ContainerNode, ParagraphNode, TextNode
from tests.paths import FIXTURES_DIR

BRITESMILE = FIXTURES_DIR / "parity_gate" / "10-K" / "0000927356-01-000369.html"

# Like the real filings, it carries an SGML <TABLE>: a wrapper <div> holding
# only text builds as one paragraph and is not split.
PLAIN_10K = """<html><body><div>
                     ANNUAL REPORT
<TABLE><TR><TD>Widgets sold</TD><TD>1,000</TD></TR></TABLE>

PART I

ITEM 1.  BUSINESS

The Company makes widgets and sells
them to wholesalers.

ITEM 2.  PROPERTIES

The Company leases one plant.

PART II

ITEM 7.  MANAGEMENT'S DISCUSSION AND ANALYSIS OF FINANCIAL CONDITION
         AND RESULTS OF OPERATIONS

Revenue rose because more widgets
were sold.

ITEM 8.  FINANCIAL STATEMENTS AND SUPPLEMENTARY DATA

The financial statements follow page F-1.
"""


def _parse(html, form="10-K"):
    return HTMLParser(ParserConfig(form=form, detect_sections=True)).parse(html)


def test_britesmile_items_end_at_the_next_items_heading():
    sections = _parse(BRITESMILE.read_text(errors="ignore")).sections
    assert len(sections) == 12  # was 1
    mda = sections["mda"].text()
    assert len(mda) == 73326  # was 218,348, through Items 8-14 to page F-25
    assert mda.startswith("ITEM 7. MANAGEMENT'S DISCUSSION AND ANALYSIS")
    assert "ITEM 8." not in mda
    item_8 = sections["financial_statements"].text()
    assert item_8.startswith("ITEM 8. FINANCIAL STATEMENTS AND SUPPLEMENTARY DATA")
    assert item_8.rstrip().endswith("forth on pages F-1 through F-28.")


def test_blank_line_blocks_become_paragraphs_and_the_text_is_unchanged():
    doc = _parse(PLAIN_10K)
    blocks = [p.text().strip() for p in doc.root.walk() if isinstance(p, ParagraphNode)]
    assert blocks[:5] == ["PART I", "ITEM 1. BUSINESS",
                          "The Company makes widgets and sells\nthem to wholesalers.",
                          "ITEM 2. PROPERTIES", "The Company leases one plant."]
    assert len(blocks) == 10
    # Siblings render with the blank line that separated them: this is the
    # text the single TextNode produced before the split, character for character.
    assert doc.text() == (
        "ANNUAL REPORT\n\n  Widgets sold      1,000\n\nPART I\n\nITEM 1. BUSINESS\n\n"
        "The Company makes widgets and sells\nthem to wholesalers.\n\nITEM 2. PROPERTIES\n\n"
        "The Company leases one plant.\n\nPART II\n\nITEM 7. MANAGEMENT'S DISCUSSION AND ANALYSIS "
        "OF FINANCIAL CONDITION\nAND RESULTS OF OPERATIONS\n\nRevenue rose because more widgets\n"
        "were sold.\n\nITEM 8. FINANCIAL STATEMENTS AND SUPPLEMENTARY DATA\n\n"
        "The financial statements follow page F-1.")


def test_a_page_marker_paragraph_is_not_split():
    # An unclosed SGML <PAGE> nests the rest of the filing in an inline element
    # and the wrapper builds as a paragraph, which renders its children without
    # a blank line between them: splitting there would lose every paragraph break.
    doc = _parse("<html><body><div><page>\nFIRST BLOCK\n\nSECOND BLOCK\n", form="N-CSR")
    assert "FIRST BLOCK\n\nSECOND BLOCK" in doc.text()


def test_a_short_first_paragraph_is_a_bullet_only_when_it_is_a_glyph():
    def container(first):
        node = ContainerNode()
        for text in (first, "A long paragraph of filing text that follows it."):
            paragraph = ParagraphNode()
            paragraph.add_child(TextNode(content=text))
            node.add_child(paragraph)
        return node

    extractor = TextExtractor()
    assert extractor._is_bullet_point_container(container("•"))
    # "-1-" is a plain-text filing's first page number, not a bullet glyph.
    assert not extractor._is_bullet_point_container(container("-1-"))
