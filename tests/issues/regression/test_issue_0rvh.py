"""
Regression test for edgartools-0rvh: offline plain-text extraction from historic
pre-HTML SGML filings via the new FilingSGML.text() convenience.

Historic SGML documents (e.g. 1995) often have no <FILENAME>, and a multi-document
submission keys every such document to '' — so the filename-based get_content('')
collides and returns the wrong document. FilingSGML.text() reads the primary document
by sequence (via the parsed sgml_document), so it returns the correct document and works
with no network access (reported by M. Gruening, TU Ilmenau).

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


def test_filing_sgml_text_returns_primary_document(sgml):
    """FilingSGML.text() returns the primary form, not a colliding filenameless sibling.

    The submission has two <FILENAME>-less documents; a naive filename lookup would
    return the shorter cover letter. text() resolves the sequence-1 primary document.
    """
    text = sgml.text()
    assert text is not None
    assert "FORM 24F-2" in text
    assert "ANNUAL NOTICE OF SECURITIES SOLD" in text
    assert "<PAGE>" not in text          # SGML page-break markers stripped
    assert len(text) > 5000              # the full form, not the cover-letter sibling
    # Fixed-width layout is preserved (not reflowed).
    assert any(line.startswith("     ") for line in text.splitlines())


def test_primary_document_content_accessible_offline(sgml):
    """The document body is reachable by sequence without any network call."""
    content = sgml.attachments.get_by_sequence(1).content
    assert "FORM 24F-2" in content
    assert len(content) > 5000


def test_filing_text_offline_for_filenameless_primary(monkeypatch, tmp_path):
    """filing.text() returns the primary <TEXT> body offline for a <FILENAME>-less filing.

    Scoped to the historic pre-HTML shape; the bundle is staged in local storage and the
    network is blocked, so any fallback fetch would fail loudly.
    """
    from edgar import Filing, use_local_storage

    day_dir = tmp_path / "filings" / "19951228"
    day_dir.mkdir(parents=True)
    (day_dir / "0000950129-95-001652.nc").write_bytes(open(FIXTURE, "rb").read())

    monkeypatch.setenv("EDGAR_LOCAL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9")
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:9")
    use_local_storage(str(tmp_path), use_local=True, allow_network_fallback=False)
    try:
        filing = Filing(cik=810271, accession_no="0000950129-95-001652", form="24F-2NT",
                        company="COMMON SENSE TRUST", filing_date="1995-12-28")
        text = filing.text()
        assert "FORM 24F-2" in text
        assert len(text) > 5000
    finally:
        use_local_storage(False)
