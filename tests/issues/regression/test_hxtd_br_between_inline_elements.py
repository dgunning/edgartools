"""A ``<br>`` between two inline elements keeps its line break (edgartools-hxtd).

The 6-K/8-K cover page is written as one paragraph of bold lines separated by
``<br>``::

    <p><strong>UNITED STATES</strong><br/>
       <strong>SECURITIES AND EXCHANGE COMMISSION</strong><br/>
       <strong>Washington, D.C. 20549</strong></p>

``Document.text()`` used to return ``UNITED STATESSECURITIES AND EXCHANGE
COMMISSIONWashington, D.C. 20549`` -- the break dropped and the words either
side glued. ``<br>`` between *bare text* always worked; it was specifically
``<br>`` between inline ELEMENTS that was lost.

CAUSE, and why it took a walk of the tree to find. ``DocumentBuilder`` does
create the node (``elif tag == 'br': TextNode(content='\\n')``) and does attach
it -- tracing ``add_child`` shows it arriving on the ParagraphNode. It is
``DocumentPostprocessor._remove_empty_nodes`` that takes it away afterwards:
``_is_empty_node`` asks ``not node.text().strip()``, and a newline strips to
nothing, so the one node whose entire meaning IS whitespace was read as empty.
The node is now marked ``is_line_break`` at construction and exempted by name,
in the same style as the TABLE and IMAGE exemptions beside it -- the latter
added after empty-node pruning silently dropped images (GH #886), which is the
same bug in a different costume.

WHY IT MATTERED BEYOND ITS SIZE. ``edgar.files.html.Document`` was the only
implementation that got this right -- ``edgar.files.html_documents.HtmlDocument``
and ``edgar.documents`` both glued -- so until this was fixed, deleting
``edgar/files`` would have removed the correct behaviour and left the broken one
on the cover page of a great many filings. It blocked edgartools-07lk.3.

Found in the edgartools-3dp Group A comparison, on 6-K 0001171843-25-004208.
"""
import pytest

from edgar.documents import parse_html

pytestmark = pytest.mark.fast


COVER_PAGE = (
    '<p><strong>UNITED STATES</strong><br/>'
    '<strong>SECURITIES AND EXCHANGE COMMISSION</strong><br/>'
    '<strong>Washington, D.C. 20549</strong></p>'
)


@pytest.mark.parametrize("inline_tag", ["strong", "span", "b", "em", "font"])
def test_a_break_between_inline_elements_survives(inline_tag):
    html = (f'<p><{inline_tag}>UNITED STATES</{inline_tag}><br/>'
            f'<{inline_tag}>SECURITIES AND EXCHANGE COMMISSION</{inline_tag}></p>')
    assert parse_html(html).text().strip() == "UNITED STATES\nSECURITIES AND EXCHANGE COMMISSION"


def test_the_cover_page_shape_reads_as_three_lines():
    """The thing that actually broke, rather than its reduction."""
    lines = [ln for ln in parse_html(COVER_PAGE).text().strip().split("\n") if ln.strip()]
    assert lines == ["UNITED STATES",
                     "SECURITIES AND EXCHANGE COMMISSION",
                     "Washington, D.C. 20549"]


def test_words_either_side_are_never_glued():
    """States the symptom directly — the failure was a missing separator, and an
    equality test alone could be satisfied by some other rendering."""
    text = parse_html(COVER_PAGE).text()
    assert "STATESSECURITIES" not in text
    assert "COMMISSIONWashington" not in text


def test_a_break_between_bare_text_still_works():
    """This path was always correct; it shares the node type that was fixed."""
    html = '<p>UNITED STATES<br/>SECURITIES AND EXCHANGE COMMISSION</p>'
    assert parse_html(html).text().strip() == "UNITED STATES\nSECURITIES AND EXCHANGE COMMISSION"


def test_a_break_inside_a_div_survives_too():
    html = '<div><strong>A</strong><br/><strong>B</strong></div>'
    assert parse_html(html).text().strip() == "A\nB"


def test_consecutive_breaks_are_both_kept():
    """Two <br> is how filers write a blank line; collapsing them to one would be
    a quieter version of the same bug."""
    assert parse_html('<p><strong>A</strong><br/><br/><strong>B</strong></p>').text().strip() == "A\n\nB"


def test_incidental_whitespace_is_still_pruned():
    """The exemption is for <br> only. Whitespace between tags carries no meaning
    and must not start surviving as blank lines, or every document grows them."""
    text = parse_html('<div>  <p>A</p>   <p>B</p>  </div>').text()
    assert "\n\n\n" not in text
    assert [ln for ln in text.split("\n") if ln.strip()] == ["A", "B"]
