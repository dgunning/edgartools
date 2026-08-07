"""Regression test for edgartools-fi4h: table-search snippet over-highlight.

The semantic ``table:<term>`` search path built a SearchResult with
``start_offset=0`` and ``end_offset=len(table_text)`` against a context
truncated to ~200 chars. ``SearchResult.snippet`` highlights
``context[start_offset:end_offset]``, so for any table longer than 200 chars the
out-of-range end made it wrap the *entire* truncated context in ``** **`` rather
than the matched term.

The fix locates the match within the table text and produces a context window
with offsets relative to that window (same mechanism as text/regex search).

Discovered while reviewing PRs #862 / #860 (the text/regex offset fix), which
did not touch the table path.
"""

from edgar.documents import parse_html
from edgar.documents.nodes import NodeType
from edgar.documents.search import DocumentSearch, SearchMode


def _doc_with_long_table(target: str = "REVENUE"):
    """A table whose text() exceeds 200 chars, with `target` appearing late."""
    cells = "".join(
        f"<tr><td>filler cell {i} with several words here</td></tr>" for i in range(20)
    )
    html = (
        f"<html><body><table>{cells}"
        f"<tr><td>{target} total 12345</td></tr></table></body></html>"
    )
    return parse_html(html)


def test_table_snippet_highlights_match_not_whole_table():
    doc = _doc_with_long_table()
    tables = [n for n in doc.root.walk() if n.type == NodeType.TABLE]
    assert len(tables[0].text()) > 200  # precondition: context would be truncated

    result = DocumentSearch(doc).search("table:REVENUE", mode=SearchMode.SEMANTIC)[0]

    # Offsets stay inside the context (the over-highlight bug ran end_offset past it).
    assert result.end_offset <= len(result.context)
    # The highlighted span is the matched term, not the entire table.
    assert result.context[result.start_offset:result.end_offset].lower() == "revenue"
    assert "**REVENUE**" in result.snippet
    # And the snippet does not wrap the whole context.
    assert not result.snippet.startswith("**...")


def test_table_search_no_match_returns_no_result():
    doc = _doc_with_long_table()

    results = DocumentSearch(doc).search("table:NONEXISTENT", mode=SearchMode.SEMANTIC)

    assert results == []
