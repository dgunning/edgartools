"""Regression tests for document search snippet highlighting."""

from edgar.documents.document import Document
from edgar.documents.nodes import DocumentNode, ParagraphNode, TextNode
from edgar.documents.search import DocumentSearch, SearchMode


def _document_with_text(text: str) -> Document:
    root = DocumentNode()
    paragraph = ParagraphNode()
    paragraph.add_child(TextNode(content=text))
    root.add_child(paragraph)
    return Document(root=root)


def test_text_search_snippet_highlights_match_after_truncated_prefix():
    text = f"{'a' * 60} target {'b' * 60}"
    result = DocumentSearch(_document_with_text(text)).search("target")[0]

    assert result.context[result.start_offset:result.end_offset] == "target"
    assert "**target**" in result.snippet


def test_regex_search_snippet_highlights_match_after_truncated_prefix():
    text = f"{'a' * 60} target phrase {'b' * 60}"
    result = DocumentSearch(_document_with_text(text)).search(
        r"target\s+phrase",
        mode=SearchMode.REGEX,
    )[0]

    assert result.context[result.start_offset:result.end_offset] == "target phrase"
    assert "**target phrase**" in result.snippet
