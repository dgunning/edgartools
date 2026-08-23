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

#
# Re-captured a SEVENTH time, for the table data-row truncation fix
# (edgartools-j8bs). A data row rendered only the first line of each cell, so
# any cell whose text wrapped lost everything after line one; header rows never
# did. Trailing per-line padding to the last column's width was dropped in the
# same change.
#
# Every filing gets SMALLER while carrying MORE text -- padding out, content in:
#
#                       chars                non-whitespace
#   Apple 10-K      269,924 -> 253,809     172,906 -> 173,747   (+841)
#   10x Genomics    604,621 -> 595,520     453,711 -> 461,351   (+7,640)
#   Exelon 8-K        2,619 ->   2,629       1,882 ->   2,012   (+130)
#   BofA 424B2      108,462 ->  81,438      63,577 ->  66,035   (+2,458)
#   Merck CORRESP     1,362 ->   1,362       1,131 ->   1,131   unchanged
#
# Merck is byte-identical and keeps its hash: a CORRESP with no wrapped table
# cell has nothing to recover and nothing to unpad.
#
# The character-level diff reports ~1,825 non-whitespace characters "removed"
# from 10x Genomics. They are not lost. The chunks it names begin mid-word
# ("ith staggered three-year terms", "approva") because re-wrapping moves the
# alignment; every phrase was probed in the new text and all are present. The
# genuine removals are box-drawing rules (U+2500) whose count tracks line
# structure -- 9,498 remain.
#
# Both paths still agree on all five, so one hash still covers them.
#
# Re-captured an EIGHTH time, for the header-row misclassifications in
# edgartools-y264. Two of the five filings move, and both moves are pure
# relocation: `sorted(before) == sorted(after)` holds on each, so not one
# character was gained, lost or altered — rows changed which side of the
# header/body split they render on.
#
#   Apple 10-K      253,809 -> 253,809 chars, 4 lines differ
#   10x Genomics    595,520 -> 595,520 chars, 2 lines differ
#   Merck, Exelon, BofA 424B2  byte-identical
#
# Apple's two moved lines are term-debt rows carrying interest-rate RANGES:
#
#   Fixed-rate 0.000% - 4.650% notes  2024 - 2062  $ 101,322  0.03% - 6.72% ...
#
# A range cell was being counted as text by the content-type-ratio branch of
# _is_header_row, so the rows scored as all-text and rendered inside the header
# block. They now render in the table body, below the rule, which is why the
# lines move down rather than change. 10x Genomics moves for the same reason at
# one remove: its two differing lines are the box-drawing rule shifting by one
# row as a row leaves its header.
#
# This is the first re-capture on this corpus where nothing was repaired in the
# text itself. The user-visible change is that these rows are now readable as
# data — which is what the markdown parity ratchet measures, and where the same
# fix took the tracked corpus from 902 lost numbers to 739.

# DO NOT WRITE THE NINTH ONE OF THESE BY HAND.
#
#     hatch run python scripts/recapture_text_baseline.py --explain "..."
#
# It checks out --before (default origin/main) into a temporary worktree,
# replays these same cassettes there, diffs old against new, rewrites the
# hashes below and prints the entry to paste above. The claim every entry above
# makes by hand — "differs by inserted spaces only, no character content
# changed" — is now checked mechanically, and the script refuses to rewrite a
# hash when it does not hold.
#
# AND IT DOES NOT ALWAYS HOLD. Running it against 9c1488b6~1 (the state before
# #1006) reproduces that re-capture exactly: 2 of these 5 filings moved, 3 were
# byte-identical, and both changes are a box-drawing rule shifting by one row as
# a row leaves the header block — content, not whitespace. So the blanket
# sentence near the top of this comment block is true of the word-boundary
# re-captures and NOT of the most recent one, which the eighth entry half-says
# already ("nothing was repaired in the text itself"). The invariant is a
# property of an individual re-capture, not of this file.

BASELINE = {
    # Modern iXBRL 10-K
    "0000320193-23-000106": (
        dict(form="10-K", filing_date="2023-11-03", company="Apple Inc.",
             cik=320193, accession_no="0000320193-23-000106"),
        # Re-captured for the fast_table column cap: the renderer kept only the 8
        # highest-scoring columns of a table, so wide financial tables silently lost
        # real columns. Apple's marketable-securities and stock-performance tables
        # regain their headers ("September", "Cash", "Unrealized", "Losses",
        # "Marketable", "Securities") and 22 "$" markers; "98 204 269" becomes
        # "$98  $204  $269". No value is lost -- every number in the old text is still
        # present, and the only tokens that leave the word Counter do so by gaining a
        # "$" prefix.
        # Re-captured again for edgartools-y0ri / -3cis. Apple's tables regain
        # sparse label columns ("Number") and merge their affix columns: 18 more
        # "%" characters appear and "7 %" becomes "7%", "(3) %" becomes "(3)%".
        # The "$" character count RISES 392 -> 400 (none lost; the standalone ones
        # merged into their figures), and every number in the old text is still
        # present IN ORDER, with 5 added.
        "e3209b778ecea2eb25debbeec095f9662f478a25125d069c96b28341d7dc10e5",
    ),
    # Plain HTML 10-K
    "0001193125-20-052640": (
        dict(form="10-K", filing_date="2020-02-27", company="10x Genomics, Inc.",
             cik=1770787, accession_no="0001193125-20-052640"),
        # Re-captured for the same fast_table column cap. 10x Genomics' statement of
        # stockholders' equity regains "Accumulated", "Shares", "Amount", "Net" and
        # "Stock" headers, 24 "$" markers, and a whole "$2" column that the cap had
        # dropped. Counts of every existing figure (420,083 / 682,494 / 138,450 /
        # 3,437 / 99,869 / 96,431) are unchanged before and after.
        # Re-captured again for edgartools-y0ri / -3cis. The clearest signal here
        # is parenthesis balance: this filing had 575 "(" against 346 ")" -- every
        # negative number rendered unclosed. It is now 577 against 556, and
        # "(31,251" / "(112,485" / "(18,762" render as "(31,251)" / "(112,485)" /
        # "(18,762)". "$" rises 606 -> 612, and every pre-existing number is still
        # present in order, with 10 added.
        "6c84a4404ec72ffbef863c7c92b227be500de7d4fa74beb0de5e7cb8d9eaf862",
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
        # Re-captured for edgartools-hxtd: a <br> between two inline elements was
        # being pruned as an empty node, so the filer's line breaks arrived as
        # spaces. This cover page gains two of them back --
        # "CURRENT REPORT Pursuant to Section 13" -> "CURRENT REPORT\nPursuant to
        # Section 13", and the same at "April 26, 2005 Date of Report". Length is
        # unchanged at 2,629 characters and
        # "".join(before.split()) == "".join(after.split()) holds, so nothing but
        # whitespace moved. This is the only filing of the five that changed.
        "37211411d05d2120eece22347d8c7cbfde46680d516751fbcce17f060dcb7b5e",
    ),
    # 424B2 structured note
    "0001481057-23-010389": (
        dict(form="424B2", filing_date="2023-12-13", company="BANK OF AMERICA CORP /DE/",
             cik=70858, accession_no="0001481057-23-010389"),
        "32a49882a47542bf4e0d03af0dd389571a83c2d42452825b7cb138dedcb4b1c2",
    ),
}

