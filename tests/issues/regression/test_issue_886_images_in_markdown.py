"""
Regression test for GitHub Issue #886:
Images (<img>) in filing HTML were silently dropped from the new parser's
markdown and text output.

Two root causes in the edgar.documents pipeline:
1. The postprocessor's _is_empty_node() treated any childless node with no text
   `content` as empty, so ImageNode (which carries src/alt but no children) was
   pruned from the tree before rendering.
2. The markdown renderer had no IMAGE branch, so even a surviving ImageNode
   emitted nothing.

Fix:
- postprocessor.py: never remove NodeType.IMAGE nodes.
- renderers/markdown.py: render ImageNode as `![alt](url)`, resolving a relative
  src against document.metadata.url when known.
- extractors/text_extractor.py: optional `include_images` placeholder
  (`[Image: ...]`, default off so clean text is unchanged).

These tests use a small synthetic document (no network) plus a live NVDA 10-K
ground-truth check.
"""
import pytest

from edgar.documents import HTMLParser, ParserConfig
from edgar.documents.extractors.text_extractor import TextExtractor
from edgar.documents.renderers.markdown import MarkdownRenderer

_IMG_HTML = (
    "<html><body>"
    "<p>The following graph compares the cumulative total shareholder return.</p>"
    '<img src="nvda-20260125_g2.jpg" alt="562" style="height:426px;width:684px" id="i-2"/>'
    "<p>$100 invested on 1/31/2021.</p>"
    "</body></html>"
)


def _parse():
    return HTMLParser(ParserConfig(form="10-K")).parse(_IMG_HTML)


def test_image_survives_postprocessing_and_renders_in_markdown():
    """The image must not be pruned, and must render as a markdown image with
    the raw relative src when no base URL is known."""
    doc = _parse()
    md = doc.to_markdown()
    assert "![562](nvda-20260125_g2.jpg)" in md


def test_markdown_resolves_relative_src_against_document_url():
    """When the source document URL is known, the relative src resolves to an
    absolute SEC-archive link so the markdown is self-contained."""
    doc = _parse()
    doc.metadata.url = (
        "https://www.sec.gov/Archives/edgar/data/1045810/000104581026000021/nvda-20260125.htm"
    )
    md = MarkdownRenderer().render(doc)
    assert (
        "![562](https://www.sec.gov/Archives/edgar/data/1045810/"
        "000104581026000021/nvda-20260125_g2.jpg)" in md
    )


def test_text_is_clean_by_default_but_opt_in_placeholder_works():
    """Default .text() stays image-free (no stray alt text); opt-in emits a
    placeholder."""
    doc = _parse()
    default_text = doc.text()
    assert "562" not in default_text  # alt text must not leak into clean text

    with_images = TextExtractor(include_images=True).extract(doc)
    assert "[Image: 562]" in with_images


def test_document_without_images_is_unchanged():
    """Silence/no-regression: a document with no images renders normally."""
    doc = HTMLParser(ParserConfig(form="10-K")).parse(
        "<html><body><p>Just text, no images here.</p></body></html>"
    )
    md = doc.to_markdown()
    # (the renderer escapes '.' to '\.', so match without the trailing period)
    assert "Just text, no images here" in md
    assert "![" not in md


@pytest.mark.network
@pytest.mark.regression
def test_nvda_10k_stock_performance_graph_in_markdown():
    """Ground truth: NVIDIA FY2026 10-K stock-performance graph image appears in
    Document.to_markdown() from the new parser."""
    from edgar import Company

    filing = Company("NVDA").get_filings(form="10-K", amendments=False)[0]
    doc = HTMLParser(ParserConfig(form="10-K")).parse(filing.html())
    md = doc.to_markdown()
    assert "nvda-20260125_g2" in md
