"""
Regression test for Issue #844: SixK.text() raises TypeError on bytes exhibit content.

``Attachment.download()`` is typed ``str | bytes`` and returns bytes for some 6-K
exhibits. That value flowed into the legacy ``Document.parse`` ->
``HtmlDocument.get_root``, whose ``"<TEXT>" in html[:500]`` check raised
``TypeError: a bytes-like object is required, not 'str'`` instead of parsing.
The fix decoded bytes before those string checks, trying UTF-8, then
Windows-1252, then Latin-1, so legacy single-byte exhibits kept their accented
letters and curly quotes instead of turning into U+FFFD.

WHERE THE FIX LIVES NOW. 6.0 removed ``edgar.files``, and with it the function
the original tests here exercised. Worse, they had already stopped guarding the
reported path: ``SixK._get_exhibit_content`` had moved to
``parse_html(content).text()``, which decodes bytes as UTF-8 with replacement, so
a cp1252 6-K exhibit was mojibaked again while these tests stayed green. The rule
now lives once, in ``edgar.sgml.text_extraction.attachment_html_to_text`` (with
``decode_html_bytes``), and every exhibit/attachment text path calls it. It is
kept out of the shared ``html_to_text`` so ``FilingSGML.text()`` is unchanged;
the last test below pins that. The tests pin the rule and then each user-facing
path that must reach it.
No network access required.

GitHub Issue: https://github.com/dgunning/edgartools/issues/844
"""

import pytest

from edgar.attachments import Attachment
from edgar.company_reports.current_report import CurrentReport
from edgar.company_reports.sixk import SixK
from edgar.sgml.text_extraction import attachment_html_to_text, decode_html_bytes, html_to_text

pytestmark = pytest.mark.fast

INNER_HTML = "<html><body><p>Exhibit 99.1 content</p></body></html>"
SEC_WRAPPED = "<DOCUMENT>\n<TYPE>EX-99.1\n<TEXT>\n" + INNER_HTML + "\n</TEXT>\n</DOCUMENT>\n"
LEGACY_EXHIBIT = "<html><body><p>café résumé ’quoted’</p></body></html>"


class TestTheDecodingRule:

    @pytest.mark.parametrize("html", [INNER_HTML, SEC_WRAPPED], ids=["bare", "sgml-wrapped"])
    def test_bytes_and_str_render_the_same_text(self, html):
        assert attachment_html_to_text(html.encode("utf-8")) == "Exhibit 99.1 content"
        assert attachment_html_to_text(html) == "Exhibit 99.1 content"

    @pytest.mark.parametrize("encoding", ["cp1252", "latin-1"])
    def test_non_utf8_bytes_preserve_characters(self, encoding):
        html_bytes = "<html><body><p>café résumé</p></body></html>".encode(encoding)
        text = attachment_html_to_text(html_bytes)
        assert text == "café résumé"

    def test_windows_1252_curly_quotes_survive(self):
        """0x92 is a right single quote in cp1252 and a C1 control in Latin-1."""
        assert decode_html_bytes(LEGACY_EXHIBIT.encode("cp1252")) == LEGACY_EXHIBIT

    def test_undecodable_bytes_do_not_crash(self):
        """0x81 is invalid in UTF-8 and undefined in cp1252; Latin-1 carries it."""
        text = attachment_html_to_text(b"<html><body><p>\x81</p></body></html>")
        assert text == "\x81"


class _Exhibit:
    """The surface the report classes read off an exhibit attachment."""

    empty = False

    def __init__(self, content: bytes):
        self._content = content

    def download(self):
        return self._content


@pytest.mark.parametrize("report_class", [SixK, CurrentReport], ids=["SixK", "CurrentReport"])
def test_report_exhibit_text_decodes_legacy_bytes(report_class):
    """The path the issue was filed against: a bytes exhibit inside report.text()."""
    report = report_class.__new__(report_class)
    content = report._get_exhibit_content(_Exhibit(LEGACY_EXHIBIT.encode("cp1252")))
    assert content == "café résumé ’quoted’"


def test_attachment_text_decodes_legacy_bytes():
    attachment = Attachment(sequence_number="2", description="EX-99.1", document="ex99-1.htm",
                            ixbrl=False, path="/Archives/edgar/data/1/000000000000000001/ex99-1.htm",
                            document_type="EX-99.1", size=None)
    attachment.content = LEGACY_EXHIBIT.encode("cp1252")
    assert attachment.text() == "café résumé ’quoted’"


def test_the_shared_rule_is_left_alone():
    """``html_to_text`` (behind ``FilingSGML.text()``) does not unwrap envelopes.

    The decoding and unwrapping are an attachment concern. Folding them into the
    shared rule changed ``FilingSGML.text()``-path output on 11 of 313 fixture
    documents saved with their SGML envelope, so they live in the wrapper only.
    """
    assert html_to_text(SEC_WRAPPED) != "Exhibit 99.1 content"
    assert attachment_html_to_text(SEC_WRAPPED) == "Exhibit 99.1 content"
