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
#
# Re-captured a SIXTH time, and this one banks two separate changes because the
# fifth capture was never followed up. All five filings move.
#
# (a) THE MISSED ONE. ef9c70b0 (#993, the exhibit-index fix) changed _extract_text
#     to stop fabricating a space between adjacent inline elements, and restored
#     exhibit-index tables that were being classified as all-header. It moved this
#     corpus and the hashes were not re-captured -- verified by bisect: 0 failures
#     at its parent ea538528, 8 at ef9c70b0. The file went red on 2026-08-08 and
#     stayed red, because it is network-marked and `hatch run test-fast` selects on
#     the `fast` marker, so nothing in the usual PR loop runs it.
#       Apple +2,969   10x Genomics +1,232   BofA +1,484   Merck 0   Exelon 0
#     Content gained, not whitespace: these are exhibit rows coming back.
#
# (b) THIS CHANGE. Both text paths stop rendering through rich_to_text(), which
#     went via Document.__repr__ and its hardcoded table_max_col_width=200, and
#     call document.text(table_max_col_width=500) directly. Long table cells were
#     being cut at 200 characters with no ellipsis. Filing.text() was fixed first
#     (#995) and FilingSGML.text() was missed, which is what broke
#     test_both_paths_agree; both are now the same call.
#       Apple +6,394   BofA +9,135   10x Genomics +1,009   Merck -1   Exelon -1
#     Recovered text is prose that had been cut mid-sentence -- Apple's FY2023
#     "gross unrecognized tax benefits was $19.5 billion, of which $9.5 billion, if
#     recognized, would impact Apple..." and BofA's automatic-call terms. Checked
#     for duplication: none of Apple's six recovered chunks already existed
#     elsewhere in the old text.
#     The two -1s are whitespace: "".join(before.split()) == "".join(after.split())
#     holds on Merck and Exelon, so nothing but a space moved on those.
#
#     Both paths now produce identical output on all five filings, which is why a
#     single hash still covers them.

BASELINE = {
    # Modern iXBRL 10-K
    "0000320193-23-000106": (
        dict(form="10-K", filing_date="2023-11-03", company="Apple Inc.",
             cik=320193, accession_no="0000320193-23-000106"),
        "ff65df35e734f046041f768a17c6f3aa939779eaa75ab2939ad2ed33e7ca2c8f",
    ),
    # Plain HTML 10-K
    "0001193125-20-052640": (
        dict(form="10-K", filing_date="2020-02-27", company="10x Genomics, Inc.",
             cik=1770787, accession_no="0001193125-20-052640"),
        "1185fdd9547ad64d3e4b9becf320b9c6033f643df2930ff45d188a5255fd1e28",
    ),
    # CORRESP — the shape where the two paths already agreed before the fix
    "0000065873-05-000060": (
        dict(form="CORRESP", filing_date="2005-11-03", company="MERCK & CO INC",
             cik=65873, accession_no="0000065873-05-000060"),
        "733944a9b6e911a63321cd3d37c3a1408ad3ac215e9a93e4ed04f549e5c42b6e",
    ),
    # 2005-era HTML 8-K
    "0000950137-05-004969": (
        dict(form="8-K", filing_date="2005-04-27", company="EXELON CORP",
             cik=1109357, accession_no="0000950137-05-004969"),
        "2105709ed5c1e6379f2f13448caeafb50add837d46dee26ad6877344a9ead511",
    ),
    # 424B2 structured note
    "0001481057-23-010389": (
        dict(form="424B2", filing_date="2023-12-13", company="BANK OF AMERICA CORP /DE/",
             cik=70858, accession_no="0001481057-23-010389"),
        "b340e30f1a3901a4ec99cc002517df3c42791a91fa99c833c6eae96210e5f74f",
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
