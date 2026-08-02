"""
Baseline protection for Filing.text() and FilingSGML.text().

These pin the output of the two text paths on ordinary filings, so that future work on
the shared pipeline in edgar/sgml/text_extraction.py cannot quietly change what the
most heavily used API in the library returns.

The three bug fixes this file accompanies (edgartools-rck1, -j8bs, -e0hr) were verified
against a 45-filing corpus covering every primary-document shape: HTML, iXBRL, plain
text with and without a <FILENAME>, ".paper" stubs, ownership XML, other XML, and
binary PDFs. Filing.text() was byte-identical on every filing that was not one of the
three bugs' repros. The filings below are the representative sample of that corpus.

A failure here is not automatically a regression — but it IS a change in what users
get, so it must be a deliberate, explained one.
"""

import hashlib

import pytest

from edgar import Filing


def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# accession -> (Filing kwargs, expected SHA-256 of BOTH .text() and .sgml().text())
# Hashes captured on the unmodified code before the rck1/j8bs/e0hr fixes, then re-captured
# twice as word boundaries were restored: 319469c7 (preprocessor) and the DocumentBuilder
# text-node edges that followed it. Both moved output the same way — a space an inline
# element used to swallow comes back ("October18" -> "October 18", "anon-acceleratedfiler"
# -> "a non-accelerated filer"), and most recently the whitespace-only spacer elements
# ("☒ANNUAL REPORT" -> "☒ ANNUAL REPORT"). Every changed line on this corpus was verified
# to differ from its predecessor by inserted spaces only, with no character content changed.
#
# Re-captured a fourth time for the lxml remove_blank_text fix (edgartools-vfwp) and the
# mid-word-split suppression (edgartools-jysx), which move output in opposite directions:
# Apple's cover page gains "Yes☒" -> "Yes ☒" and its Item 8 loses "foreign jurisd ictions"
# -> "foreign jurisdictions". 3 of the 5 filings changed (Apple, Merck, Exelon); 10x
# Genomics and the BofA 424B2 are byte-identical. Each changed filing was checked with
# "".join(before.split()) == "".join(after.split()) — true on all three, so nothing but
# whitespace moved. The Exelon 8-K is the same length before and after: a line re-wrapped.
#
# Apple moved once more for the CSS-gap rule (also edgartools-jysx), which separates a
# bullet or footnote marker from its text where the filer drew that gap with padding
# rather than whitespace: "•MacBook Pro 14”" -> "• MacBook Pro 14”", "(3)Exhibits
# required by Item 601" -> "(3) Exhibits required...". Apple is the only one of the five
# affected, +3 chars, whitespace-only.
#
# Re-captured a fifth time for the removal of the ParagraphNode.text() tag allowlist
# (edgartools-jysx). This is the first re-capture where hashes move because output
# *loses* a space rather than gains one — the allowlist spaced any two adjacent inline
# elements regardless of what sat between them, and the spaces it invented after an
# opening quote are the shape that shows up here. 2 of the 5 filings changed:
#   Apple        -1 char, 1 line:  '“ The Company’s operations' -> '“The Company’s operations'
#   10x Genomics -5 chars, 5 lines: '“ Risk Factors - R...' -> '“Risk Factors - R...' (x3,
#                 the exact string Item 1A cross-references), 'Customer’ s Accounting'
#                 -> 'Customer’s Accounting', and one more of the same shape.
# Merck, Exelon and the BofA 424B2 are byte-identical. Both changed filings were checked
# with "".join(before.split()) == "".join(after.split()) — true on both, so nothing but
# whitespace moved, and every changed line was read individually: all four distinct
# repairs, no destroyed boundary.
BASELINE = {
    # Modern iXBRL 10-K
    "0000320193-23-000106": (
        dict(form="10-K", filing_date="2023-11-03", company="Apple Inc.",
             cik=320193, accession_no="0000320193-23-000106"),
        "65e6cb488de90806dd54b4bff0aba0b678a2c0bf6af698a47df09bed19369462",
    ),
    # Plain HTML 10-K
    "0001193125-20-052640": (
        dict(form="10-K", filing_date="2020-02-27", company="10x Genomics, Inc.",
             cik=1770787, accession_no="0001193125-20-052640"),
        "1faea8fc5913ca353f6a5124f221631acccb9bcc16cfc55f6e2a26378298a6d8",
    ),
    # CORRESP — the shape where the two paths already agreed before the fix
    "0000065873-05-000060": (
        dict(form="CORRESP", filing_date="2005-11-03", company="MERCK & CO INC",
             cik=65873, accession_no="0000065873-05-000060"),
        "5fb3d0a62a5bc0d8c77fb8791b068011d4f047d3add254a6a8d6d56c6d787ed5",
    ),
    # 2005-era HTML 8-K
    "0000950137-05-004969": (
        dict(form="8-K", filing_date="2005-04-27", company="EXELON CORP",
             cik=1109357, accession_no="0000950137-05-004969"),
        "a37f4e540bd777f1e2017e4c7c9a58b8782b6b63123a7c2a2fa8260eba8ffc83",
    ),
    # 424B2 structured note
    "0001481057-23-010389": (
        dict(form="424B2", filing_date="2023-12-13", company="BANK OF AMERICA CORP /DE/",
             cik=70858, accession_no="0001481057-23-010389"),
        "fcd15e64fb76fec683067bc1e1c100ce886dc14723d20030dd34d2f6010a6b91",
    ),
}

