"""
Regression test for Issue #844: SixK.text() raises TypeError on bytes exhibit content.

``Attachment.download()`` is typed ``str | bytes`` and returns bytes for some 6-K
exhibits. That value flows into ``Document.parse`` -> ``HtmlDocument.get_root``,
whose ``"<TEXT>" in html[:500]`` check raised
``TypeError: a bytes-like object is required, not 'str'`` instead of parsing.

The parser now decodes bytes before those string checks, so bytes and str inputs
behave identically. No network access required.
"""

import pytest

from edgar.files.html import Document
from edgar.files.html_documents import HtmlDocument

INNER_HTML = "<html><body><p>Exhibit 99.1 content</p></body></html>"
SEC_WRAPPED = "<DOCUMENT>\n<TYPE>EX-99.1\n<TEXT>\n" + INNER_HTML + "\n</TEXT>\n</DOCUMENT>\n"


class TestIssue844BytesExhibitContent:
    """Parsing must accept bytes HTML, matching Attachment.download()'s str|bytes return."""

    @pytest.mark.parametrize("html", [INNER_HTML, SEC_WRAPPED])
    def test_document_parse_accepts_bytes(self, html):
        """Document.parse must not raise TypeError on bytes input (GH #844)."""
        doc_bytes = Document.parse(html.encode("utf-8"))
        doc_str = Document.parse(html)
        assert doc_bytes is not None
        # bytes input parses equivalently to the already-decoded str input
        assert len(doc_bytes.nodes) == len(doc_str.nodes)

    def test_get_root_accepts_bytes(self):
        """HtmlDocument.get_root decodes bytes instead of raising at the crash site."""
        root = HtmlDocument.get_root(SEC_WRAPPED.encode("utf-8"))
        assert root is not None

    def test_non_utf8_bytes_do_not_crash(self):
        """Latin-1/cp1252 bytes degrade gracefully rather than raising."""
        latin1 = "<html><body><p>café résumé</p></body></html>".encode("latin-1")
        assert Document.parse(latin1) is not None
