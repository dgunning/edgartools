"""Item headers wrapped across lines still match their patterns (edgartools-dt1f.1).

Header text arrives carrying the source HTML's line wrapping. A filer-agent
table cell written as::

    <td>ITEM 5. OPERATING
    AND FINANCIAL REVIEW AND PROSPECTS</td>

reaches the section extractor as ``'ITEM\\n5. OPERATING\\nAND FINANCIAL REVIEW
AND PROSPECTS'``. In HTML that newline is only whitespace, but the section
patterns join words with ``.*``, which does not cross a newline — they are
compiled without ``DOTALL``. So whether a wrapped header matched came down to
which metacharacter its pattern happened to use: ``item_4``'s
``Information\\s+on\\s+the\\s+Company`` matched because ``\\s`` covers ``\\n``,
while ``item_5``'s ``Operating.*Financial\\s+Review`` did not.

The headers were never missing. Every one asserted here was already in the list
``_find_section_headers`` returned; they failed at the match. That is why the
symptom looked like a detection hole on some items and not others of the same
filing.

WHAT THIS CLOSED. Eight of the nineteen item lookups that returned text only
because ``ChunkedDocument`` was still wired in as a ``__getitem__`` fallback:
seven on the two 20-Fs below and 10-K Item 7A, whose header reads "Quantitative
and Qualitative\\nDisclosures about Market Risk". The remaining eleven are other
defects — see the bead.

THE CHARACTER COUNTS ARE THE ASSERTION. `is not None` would pass on a section
that starts at the wrong header or stops at the wrong boundary, which is the
failure mode this area actually has. If one of these numbers moves, the
extraction boundary moved: verify what the section now contains before updating
it, rather than re-recording the new number.

CORPUS NOTE. The 20-F and 10-K asserted unconditionally live in
``tests/fixtures/parity_gate``, which is tracked, so this test runs in CI. The
2010 20-F that carries five of the eight lookups is in
``tests/fixtures/text_boundary_corpus``, which is gitignored — anchoring only on
that one would pass locally and skip in CI, which is how parity evidence has
been lost here before. It is checked opportunistically at the bottom.
"""
import pathlib
import re

import pytest

from edgar.company_reports.ten_k import TenK
from edgar.company_reports.twenty_f import TwentyF
from edgar.documents.extractors.pattern_section_extractor import SectionExtractor

FIXTURES = pathlib.Path(__file__).parent.parent.parent / "fixtures"
TRACKED_20F = FIXTURES / "parity_gate" / "20-F" / "0001062993-16-008650.html"
TRACKED_10K = FIXTURES / "parity_gate" / "10-K" / "0000950153-99-001234.html"
IGNORED_20F = (FIXTURES / "text_boundary_corpus" / "e3_2009_2014" / "20-F"
               / "0001144204-10-017467.html")


class FixtureFiling:
    """The minimum surface the report classes touch, backed by a local file."""

    filing_date = None

    def __init__(self, path: pathlib.Path, form: str):
        self._path = path
        self.form = form
        self.company = "fixture"
        self.accession_number = path.stem
        self.base_dir = str(path.parent)

    def html(self):
        return self._path.read_text(encoding="utf-8", errors="replace")


def _without_legacy(cls):
    """A subclass whose legacy fallbacks are unavailable.

    Deliberately a throwaway subclass rather than patching and deleting the
    attribute on ``cls``: TenK, TenQ and CurrentReport each define
    ``_chunked_document`` on themselves, so ``del cls._chunked_document`` would
    destroy the real override instead of restoring it, and every later assertion
    in the session would silently measure a different object.

    ``_cross_reference_index`` goes too. On a 10-K it is consulted after the new
    parser and before ChunkedDocument, so leaving it in place would let a lookup
    pass through a path this fix says nothing about.
    """
    return type(
        f"NoLegacy{cls.__name__}",
        (cls,),
        {
            "_chunked_document": property(lambda self: None),
            "_cross_reference_index": property(lambda self: None),
        },
    )


def test_the_tracked_fixtures_are_present():
    """Absent is not passing — guard the fixtures these assertions rest on."""
    for path in (TRACKED_20F, TRACKED_10K):
        assert path.exists(), (
            f"{path} is tracked and must be present; without it the assertions "
            f"below would vacuously skip"
        )


def test_the_20f_headers_really_are_wrapped():
    """Pin the precondition.

    Without this, a future change that stops emitting the newline would leave
    the assertions below passing for an unrelated reason, and the defect they
    guard would be unguarded.
    """
    from edgar.documents.config import ParserConfig
    from edgar.documents.parser import HTMLParser
    from edgar.documents.table_nodes import TableNode

    doc = HTMLParser(ParserConfig(form="20-F")).parse(
        TRACKED_20F.read_text(encoding="utf-8", errors="replace")
    )
    wrapped = [
        text
        for table in doc.root.find(lambda n: isinstance(n, TableNode))
        for row in table.rows
        for text in (" ".join(c.text().strip() for c in row.cells if c.text().strip()),)
        if re.match(r"^Item\s+6\.\s+Directors", text, re.IGNORECASE) and "\n" in text
    ]
    assert wrapped, "expected this filing's Item 6 header to wrap across lines"


