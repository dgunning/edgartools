"""
Regression test for edgartools-j8bs: an unterminated HTML comment emptied the document.

Beads: edgartools-j8bs

Bug: 1990s and early-2000s filings sometimes open with a comment that is never closed:

    <!--DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 3.2//EN">     (a typo for <!DOCTYPE)
    <!-- HTML (c)2001 Some Author, email:someone@example.com  (just never closed)

lxml treats the unterminated "<!--" as running to end of input, so the whole document
becomes one comment and the parse tree is empty. edgar/documents/parser.py then raised
HTMLParsingError("Document is empty"). FilingSGML.text() propagated that exception;
Filing.text() "survived" only because a different bug routed it around the parser, and
it returned raw HTML markup — tags and all — from the filing's <TEXT> body.

Fix: terminate_unclosed_comments() closes an unterminated comment at the end of its
line (the authoring intent in both shapes above) before lxml sees it. Comments that
are already closed are untouched. This sits below both APIs, so any path that reaches
the HTML parser is fixed (both paths for the Autoliv filing below).

KNOWN LIMITATION — Filing.text() on <FILENAME>-less filings (the Northrop filing
below) never reaches the parser: Filing.html() returns None for them and text() falls
through to the raw <TEXT> body, still returning markup. The fix for that is the
Attachment.empty change reverted in d216a934, so it stays out of scope; use
FilingSGML.text() for those filings.

Ground truth verified by hand against the filings themselves.
"""

import pytest

from edgar import Filing
from edgar.documents.utils.html_utils import terminate_unclosed_comments

# Northrop Grumman Form 15, 1999. Primary document begins with the <!--DOCTYPE typo
# and has no <FILENAME>. Before the fix: FilingSGML.text() raised, Filing.text()
# returned raw markup starting '<!--DOCTYPE HTML PUBLIC ...'.
NORTHROP_FORM15 = dict(
    form="15-12B",
    filing_date="1999-09-30",
    company="NORTHROP GRUMMAN CORP",
    cik=72945,
    accession_no="0000889810-99-000271",
)

# Autoliv revised proxy, 2001. Has a valid <!DOCTYPE followed by an unterminated
# comment. Before the fix BOTH paths raised HTMLParsingError.
AUTOLIV_PROXY = dict(
    form="DEFR14A",
    filing_date="2001-03-30",
    company="AUTOLIV INC",
    cik=1034670,
    accession_no="0001034670-01-500017",
)


# --------------------------------------------------------------------------
# Network tests against the real filings
# --------------------------------------------------------------------------

@pytest.mark.network
def test_northrop_sgml_text_renders_instead_of_raising():
    filing = Filing(**NORTHROP_FORM15)
    text = filing.sgml().text()

    assert text is not None
    assert "FORM 15" in text
    assert "NORTHROP GRUMMAN CORPORATION" in text
    assert "Certification and Notice of Termination of Registration" in text


@pytest.mark.network
@pytest.mark.xfail(
    reason="Known limitation: this filing's primary document has no <FILENAME>, so "
    "Filing.html() returns None (Attachment.empty means 'no FILENAME tag') and "
    "Filing.text() falls through to the raw <TEXT> body without ever reaching the "
    "hardened HTML parser. Fixing it requires the Attachment.empty change that was "
    "reverted in d216a934. FilingSGML.text() is the reliable path for these filings.",
    strict=False,
)
def test_northrop_filing_text_is_not_raw_markup():
    """Filing.text() would ideally render this instead of handing back HTML source."""
    filing = Filing(**NORTHROP_FORM15)
    text = filing.text()

    assert text is not None
    assert "<!--DOCTYPE" not in text
    assert "<html" not in text.lower()
    assert "FORM 15" in text


@pytest.mark.network
def test_autoliv_both_paths_return_text_without_raising():
    """Before the fix both paths raised HTMLParsingError('Document is empty')."""
    filing = Filing(**AUTOLIV_PROXY)

    sgml_text = filing.sgml().text()
    filing_text = filing.text()

    for text in (sgml_text, filing_text):
        assert text is not None
        assert "DEAR STOCKHOLDER" in text
        assert "Autoliv" in text
        assert "2001 Annual Meeting of Stockholders" in text
    assert sgml_text == filing_text


# --------------------------------------------------------------------------
# Network-free unit tests for the comment neutralisation itself
# --------------------------------------------------------------------------

