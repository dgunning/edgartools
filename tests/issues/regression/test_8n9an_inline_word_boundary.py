"""
Regression test for edgartools-8n9an: a word a filer wrote across two inline
elements came out split in two places.

1. Headings. ``DocumentBuilder`` stripped each run of an <h1>-<h6> and
   space-joined them, so ``<h2>ITEM 2. PROPERT<a name="2">IES</a></h2>`` (the
   2010 Bowne 10-K 0001140361-10-014238) became the heading text
   'ITEM 2. PROPERT IES', which is also what section detection read.
2. Markdown. ``MarkdownRenderer`` space-joined a paragraph's inline children,
   while ``ParagraphNode.text()`` decides each gap from the source. Across the
   87 HTML fixtures 2,519 of 17,394 inline multi-child paragraphs had more
   words in markdown than in text, 139 after the fix (the rest are footnote
   markers in nested containers and tables nested inside paragraphs).
   Both now join from ``nodes.inline_runs``.

The fixture values below were read from the filings' own HTML:
- Goldman Sachs FY2024 10-K, 0000886982-25-000005, writes
  ``2024 ve</span><span ...>rsus 2023</span>``.
- American Express FY2024 10-K, 0000004962-25-000016, writes
  ``THE C</span><span ...>OMPANY </span>``.
"""

import pytest

from edgar.documents import HTMLParser, ParserConfig
from edgar.documents.nodes import HeadingNode, ParagraphNode
from edgar.documents.renderers.markdown import MarkdownRenderer
from tests.paths import FIXTURES_DIR


def _parse(html: str):
    return HTMLParser(ParserConfig()).parse(f"<html><body>{html}</body></html>")


def _paragraphs(doc, text):
    return [n for n in doc.root.walk() if isinstance(n, ParagraphNode) and n.text().strip() == text]


@pytest.mark.parametrize("html, expected", [
    ('<h2>ITEM 2. PROPERT<a name="item2">IES</a></h2>', "ITEM 2. PROPERTIES"),
    ("<h3>RI<span>SK</span> FACTORS</h3>", "RISK FACTORS"),
    # A gap that is in the source survives, at a tag boundary or inside a run.
    ("<h3><b>Item 1A.</b> <span>Risk Factors</span></h3>", "Item 1A. Risk Factors"),
    ("<h3><b>Item 7.</b><span> Management</span></h3>", "Item 7. Management"),
    # A line break or a block inside a heading still separates its words.
    ("<h2>ITEM 2.<br>PROPERTIES</h2>", "ITEM 2. PROPERTIES"),
    ("<h2><div>PART I</div><div>ITEM 1. BUSINESS</div></h2>", "PART I ITEM 1. BUSINESS"),
])
def test_heading_text_joins_runs_as_written(html, expected):
    headings = [n for n in _parse(html).root.walk() if isinstance(n, HeadingNode)]
    assert [h.text() for h in headings] == [expected]


def test_heading_markdown_keeps_the_word():
    md = MarkdownRenderer().render(_parse('<h2>ITEM 2. PROPERT<a name="item2">IES</a></h2>'))
    assert "# ITEM 2. PROPERTIES" in md, md


@pytest.mark.parametrize("path, text, markdown", [
    ("gs/10k/gs-10-k-2025-02-27.html", "2024 versus 2023", "**2024 versus 2023**"),
    ("axp/10k/axp-10-k-2025-02-07.html", "THE COMPANY", "**THE COMPANY **"),
])
def test_paragraph_markdown_matches_text_on_real_filings(path, text, markdown):
    html = (FIXTURES_DIR / "html" / path).read_text(encoding="utf-8")
    paragraphs = _paragraphs(HTMLParser(ParserConfig()).parse(html), text)
    assert paragraphs, f"{path}: no paragraph reads {text!r}"
    rendered = {MarkdownRenderer().render_node(p) for p in paragraphs}
    assert rendered == {markdown}, rendered


def test_paragraph_markdown_keeps_source_gaps():
    doc = _parse("<p>Revenue was <span>$394.3 billion</span> in <i>fiscal</i> 2024. <span>Net sales rose.</span></p>")
    md = MarkdownRenderer().render(doc).strip()
    plain = md.replace("\\", "").replace("*", "")
    assert plain.split() == "Revenue was $394.3 billion in fiscal 2024. Net sales rose.".split(), md
    # Gap for gap the same as the paragraph's text, whatever that text decides.
    assert plain == doc.root.text().strip(), md


def test_escaped_star_is_not_an_italic_closer():
    # A footnote star in plain text must not be merged into the italic run after it.
    doc = _parse("<p>Total revenue*<i>unaudited</i> for the period was $1 million.</p>")
    md = MarkdownRenderer().render(doc).strip()
    assert md.startswith("Total revenue\\**unaudited*"), md
