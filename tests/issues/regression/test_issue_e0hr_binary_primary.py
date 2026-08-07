"""
Regression test for edgartools-e0hr: binary primary documents came back as mojibake.

Beads: edgartools-e0hr

Bug: UPLOAD filings (SEC comment letters) often carry a scanned PDF as the primary
document. FilingSGML.text() ran `content.decode('utf-8', 'replace')` over the PDF
bytes and returned a page of U+FFFD replacement characters that every caller
downstream treated as text. Filing.text() fell through to the raw <TEXT> body and
returned the uuencoded armor ('<PDF>\\nbegin 644 filename1.pdf\\nM)5!$1BTQ...').

CONTRACT CHOSEN BY THE FIX
--------------------------
For a binary primary document, FilingSGML.text() returns, in order of preference:

  1. the content of the SEC-provided TEXT-EXTRACT sibling, when the submission has
     one (this is the SEC's own plain-text rendering of the PDF); otherwise
  2. None.

None is the point. A PDF-only filing genuinely has no extractable text in the
submission, and "no text" is more useful than bytes wearing a text costume — callers
can branch on it, whereas mojibake silently poisons search, markdown and grep.

Filing.text() is deliberately unchanged: its UPLOAD behavior (TEXT-EXTRACT sibling
when present, otherwise the raw <TEXT> body — uuencoded armor for a PDF) is pinned
by test_correspondence and was one of the contracts the d216a934 revert restored.
Where a TEXT-EXTRACT sibling exists, the two paths agree.
"""

import pytest

from edgar import Filing

REPLACEMENT_CHAR = "�"

# PDF-only UPLOADs with NO TEXT-EXTRACT sibling -> text() is None.
TEAMSTAFF_UPLOAD = dict(
    form="UPLOAD",
    filing_date="2006-06-30",
    company="TEAMSTAFF INC",
    cik=785557,
    accession_no="0000000000-06-030726",
)
BRAVO_UPLOAD = dict(
    form="UPLOAD",
    filing_date="2006-07-20",
    company="BRAVO RESOURCE PARTNERS LTD",
    cik=1116137,
    accession_no="0000000000-06-033862",
)

# A PDF UPLOAD that DOES have a TEXT-EXTRACT sibling -> real text, both paths.
ANTELOPE_UPLOAD = dict(
    form="UPLOAD",
    filing_date="2024-03-01",
    company="Antelope Enterprise Holdings Ltd",
    cik=1470683,
    accession_no="0000000000-24-002373",
)


@pytest.mark.network
@pytest.mark.parametrize("filing_kwargs", [TEAMSTAFF_UPLOAD, BRAVO_UPLOAD],
                         ids=["teamstaff", "bravo"])
def test_pdf_only_upload_returns_none_not_mojibake(filing_kwargs):
    """No TEXT-EXTRACT sibling means no text - say so, do not invent bytes.

    Only FilingSGML.text() is asserted: Filing.text()'s UPLOAD behavior (raw
    <TEXT> body when there is no TEXT-EXTRACT sibling) is a pinned contract.
    """
    filing = Filing(**filing_kwargs)

    sgml_text = filing.sgml().text()

    assert sgml_text is None


@pytest.mark.network
@pytest.mark.parametrize("filing_kwargs", [TEAMSTAFF_UPLOAD, BRAVO_UPLOAD],
                         ids=["teamstaff", "bravo"])
def test_pdf_only_upload_never_returns_replacement_characters(filing_kwargs):
    """The specific symptom: a decoded PDF full of U+FFFD replacement characters."""
    filing = Filing(**filing_kwargs)

    text = filing.sgml().text()
    if text is not None:
        assert REPLACEMENT_CHAR not in text
        assert "%PDF" not in text
        assert "begin 644" not in text


@pytest.mark.network
def test_upload_with_text_extract_sibling_returns_real_text():
    """When the SEC ships a plain-text rendering, both paths use it."""
    filing = Filing(**ANTELOPE_UPLOAD)

    sgml_text = filing.sgml().text()
    filing_text = filing.text()

    assert sgml_text is not None
    assert REPLACEMENT_CHAR not in sgml_text
    assert "%PDF" not in sgml_text
    assert "Antelope Enterprise" in sgml_text
    assert "We have completed our review of your filing" in sgml_text
    # Filing.text() already used the sibling; FilingSGML.text() now agrees with it.
    assert sgml_text == filing_text


# --------------------------------------------------------------------------
# Network-free unit tests for the binary sniff
# --------------------------------------------------------------------------

class TestDecodeDocumentContent:

    def test_pdf_bytes_are_reported_as_binary(self):
        from edgar.sgml.text_extraction import decode_document_content

        pdf = b"%PDF-1.5\n%\xd0\xd4\xc5\xd8\n1 0 obj\n<</Length 365>>stream\n\x00\x01\x02"
        assert decode_document_content(pdf) is None

    def test_attachment_binary_flag_wins(self):
        from edgar.sgml.text_extraction import decode_document_content

        assert decode_document_content(b"looks like text", is_binary=True) is None
        assert decode_document_content("looks like text", is_binary=True) is None

    def test_utf8_text_bytes_decode(self):
        from edgar.sgml.text_extraction import decode_document_content

        assert decode_document_content(b"hello \xc2\xa9 world") == "hello © world"

    def test_undecodable_bytes_are_binary_not_lossy(self):
        from edgar.sgml.text_extraction import decode_document_content

        assert decode_document_content(b"\xff\xfe\xfd\xfc") is None

    def test_none_content(self):
        from edgar.sgml.text_extraction import decode_document_content

        assert decode_document_content(None) is None


class TestPrimaryDocumentTextBinaryHandling:

    def test_binary_without_text_extract_returns_none(self):
        from edgar.sgml.text_extraction import primary_document_text

        assert primary_document_text("UPLOAD", b"%PDF-1.5\n\x00\x01", is_binary=True) is None

    def test_binary_with_text_extract_returns_the_sibling(self):
        from edgar.sgml.text_extraction import primary_document_text

        result = primary_document_text(
            "UPLOAD", b"%PDF-1.5\n\x00\x01", is_binary=True,
            text_extract=lambda: "Dear Registrant: we have comments.",
        )
        assert result == "Dear Registrant: we have comments."

    def test_text_extract_is_not_consulted_for_text_primaries(self):
        from edgar.sgml.text_extraction import primary_document_text

        def boom():
            raise AssertionError("text_extract must only be used for binary primaries")

        assert primary_document_text("CORRESP", "plain letter", text_extract=boom) == "plain letter"

    def test_empty_content_returns_none(self):
        from edgar.sgml.text_extraction import primary_document_text

        assert primary_document_text("10-K", "") is None
        assert primary_document_text("10-K", "   \n  ") is None
        assert primary_document_text("10-K", None) is None
