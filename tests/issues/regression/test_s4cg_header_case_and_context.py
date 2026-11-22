"""
Regression test for edgartools-s4cg: words that are not titles became headings.

PatternBasedDetector matched every pattern with re.IGNORECASE, so the shape
patterns whose meaning is in their case class ('All caps headers' is
``^[A-Z\\s]+$``) matched any run of letters. Apple's FY2024 10-K
(0000320193-24-000123) promoted the cover page's centered ``<div><span>or</span></div>``,
between the annual-report and transition-report boxes, to a heading.

Dropping the flag alone, as the bead proposed, was measured over the
128-filing parser corpus and was worse. Two other things had been hidden by the
pattern detector's vote, which ``_combine_results`` averages in:

* ContextualDetector scored 0.8 on context alone (a heading before, a long
  paragraph after, early in the document) without the text looking like a
  header, so checkbox answers ('No', 236 of them) and split-off function words
  ('and', 86) became headings.
* An inline run in the middle of a sentence was offered to header detection, so
  the style detector, now scoring it alone, promoted
  ``<p>Paragraph with <b>bold</b> ...</p>``'s bold word.

The fix keeps the vocabulary patterns case-insensitive with an inline ``(?i)``,
makes the shape patterns case-sensitive, gates ContextualDetector on the text,
and skips header detection for an inline element that has text before it in
its block. Over the corpus no section is lost, added or moved; 3,570 + 561
headings are removed, such as the prose cross-references in Cheniere's 2025
10-K ('...other factors described in Item 1A. Risk Factors in this Annual
Report...', 0000003570-26-000005).
"""

import lxml.html
import pytest

from edgar.documents import HTMLParser, ParserConfig
from edgar.documents.nodes import HeadingNode
from edgar.documents.renderers.markdown import MarkdownRenderer
from edgar.documents.strategies.header_detection import PatternBasedDetector
from edgar.documents.types import ParseContext
from tests.paths import FIXTURES_DIR


def _headings(doc):
    return [n.text().strip() for n in doc.root.walk() if isinstance(n, HeadingNode)]


def _parse_fixture(path, form="10-K"):
    html = (FIXTURES_DIR / "html" / path).read_text(encoding="utf-8")
    return HTMLParser(ParserConfig(form=form)).parse(html)


def test_apple_cover_page_or_is_not_a_heading():
    headings = _headings(_parse_fixture("aapl/10k/aapl-10-k-2024-11-01.html"))
    assert "or" not in headings
    assert not [h for h in headings if h in ("No", "and")], headings[:20]


def test_cheniere_prose_cross_references_are_not_headings():
    doc = _parse_fixture("lng/10k/lng-10-k-2026-02-26.html")
    headings = _headings(doc)
    # On main this fixture carried the cross-reference as a heading 14 times; the
    # filing's own Item 1A heading is a block of its own and stays.
    assert headings.count("Item 1A. Risk Factors") <= 1, headings.count("Item 1A. Risk Factors")
    assert "Item 1A. Risk Factors" not in [h for h in headings if h.startswith("•")]


@pytest.mark.parametrize("text, matches", [
    ("BUSINESS", True),
    ("Business", True),        # the vocabulary patterns stay case-insensitive
    ("Risk Factors", True),
    ("ITEM 7. MANAGEMENT'S DISCUSSION", True),
    ("item 7. management's discussion", True),
    ("PART II", True),
    ("OVERVIEW", True),        # all caps
    ("Results of Operations", True),
    ("(B) The Connecticut Light and Power Company", True),
    ("a. Basis of Presentation", True),
    ("or", False),             # was all caps under the flag
    ("the company also offers", False),
    ("1. lowercase heading", False),
])
def test_pattern_case_intent(text, matches):
    element = lxml.html.fragment_fromstring(f"<div><div>{text}</div><div>x</div></div>").getchildren()[0]
    hit = PatternBasedDetector().detect(element, ParseContext())
    assert (hit is not None) is matches, (text, hit)


def test_mid_sentence_emphasis_is_not_a_heading():
    doc = HTMLParser(ParserConfig()).parse(
        "<html><body><h1>Title</h1><p>Paragraph with <b>bold</b> and <i>italic</i>.</p>"
        "<div>Hello <b>world</b> again, in a sentence long enough to be prose.</div></body></html>")
    assert _headings(doc) == ["Title"]
    md = MarkdownRenderer().render(doc)
    assert "**bold**" in md and "# world" not in md, md


def test_checkbox_answer_is_not_a_heading():
    doc = HTMLParser(ParserConfig(form="10-K")).parse(
        "<html><body><div><b>ANNUAL REPORT PURSUANT TO SECTION 13</b></div>"
        "<div>No</div>"
        "<div>" + "Indicate by check mark whether the registrant is a well-known seasoned issuer. " * 3 + "</div>"
        "</body></html>")
    assert "No" not in _headings(doc)
