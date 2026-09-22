"""
Regression test for edgartools-dzwm: FilingSGML.html() raised UnicodeDecodeError on
filings whose primary document is a PDF (reported by M. Gruening from a 1993-2026
full-corpus crawl; 10 occurrences, all 40-17G / CERT / 40-24B2-A).

The guard was never missing. ``html()`` has always skipped binary primaries, but
``is_binary()`` compared a raw ``.extension`` against a lowercase tuple, so a document
named ``goodhaven_40-17g.PDF`` answered False and fell through to a bare
``.decode('utf-8')``. Three independent ways to fail open lived in that one path:

  1. case-sensitive comparison (``.PDF`` never matched ``.pdf``)
  2. a malformed table entry (``"png"``, with no leading dot, matched nothing)
  3. ``binary_extensions`` defined twice in edgar/core.py, so fixing one copy was a no-op

Assertions run offline against a synthetic submission and the tables themselves. The
real accessions from the report are covered by a network-marked test at the bottom.
"""

import pytest

from edgar.attachments import Attachment
from edgar.core import binary_extensions, text_extensions
from edgar.sgml import FilingSGML

# Modelled on 0000894189-25-002476 (GoodHaven 40-17G): a fidelity bond filed as a PDF
# whose filename carries an uppercase extension, with the real PDF magic bytes.
PDF_PRIMARY_SUBMISSION = """<SEC-DOCUMENT>0000894189-25-002476.txt : 20250401
<SEC-HEADER>0000894189-25-002476.hdr.sgml : 20250401
ACCESSION NUMBER:\t\t0000894189-25-002476
CONFORMED SUBMISSION TYPE:\t40-17G
FILED AS OF DATE:\t\t20250401
</SEC-HEADER>
<DOCUMENT>
<TYPE>40-17G
<SEQUENCE>1
<FILENAME>goodhaven_40-17g.PDF
<DESCRIPTION>FIDELITY BOND
<TEXT>
%PDF-1.6
%\xe2\xe3\xcf\xd3
1 0 obj
</TEXT>
</DOCUMENT>
</SEC-DOCUMENT>
"""

# Every accession that raised in the reporter's log.
REPORTED_ACCESSIONS = [
    "0001569521-14-000005",
    "0000894189-17-006543",
    "0000894189-18-003204",
    "0001354457-18-000175",
    "0001354457-18-000200",
    "0000746601-18-000009",
    "0000894189-18-004537",
    "0001354457-20-000186",
    "0001162044-24-000236",
    "0000894189-25-002476",
]


def _attachment(document: str) -> Attachment:
    return Attachment(
        sequence_number="1",
        description="",
        document=document,
        ixbrl=False,
        path=f"/Archives/edgar/data/1/{document}",
        document_type="40-17G",
        size=None,
    )


# ── The extension tables themselves ────────────────────────────────────────

@pytest.mark.fast
def test_extension_tables_are_lowercase_and_dot_prefixed():
    """Entries are matched against a normalized extension, so a bare or uppercase
    entry can never fire. Two such entries ("png", "XML") shipped for years."""
    for table, name in ((binary_extensions, "binary_extensions"), (text_extensions, "text_extensions")):
        for entry in table:
            assert entry.startswith("."), f"{name} entry {entry!r} is missing its leading dot"
            assert entry == entry.lower(), f"{name} entry {entry!r} is not lowercase"


@pytest.mark.fast
def test_png_is_classified_as_binary():
    """The specific casualty of the missing leading dot."""
    assert ".png" in binary_extensions
    assert _attachment("chart.png").is_binary()


@pytest.mark.fast
def test_extension_tables_defined_once():
    """binary_extensions was defined twice in edgar/core.py with the typo in both
    copies, so a fix applied to one was silently a no-op."""
    source = (pytest.importorskip("pathlib").Path(__file__).parents[3] / "edgar" / "core.py").read_text()
    assert source.count("\nbinary_extensions = ") == 1
    assert source.count("\ntext_extensions = ") == 1


# ── Classification is case-insensitive ─────────────────────────────────────

@pytest.mark.fast
@pytest.mark.parametrize("document", ["bond.pdf", "bond.PDF", "bond.Pdf"])
def test_is_binary_ignores_filename_casing(document):
    assert _attachment(document).is_binary()


@pytest.mark.fast
@pytest.mark.parametrize(
    "document,predicate",
    [
        ("doc.HTM", "is_html"), ("doc.HTML", "is_html"),
        ("doc.XML", "is_xml"), ("doc.XSD", "is_xml"),
        ("doc.TXT", "is_text"), ("doc.PAPER", "is_text"),
    ],
)
def test_predicates_ignore_filename_casing(document, predicate):
    """is_xml/is_html already lowercased; is_text/is_binary did not. All four now agree."""
    assert getattr(_attachment(document), predicate)()


# ── End to end, offline ────────────────────────────────────────────────────

@pytest.mark.fast
def test_pdf_primary_is_recognised_as_binary():
    sgml = FilingSGML.from_text(PDF_PRIMARY_SUBMISSION)
    primary = sgml.attachments.primary_html_document
    # primary_html_document falls back to the first primary document when nothing
    # has an .htm/.html extension, so a PDF legitimately arrives here.
    assert primary.document == "goodhaven_40-17g.PDF"
    assert primary.extension == ".PDF"
    assert primary.is_binary()


@pytest.mark.fast
def test_html_returns_none_for_pdf_primary_instead_of_raising():
    """The reported crash. None is the contract edgartools-e0hr established for text():
    a truthful "no HTML here", never U+FFFD mojibake."""
    sgml = FilingSGML.from_text(PDF_PRIMARY_SUBMISSION)
    assert sgml.html() is None


@pytest.mark.fast
def test_text_returns_none_for_pdf_primary():
    """text() was already correct (edgartools-e0hr); pinned so it stays that way."""
    sgml = FilingSGML.from_text(PDF_PRIMARY_SUBMISSION)
    assert sgml.text() is None


# ── The real filings from the report ───────────────────────────────────────

@pytest.mark.network
@pytest.mark.parametrize("accession", REPORTED_ACCESSIONS)
def test_reported_accessions_do_not_raise(accession):
    from edgar import find

    sgml = find(accession).sgml()
    # The assertion is that this returns at all — every one of these raised
    # UnicodeDecodeError on 5.47.0 through 5.49.0.
    assert sgml.html() is None