def test_20f_wrapped_headers_resolve_without_the_legacy_parser():
    """Items 6 and 11 wrap mid-title; both patterns join words with ``.*``."""
    filing = FixtureFiling(TRACKED_20F, "20-F")
    report = _without_legacy(TwentyF)(filing)

    # 'Item 6. Directors, Senior Management and\nEmployees'
    assert len(report["Item 6"]) == 42307
    assert report["Item 6"].split("\n", 1)[0].startswith("Item 6.")

    # 'Item 11. Quantitative and Qualitative Disclosures\nAbout Market Risk.'
    assert len(report["Item 11"]) == 268
    assert report["Item 11"].split("\n", 1)[0].startswith("Item 11.")

    # And the same answers on the real class, legacy fallback and all.
    assert len(TwentyF(filing)["Item 6"]) == 42307
    assert len(TwentyF(filing)["Item 11"]) == 268


def test_10k_wrapped_item_7a_resolves_without_the_legacy_parser():
    """"Quantitative and Qualitative\\nDisclosures about Market Risk"."""
    filing = FixtureFiling(TRACKED_10K, "10-K")

    text = _without_legacy(TenK)(filing)["Item 7A"]
    assert len(text) == 265
    assert text.startswith("Item 7A:")


def test_a_toc_row_does_not_outrank_the_body_header():
    """The other half of the fix.

    Normalizing header text also lets table-of-contents rows match patterns they
    used to miss, and the candidate ranking breaks ties by content size — which a
    TOC row always wins, because it sits in the front matter and its span runs
    until the next matched header rather than over the item's real content. On
    this filing Item 1 is a 372-character "not applicable" stub, and the TOC row
    would have claimed 6,160 characters of front matter for it.

    ``_is_likely_toc_entry`` is the primary guard and does flag both rows here,
    but it needs ``find_toc_boundaries`` to have located a TOC; on
    0001144204-10-017467 it locates none, and nothing marked that filing's TOC
    rows at all. The page-number demotion is what covers that case.
    """
    report = TwentyF(FixtureFiling(TRACKED_20F, "20-F"))
    assert len(report["Item 1"]) == 372


def test_a_bare_item_number_is_not_read_as_a_page_number():
    """"ITEM 5" ends in a digit; the digit is the item, not a page.

    The demotion strips the leading item marker before looking for a trailing
    number. Without that, every bare item header would demote itself.
    """
    assert not SectionExtractor._has_page_number_suffix("ITEM 5")
    assert not SectionExtractor._has_page_number_suffix("Item 16A")
    assert not SectionExtractor._has_page_number_suffix("ITEM 15. CONTROLS AND PROCEDURES")
    assert SectionExtractor._has_page_number_suffix(
        "ITEM 1. IDENTITY OF DIRECTORS, SENIOR MANAGEMENT AND ADVISERS 5"
    )


@pytest.mark.skipif(
    not IGNORED_20F.exists(),
    reason="text_boundary_corpus is gitignored; present on developer machines only",
)
def test_2010_20f_resolves_all_eight_wrapped_items_without_the_legacy_parser():
    """The filing this defect was measured on.

    EDGARizer-generated filer-agent HTML — 12,880 ``<font>`` tags and zero
    ``<p>`` — where every item header is a one-row table wrapped at the source
    line width. Five of these (5, 6, 11, 12, 15) are on the dt1f.1 work list;
    16D-16F came with them.
    """
    filing = FixtureFiling(IGNORED_20F, "20-F")
    report = _without_legacy(TwentyF)(filing)

    # Items 5 and 6 grew by 150 and 20 characters when the fast_table 8-column cap
    # was removed (edgartools-kq2q) -- they are the two that carry tables. The other
    # six are unchanged, which is the signal that the cap removal touches table
    # rendering only and moves no item boundary.
    expected = {
        "Item 5": 107457,
        # Item 6 moved twice: 57,841 -> 57,861 for kq2q, then -> 58,425 for
        # y0ri/3cis, which recovers "Headcount", "Bonus", "Shares" and "Common"
        # label cells and merges "24.8" + "%" into "24.8%". Numbers unchanged.
        "Item 6": 58425,
        "Item 11": 7504,
        "Item 12": 152,
        "Item 15": 14078,
        "Item 16D": 181,
        "Item 16E": 338,
        "Item 16F": 157,
    }
    assert {item: len(report[item]) for item in expected} == expected

    # The TOC row for Item 1 carries a page number and must lose to the body
    # header, which is a 146-character "not applicable" stub.
    assert len(report["Item 1"]) == 146
