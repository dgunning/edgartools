"""
Regression test for edgartools-0rvh: plain-text extraction from historic
pre-HTML SGML filings must work from the locally-parsed SGML, without network.

Root cause: historic SGML documents (e.g. 1995) often have no <FILENAME>. Two
filename-keyed code paths broke as a result:

1. ``Attachment.empty`` only inspected the (missing) filename, so the primary
   document reported ``empty=True`` even though its content was available via
   the parsed ``sgml_document``.
2. ``FilingSGML.html()`` fetched content via ``get_content(filename)``; with an
   empty filename every document keyed to ``''`` and collided, returning the
   wrong document.

The combined effect was that ``FilingSGML.html()`` returned ``None``, sending
``Filing.html()``/``Filing.text()`` to a network fallback — so plain-text
extraction was impossible offline (reported by M. Gruening, TU Ilmenau).

These assertions run purely off a local fixture: no network, no cassette.
"""

import pytest

from edgar.sgml import FilingSGML

# Real filing from the report: COMMON SENSE TRUST 24F-2NT, filed 1995-12-28.
# A text-only, pre-HTML SGML submission whose documents have no <FILENAME>.
FIXTURE = "data/sgml/0000950129-95-001652.txt"


@pytest.fixture(scope="module")
def sgml():
    return FilingSGML.from_source(FIXTURE)


def test_header_parses(sgml):
    assert sgml.accession_number == "0000950129-95-001652"
    assert sgml.form == "24F-2NT"
    assert sgml.cik == 810271


def test_filenameless_primary_document_is_not_empty(sgml):
    """Regression: a <FILENAME>-less document with real content is not 'empty'."""
    primary = sgml.attachments.primary_documents
    assert len(primary) == 1
    doc = primary[0]
    assert doc.document == ""          # the historic submission has no <FILENAME>
    assert doc.empty is False          # ...but it is NOT empty — content is present
    assert "FORM 24F-2" in doc.content


def test_html_returns_correct_primary_document(sgml):
    """Regression: html() must return the primary form, not a colliding sibling doc.

    Before the fix, get_content('') resolved to the wrong filenameless document
    (the cover letter) instead of the sequence-1 primary form.
    """
    html = sgml.html()
    assert html is not None
    assert "FORM 24F-2" in html
    assert "ANNUAL NOTICE OF SECURITIES SOLD" in html


def test_plain_text_extractable_offline(sgml):
    """The document body is reachable without any network call."""
    content = sgml.attachments.get_by_sequence(1).content
    assert "FORM 24F-2" in content
    # The full form body, not the shorter cover-letter sibling.
    assert len(content) > 5000


def test_filing_sgml_text_convenience(sgml):
    """FilingSGML.text() returns the primary document as plain text, page markers removed."""
    text = sgml.text()
    assert text is not None
    assert "FORM 24F-2" in text
    assert "<PAGE>" not in text          # SGML page-break markers stripped
    assert len(text) > 5000              # the full form, not the cover-letter sibling
    # Fixed-width layout is preserved (not reflowed).
    assert any(line.startswith("     ") for line in text.splitlines())


def test_filing_text_is_verbatim_and_offline(monkeypatch, tmp_path):
    """Filing.text() returns the primary document verbatim, from local storage, no network."""
    from edgar import Filing, use_local_storage

    # Stage the fixture in the FILED AS OF DATE folder (how local storage keys lookups).
    day_dir = tmp_path / "filings" / "19951228"
    day_dir.mkdir(parents=True)
    (day_dir / "0000950129-95-001652.nc").write_bytes(open(FIXTURE, "rb").read())

    use_local_storage(str(tmp_path), use_local=True, allow_network_fallback=False)
    try:
        # Force any accidental network call to fail loudly.
        monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9")
        monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:9")
        filing = Filing(cik=810271, accession_no="0000950129-95-001652", form="24F-2NT",
                        company="COMMON SENSE TRUST", filing_date="1995-12-28")
        text = filing.text()
        assert "FORM 24F-2" in text
        assert "<PAGE>" not in text
        # Verbatim (fixed-width) output, not the narrower HTML-reflowed rendering.
        assert any(line.startswith("     ") for line in text.splitlines())
    finally:
        use_local_storage(False)