ASSERTED = list(BASELINE)


@pytest.mark.network
@pytest.mark.parametrize("accession", ASSERTED)
def test_filing_text_output_unchanged(accession):
    """Filing.text() returns exactly what it returned before the text-path unification."""
    kwargs, expected = BASELINE[accession]
    filing = Filing(**kwargs)

    text = filing.text()

    assert text is not None
    assert sha256(text) == expected, (
        f"Filing.text() output changed for {accession}. If this is intentional, "
        f"update the hash and say why in the commit message."
    )


@pytest.mark.network
@pytest.mark.parametrize("accession", ASSERTED)
def test_sgml_text_output_unchanged(accession):
    """FilingSGML.text() agrees with Filing.text() and is likewise unchanged."""
    kwargs, expected = BASELINE[accession]
    filing = Filing(**kwargs)

    text = filing.sgml().text()

    assert text is not None
    assert sha256(text) == expected


@pytest.mark.network
@pytest.mark.parametrize("accession", ASSERTED)
def test_both_paths_agree(accession):
    kwargs, _ = BASELINE[accession]
    filing = Filing(**kwargs)

    assert filing.text() == filing.sgml().text()


@pytest.mark.network
def test_distinctive_content_survives_in_apple_10k():
    """A content check alongside the hash, so a failure says what was lost."""
    kwargs, _ = BASELINE["0000320193-23-000106"]
    text = Filing(**kwargs).text()

    assert "Apple Inc." in text
    assert "CONSOLIDATED STATEMENTS OF OPERATIONS" in text.upper()
    assert "iPhone" in text

    # Words either side of an inline element stay separate (319469c7).
    assert "Apple Watch® Series 9" in text
    assert "established in Internal Control - Integrated Framework" in text


@pytest.mark.network
def test_historic_plaintext_filing_keeps_fixed_width_layout():
    """Pre-HTML filings are returned as laid out, not reflowed through an HTML parser.

    FilingSGML.text() is the offline path for these; it preserves the fixed-width
    columns that historic financial tables depend on.
    """
    filing = Filing(form="10-Q", filing_date="2000-05-11", company="APPLE COMPUTER INC",
                    cik=320193, accession_no="0000912057-00-023442")

    text = filing.sgml().text()

    assert text is not None
    assert "<PAGE>" not in text          # SGML page-break markers stripped
    assert any(line.startswith("     ") for line in text.splitlines())
    assert "SECURITIES AND EXCHANGE COMMISSION" in text
