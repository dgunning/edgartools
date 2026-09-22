"""libxml2 silently discards everything nested deeper than 256 elements.

No exception, nothing in the parser's error log -- just a shorter document.
`create_lxml_parser` passes `huge_tree=True` to lift the limit; these tests
fail without it.

This is not a hypothetical. 2000s-era filings nest layout tables that deep,
and BeautifulSoup never behaved this way with either treebuilder: html.parser
has no depth limit at all, and bs4's own lxml treebuilder passes huge_tree.
So every reader moved from bs4 to lxml would have become quietly lossy on
those filings.
"""
import lxml.html
import pytest

from edgar.documents import HTMLParser, ParserConfig
from edgar.documents.utils.html_utils import create_lxml_parser

pytestmark = pytest.mark.fast


def _nested(depth: int, marker: str = "DEEPMARKER") -> str:
    return ("<div>" * depth) + marker + ("</div>" * depth)


@pytest.mark.parametrize("depth", [250, 260, 500, 1000])
def test_text_below_the_libxml2_depth_limit_survives(depth):
    """256 is the limit. 250 passed before the fix; 260 did not."""
    root = lxml.html.fromstring(_nested(depth).encode(), parser=create_lxml_parser())
    assert "DEEPMARKER" in root.text_content()


def test_the_limit_is_real_when_it_is_not_lifted():
    """Pin the behaviour being defended against, so this file still means
    something if the default ever changes back."""
    parser = lxml.html.HTMLParser(recover=True, encoding="utf-8", huge_tree=False)
    root = lxml.html.fromstring(_nested(260).encode(), parser=parser)
    assert "DEEPMARKER" not in root.text_content()
    # And note the silence: recovery reports nothing.
    assert not [e for e in parser.error_log if "DEEPMARKER" in str(e)]


def test_the_document_pipeline_keeps_deeply_nested_text():
    """The end that matters: filing.text() runs through this parser."""
    html = f"<html><body><p>Alpha</p>{_nested(300)}<p>Omega</p></body></html>"
    text = HTMLParser(ParserConfig()).parse(html).text()
    assert "DEEPMARKER" in text
    assert "Alpha" in text and "Omega" in text
