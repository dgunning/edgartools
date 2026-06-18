"""Regression test for #860: search snippet offsets should be adjusted for context.

When _get_context truncates text and adds ellipsis markers, the SearchResult
start_offset and end_offset must reflect positions within the returned context
string, not the original text. Otherwise SearchResult.snippet highlights the
wrong characters.
"""

from edgar.documents.search import DocumentSearch


def test_get_context_with_offsets_adjusts_for_truncation():
    """Offsets should be adjusted when context is truncated."""
    ds = DocumentSearch.__new__(DocumentSearch)

    # Text with match far from start and end, so context is truncated both sides
    text = "x" * 200 + "THE_MATCH" + "y" * 200
    pos = 200  # start of THE_MATCH
    context, start, end = ds._get_context_with_offsets(text, pos, pos + 9, 10)

    # The adjusted offsets should point to THE_MATCH within context
    assert context[start:end] == "THE_MATCH"
    # The original offset would be wrong (pointing outside context)
    assert start != pos


def test_get_context_with_offsets_no_truncation():
    """Offsets should be unchanged when context is not truncated."""
    ds = DocumentSearch.__new__(DocumentSearch)

    text = "hello world this is a test"
    pos = 6
    context, start, end = ds._get_context_with_offsets(text, pos, pos + 5, 10)

    assert context[start:end] == "world"
    # No truncation, offsets unchanged
    assert start == pos
    assert end == pos + 5


def test_backward_compatible_get_context():
    """Existing _get_context should still return just the string."""
    ds = DocumentSearch.__new__(DocumentSearch)

    text = "x" * 100 + "match" + "y" * 100
    result = ds._get_context(text, 100, 105, 10)

    assert isinstance(result, str)
    assert "match" in result
    assert result.startswith("...")
    assert result.endswith("...")