ASSERTED = list(BASELINE)


# These replay recorded submissions rather than fetching from SEC.
#
# This file is the guard on Filing.text(), and while it was `network`-marked it
# ran post-merge only: three pull requests merged green on 2026-08-08 and each
# turned `main` red here minutes later (bead edgartools-hwdp). Nothing in the
# usual PR loop ran it, because `hatch run test-fast` selects on the `fast`
# marker. Replaying moves all 17 tests into the pull-request gate, which is the
# point of the change — a regression-marked test with no fast/network/slow
# marker is auto-marked `fast` (see tests/conftest.py), so dropping `network`
# is what puts them there.
#
# ONE CASSETTE PER FILING, not one per test. The three parametrized tests fetch
# the same six submissions, so per-test cassettes would store 19.4 MB of corpus
# three times over. Naming the cassette after the accession instead of the test
# stores each submission once — 23.5 MB total — and the tests that share a
# filing share its recording.
#
# It also makes recording work at all. `record_mode` is `once`, so a cassette is
# sealed as soon as it exists; a single shared cassette records the first test's
# filing and then refuses the other five. Keyed by accession, each file contains
# exactly the one submission its tests ask for.
#
# To re-record: delete the affected tests/cassettes/filing_text_baseline_*.yaml
# and run this file with the network available. Record against `main`, per
# CONTRIBUTING.md — a cassette recorded with a text-pipeline change applied
# bakes that change in, and the baseline can no longer fail when it regresses.
APPLE_10K = "0000320193-23-000106"
HISTORIC_PLAINTEXT = "0000912057-00-023442"


def records(accession):
    """Point an unparametrized test at the cassette for the filing it reads."""
    def mark(func):
        func.accession = accession
        return func
    return mark


@pytest.fixture
def vcr_cassette_name(request):
    """Name the cassette after the filing it holds, not the test that plays it."""
    callspec = getattr(request.node, "callspec", None)
    accession = callspec.params["accession"] if callspec else request.function.accession
    return f"filing_text_baseline_{accession}"


@pytest.mark.vcr
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


@pytest.mark.vcr
@pytest.mark.parametrize("accession", ASSERTED)
def test_sgml_text_output_unchanged(accession):
    """FilingSGML.text() agrees with Filing.text() and is likewise unchanged."""
    kwargs, expected = BASELINE[accession]
    filing = Filing(**kwargs)

    text = filing.sgml().text()

    assert text is not None
    assert sha256(text) == expected


@pytest.mark.vcr
@pytest.mark.parametrize("accession", ASSERTED)
def test_both_paths_agree(accession):
    kwargs, _ = BASELINE[accession]
    filing = Filing(**kwargs)

    assert filing.text() == filing.sgml().text()


@pytest.mark.vcr
@records(APPLE_10K)
def test_distinctive_content_survives_in_apple_10k():
    """A content check alongside the hash, so a failure says what was lost."""
    kwargs, _ = BASELINE[APPLE_10K]
    text = Filing(**kwargs).text()

    assert "Apple Inc." in text
    assert "CONSOLIDATED STATEMENTS OF OPERATIONS" in text.upper()
    assert "iPhone" in text

    # Words either side of an inline element stay separate (319469c7).
    assert "Apple Watch® Series 9" in text
    assert "established in Internal Control - Integrated Framework" in text


@pytest.mark.vcr
@records(HISTORIC_PLAINTEXT)
def test_historic_plaintext_filing_keeps_fixed_width_layout():
    """Pre-HTML filings are returned as laid out, not reflowed through an HTML parser.

    FilingSGML.text() is the offline path for these; it preserves the fixed-width
    columns that historic financial tables depend on.
    """
    filing = Filing(form="10-Q", filing_date="2000-05-11", company="APPLE COMPUTER INC",
                    cik=320193, accession_no=HISTORIC_PLAINTEXT)

    text = filing.sgml().text()

    assert text is not None
    assert "<PAGE>" not in text          # SGML page-break markers stripped
    assert any(line.startswith("     ") for line in text.splitlines())
    assert "SECURITIES AND EXCHANGE COMMISSION" in text
