"""
Regression test for Issue #898: text after inline-XBRL facts is silently dropped.

GitHub Issue: https://github.com/dgunning/edgartools/issues/898

Bug (FIXED): the document parser's ``_get_element_text()`` collected each child's
``text_content()`` but never its ``.tail``. For inline containers this dropped the
text between an inline fact's closing tag and the next element - the unit word and
the rest of the sentence. So "$95.2 billion, of which ... paid" rendered as
"$ 95.2": the scale word "billion" and the trailing clause vanished, leaving a bare
number that reads as 95.2 rather than 95.2 billion. Multi-fact sentences collapsed
into number runs.

Fix: read ``child.tail`` in ``_get_element_text``
(``edgar/documents/strategies/document_builder.py``) so trailing text is preserved.

Note: inter-token spacing (e.g. "$ 95.2" vs "$95.2") is governed by a separate,
pre-existing whitespace-normalization step and is out of scope here. These tests
assert that the previously-dropped text is present, not exact spacing. All are
network-free.
"""
from edgar.documents import HTMLParser, ParserConfig
from edgar.richtools import rich_to_text

IX = "http://www.xbrl.org/2013/inlineXBRL"


def _render(html: str) -> str:
    doc = HTMLParser(ParserConfig(form="10-K")).parse(html)
    return rich_to_text(doc, width=500)


def test_text_after_inline_fact_is_preserved():
    html = (
        f'<html xmlns:ix="{IX}"><body><div><span>'
        'commitments were $<ix:nonfraction name="us-gaap:OtherCommitment" '
        'contextref="c-1" scale="9">95.2</ix:nonfraction>'
        " billion, of which substantially all will be paid."
        "</span></div></body></html>"
    )
    text = _render(html)
    # The tagged value survives ...
    assert "95.2" in text
    # ... and so do the scale word and trailing clause that used to vanish.
    assert "billion" in text
    assert "of which substantially all will be paid" in text


def test_multiple_inline_facts_do_not_collapse_to_a_number_run():
    html = (
        f'<html xmlns:ix="{IX}"><body><div><span>'
        'total was $<ix:nonfraction name="a" contextref="c" scale="9">27</ix:nonfraction>'
        ' billion, of which $<ix:nonfraction name="b" contextref="c" scale="9">7</ix:nonfraction>'
        " billion will be paid."
        "</span></div></body></html>"
    )
    text = _render(html)
    # Both scale words survive instead of collapsing into "$ 27 7".
    assert text.count("billion") == 2
    assert "will be paid" in text


def test_text_after_a_skipped_child_is_preserved():
    # Text following an ix:exclude (a skipped child) is still document text and
    # must survive, while the excluded content itself is dropped.
    html = (
        f'<html xmlns:ix="{IX}"><body><div><span>'
        "keep this<ix:exclude>drop this</ix:exclude> and keep this too."
        "</span></div></body></html>"
    )
    text = _render(html)
    assert "keep this" in text
    assert "and keep this too" in text
    assert "drop this" not in text