class TestTerminateUnclosedComments:

    def test_unterminated_doctype_typo_is_closed(self):
        html = '<!--DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 3.2//EN">\n<HTML><BODY>hi</BODY></HTML>'
        fixed = terminate_unclosed_comments(html)

        assert fixed.count("-->") == 1
        assert fixed.startswith('<!--DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 3.2//EN">-->')
        assert "<HTML><BODY>hi</BODY></HTML>" in fixed

    def test_unterminated_comment_is_closed_at_end_of_line(self):
        html = "<!DOCTYPE HTML>\n<!-- a note that never closes\n<html><body>hi</body></html>"
        fixed = terminate_unclosed_comments(html)

        assert "<!-- a note that never closes-->" in fixed
        assert "<html><body>hi</body></html>" in fixed

    def test_terminated_comment_is_untouched(self):
        html = "<!-- a normal comment --><p>hi</p>"
        assert terminate_unclosed_comments(html) == html

    def test_document_without_comments_is_untouched(self):
        html = "<html><body><p>hi</p></body></html>"
        assert terminate_unclosed_comments(html) == html

    def test_multiple_terminated_comments_are_untouched(self):
        html = "<!-- one --><p>a</p><!-- two --><p>b</p>"
        assert terminate_unclosed_comments(html) == html

    def test_terminated_and_unterminated_together(self):
        html = "<!-- fine --><p>a</p>\n<!-- broken\n<p>b</p>"
        fixed = terminate_unclosed_comments(html)

        assert "<!-- fine -->" in fixed
        assert "<!-- broken-->" in fixed
        assert "<p>b</p>" in fixed

    def test_unterminated_comment_with_no_newline(self):
        html = "<p>a</p><!-- trailing"
        assert terminate_unclosed_comments(html) == "<p>a</p><!-- trailing-->"

    def test_two_unterminated_comments_are_both_closed(self):
        """Scanning must continue past the first repair - a document can contain
        more than one stray comment."""
        html = "<!-- first stray\n<p>a</p>\n<!-- second stray\n<p>b</p>"
        fixed = terminate_unclosed_comments(html)

        assert "<!-- first stray-->" in fixed
        assert "<!-- second stray-->" in fixed
        assert "<p>a</p>" in fixed
        assert "<p>b</p>" in fixed


class TestHtmlToTextDegradesRatherThanRaising:
    """The shared renderer's contract when the parser cannot cope at all."""

    def test_parse_failure_falls_back_to_stripped_text(self, monkeypatch):
        from edgar.documents.exceptions import HTMLParsingError
        from edgar.sgml import text_extraction

        def explode(self, html):
            raise HTMLParsingError("Document is empty", context={})

        monkeypatch.setattr("edgar.documents.HTMLParser.parse", explode)

        result = text_extraction.html_to_text("<html><body><p>rescued text</p></body></html>")

        assert "rescued text" in result
        assert "<p>" not in result
        assert "<html" not in result

    def test_document_too_large_still_propagates(self, monkeypatch):
        """A size guard is not a malformed document; it must not be swallowed."""
        from edgar.documents.exceptions import DocumentTooLargeError
        from edgar.sgml import text_extraction

        def too_large(self, html):
            raise DocumentTooLargeError(10, 5)

        monkeypatch.setattr("edgar.documents.HTMLParser.parse", too_large)

        with pytest.raises(DocumentTooLargeError):
            text_extraction.html_to_text("<html><body>x</body></html>")

    def test_strip_html_tags_drops_scripts_and_unescapes(self):
        from edgar.sgml.text_extraction import strip_html_tags

        html = "<html><script>var x = 1;</script><p>A &amp; B</p></html>"
        result = strip_html_tags(html)

        assert "A & B" in result
        assert "var x" not in result
        assert "<" not in result


class TestParserSurvivesUnterminatedComments:
    """The parser must produce a real document, not raise 'Document is empty'."""

    def _parse(self, html):
        from edgar.documents import HTMLParser, ParserConfig
        return HTMLParser(ParserConfig()).parse(html)

    def test_doctype_typo_document_parses(self):
        html = (
            '<!--DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 3.2//EN">\n'
            "<HTML><HEAD><TITLE>Form 15</TITLE></HEAD>"
            "<BODY><P>Certification and Notice of Termination</P></BODY></HTML>"
        )
        document = self._parse(html)

        assert not document.is_empty
        assert "Certification and Notice of Termination" in document.text()

    def test_normal_comment_still_removed_from_output(self):
        html = "<html><body><!-- hidden note --><p>visible</p></body></html>"
        document = self._parse(html)

        assert "visible" in document.text()
        assert "hidden note" not in document.text()

    def test_document_with_both_comment_kinds_parses(self):
        html = (
            "<!DOCTYPE HTML>\n"
            "<!-- unclosed banner comment\n"
            "<html><body><!-- closed note --><p>content survives</p></body></html>"
        )
        document = self._parse(html)

        assert not document.is_empty
        assert "content survives" in document.text()
        assert "closed note" not in document.text()
        assert "unclosed banner comment" not in document.text()
