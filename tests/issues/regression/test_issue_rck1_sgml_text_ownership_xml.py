"""
Regression test for edgartools-rck1: FilingSGML.text() returned raw ownership XML.

Beads: edgartools-rck1

Bug: FilingSGML.text() handed the primary document straight to an is-it-HTML check.
For Forms 3/4/5 the primary document is <ownershipDocument> XML, which is not HTML,
so text() returned the raw markup — schema versions, CIK digits and tag names instead
of a readable Form 4.

Fix: FilingSGML.text() now detects ownership XML by its root element and renders it
through the same Ownership.to_html() the data objects use.

KNOWN LIMITATION — Filing.text() is deliberately NOT changed. Its form-aware branch
in Filing.html() fires on `html.startswith("<?xml")`, so 2000s ownership filings whose
XML has no declaration (like the AAR filing below) still come back as a bare list of
tag values ("X0201\\n4\\n2004-01-07\\n..."). Changing Filing.html()/Filing.text() is
out of scope per the d216a934 revert (their contracts are load-bearing); see the
module docstring of edgar/sgml/text_extraction.py. For declaration-carrying ownership
XML (the modern, common shape) the two paths agree exactly.

Ground truth verified by hand against the filing's own Form 4:
AAR CORP [AIR], reporting person ROMENESKO TIMOTHY J, transaction dated 2004-01-07.
"""

import pytest

from edgar import Filing

# AAR CORP Form 4, 2004-02-04. Its ownership XML has NO <?xml declaration, which is
# what let the bug through on both code paths.
AAR_FORM4 = dict(
    form="4",
    filing_date="2004-02-04",
    company="AAR CORP",
    cik=1750,
    accession_no="0000001750-04-000011",
)

# A Form 4 whose XML *does* carry a declaration — only FilingSGML.text() was wrong here.
ABRAMS_FORM4 = dict(
    form="4",
    filing_date="2004-01-05",
    company="ABRAMS INDUSTRIES INC",
    cik=1923,
    accession_no="0000001923-04-000001",
)


@pytest.fixture(scope="module")
def aar_filing():
    return Filing(**AAR_FORM4)


@pytest.mark.network
def test_sgml_text_is_not_raw_ownership_xml(aar_filing):
    """FilingSGML.text() renders the Form 4 instead of dumping its XML."""
    text = aar_filing.sgml().text()

    assert text is not None
    assert not text.lstrip().startswith("<")
    assert "<ownershipDocument" not in text
    assert "<schemaVersion>" not in text
    assert "documentType" not in text


@pytest.mark.network
def test_sgml_text_contains_the_rendered_form(aar_filing):
    """The rendered text carries the Form 4's actual content."""
    text = aar_filing.sgml().text()

    assert "FORM 4" in text
    assert "STATEMENT OF CHANGES IN BENEFICIAL OWNERSHIP" in text
    # Ground truth from the filing itself.
    assert "ROMENESKO TIMOTHY J" in text
    assert "AAR CORP" in text
    assert "AIR" in text


@pytest.mark.network
@pytest.mark.xfail(
    reason="Known limitation: Filing.html()'s ownership branch fires only on an "
    "<?xml declaration, so declaration-less ownership XML still renders as a tag "
    "skeleton. Fixing it means changing Filing.html(), which the d216a934 revert "
    "showed is high-risk; FilingSGML.text() is the reliable path for these.",
    strict=False,
)
def test_filing_text_no_longer_returns_tag_skeleton(aar_filing):
    """Filing.text() would ideally render declaration-less ownership XML too."""
    text = aar_filing.text()

    assert text is not None
    assert not text.startswith("X0201")
    assert "FORM 4" in text
    assert "ROMENESKO TIMOTHY J" in text


@pytest.mark.network
def test_ownership_xml_with_declaration_also_renders():
    """The fix is not specific to declaration-less XML."""
    filing = Filing(**ABRAMS_FORM4)
    sgml_text = filing.sgml().text()

    assert "<ownershipDocument" not in sgml_text
    assert "FORM 4" in sgml_text
    assert sgml_text == filing.text()


def test_ownership_detection_ignores_plain_text():
    """Pre-XML (2002-era) Forms 4 are fixed-width text and must not hit the XML parser."""
    from edgar.sgml.text_extraction import looks_like_ownership_xml, primary_document_text

    plain = "                      FORM 4\n\n  UNITED STATES SECURITIES AND EXCHANGE\n"
    assert not looks_like_ownership_xml(plain)
    # Form says "4", content says otherwise — content wins, text is returned untouched.
    assert primary_document_text("4", plain) == plain


def test_ownership_detection_handles_namespaced_root():
    from edgar.sgml.text_extraction import looks_like_ownership_xml

    assert looks_like_ownership_xml('<?xml version="1.0"?><ownershipDocument>')
    assert looks_like_ownership_xml('<?xml version="1.0"?><ns1:ownershipDocument>')
    assert not looks_like_ownership_xml('<?xml version="1.0"?><edgarSubmission>')
