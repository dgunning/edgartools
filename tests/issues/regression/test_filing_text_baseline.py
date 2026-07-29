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
# Hashes captured on the unmodified code before the rck1/j8bs/e0hr fixes.
BASELINE = {
    # Modern iXBRL 10-K
    "0000320193-23-000106": (
        dict(form="10-K", filing_date="2023-11-03", company="Apple Inc.",
             cik=320193, accession_no="0000320193-23-000106"),
        "80f608044f7a2eb0cbcb6b3102a905a5757e837671b761b261d4132be7aacd61",
    ),
    # Plain HTML 10-K
    "0001193125-20-052640": (
        dict(form="10-K", filing_date="2020-02-27", company="10x Genomics, Inc.",
             cik=1770787, accession_no="0001193125-20-052640"),
        "6a6a53a9bec74819bae9fb181a708a13f010be6da2479fd12c6c90756e98af01",
    ),
    # CORRESP — the shape where the two paths already agreed before the fix
    "0000065873-05-000060": (
        dict(form="CORRESP", filing_date="2005-11-03", company="MERCK & CO INC",
             cik=65873, accession_no="0000065873-05-000060"),
        "7e80dff07ee6e4eb414c48c11171768643fb1afa2093d5f1c4f829d8d4171898",
    ),
    # 2005-era HTML 8-K
    "0000950137-05-004969": (
        dict(form="8-K", filing_date="2005-04-27", company="EXELON CORP",
             cik=1109357, accession_no="0000950137-05-004969"),
        "3e61134657342bc1674d37ca72b67f1090745b4792c03a7c8c17f3e7b846f00e",
    ),
    # 424B2 structured note
    "0001481057-23-010389": (
        dict(form="424B2", filing_date="2023-12-13", company="BANK OF AMERICA CORP /DE/",
             cik=70858, accession_no="0001481057-23-010389"),
        "7592cef4538e85438ceef27cf39a041fb23f36551994d1a0ac10f2b5d150ca18",
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
