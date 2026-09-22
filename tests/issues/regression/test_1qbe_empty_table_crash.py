"""A note holding a table with no usable rows crashed markdown rendering.

edgartools-1qbe.

`html_to_json()` documents its first return value as a list of text blocks, but
three early returns handed back `None` -- when the table has no `<tr>` at all,
when every row is filtered out as a width-grid layout row, and when the rows
carry no cells. `process_content()` iterates that value unconditionally, so the
whole note raised `TypeError: 'NoneType' object is not iterable`.

It is reachable from the RAG surface: `edgar/xbrl/notes.py` calls
`process_content` for `note.to_context()` and `notes.to_markdown()` whenever
`optimize_for_llm` is set, so one empty table in a filer's TextBlock took the
entire note down rather than degrading to the prose around it.

The fix is at the source rather than at the call site. `html_to_json` is in
`edgar.markdown.__all__`, so any caller iterating its documented list hit the
same crash; guarding only `process_content` would have left that standing and
masked a regression here.
"""
import pytest

from edgar.markdown import html_to_json, process_content

pytestmark = pytest.mark.fast

_LAYOUT_ROW = "<tr>" + "".join("<td style='width:10px'></td>" for _ in range(8)) + "</tr>"

# Every one of these raised TypeError before the fix.
NO_USABLE_ROWS = {
    "table-with-no-rows": "<table></table>",
    "table-with-only-a-tbody": "<table><tbody></tbody></table>",
    "table-with-cells-but-no-row": "<table><td>x</td></table>",
    "table-of-only-layout-rows": f"<table>{_LAYOUT_ROW}</table>",
}


@pytest.mark.parametrize("name", list(NO_USABLE_ROWS))
def test_process_content_survives_a_table_with_no_usable_rows(name):
    """The prose around the table must still render."""
    html = f"<p>The Company had no material commitments.</p>{NO_USABLE_ROWS[name]}"
    md = process_content(html)
    assert "The Company had no material commitments." in md, (
        f"{name}: the surrounding prose was lost"
    )


def test_prose_that_merely_mentions_a_table_tag_does_not_raise():
    """`is_html` matches on the string `<table`, so plain prose takes the HTML path.

    It no longer raises, which is what 1qbe was. It returns `""` rather than the
    sentence, because `html.parser` reads the `<table>` as an open tag and
    swallows everything after it -- a separate deficiency in the `is_html`
    heuristic, and NOT fixed here. It is close to unreachable in production:
    an XBRL TextBlock carrying that sentence would have escaped the angle
    brackets as `&lt;table&gt;`. Asserted as-is so that if the heuristic is ever
    tightened, this test says so rather than quietly agreeing.
    """
    assert process_content("See the <table> of contents for details.") == ""


@pytest.mark.parametrize("name", list(NO_USABLE_ROWS))
def test_html_to_json_returns_a_list_not_none(name):
    """The documented contract: text_blocks is a list, so callers can iterate it."""
    import lxml.html

    table = lxml.html.fromstring(NO_USABLE_ROWS[name]).find(".//table")
    if table is None:  # a single-element fragment is rooted AT the table
        table = lxml.html.fromstring(NO_USABLE_ROWS[name])
    text_blocks, records, derived_title = html_to_json(table)
    assert text_blocks == [], f"{name}: expected an empty list, got {text_blocks!r}"
    assert records == []
    assert derived_title is None
    # The point of the fix: this must not raise.
    assert [b for b in text_blocks] == []


def test_a_real_table_still_renders():
    """The fix must not quiet a table that does have rows."""
    md = process_content(
        "<table><tr><th>Item</th><th>2024</th></tr>"
        "<tr><td>Revenue</td><td>$1,000</td></tr></table>"
    )
    assert "Revenue" in md and "1,000" in md
