"""Items 4 and 14 have each carried two titles (edgartools-dt1f.1, Defect A).

The 10-K vocabulary held only the modern meaning of each:

    Item 4    "Mine Safety Disclosures"              — since 2011
    Item 14   "Principal Accountant Fees and Services" — since 2003

Item 4 was "Submission of Matters to a Vote of Security Holders" until
Dodd-Frank s.1503 gave it to mine safety, and exhibits were Item 14 until the
2003 renumbering moved them to Item 15. So on a 1999 10-K both headers were
found as candidates and then discarded at match time, and ``tenk["Item 4"]`` and
``tenk["Item 14"]`` returned text only because the legacy ``ChunkedDocument``
fallback was still wired in — which is what dt1f.1 has to close before
``edgar.files`` can go. The blast radius is every 10-K from before the relevant
renumbering, not the one filing that surfaced it.

TWO DEFECTS, NOT ONE. Matching the header only got Item 14 as far as its first
sub-heading. This filer divides the item with bold "Item 14(a)(1):",
"Item 14 (a)(2):", "Item 14 (a)(3):" markers, which look exactly like Item
headers to the boundary test, so the section stopped at the second of them and
returned 1,189 of its 16,063 characters — the financial-statement list, and
nothing of the schedules or the exhibit index. An item's own sub-designated
markers are now excluded from the boundary test: they carry a parenthesized
sub-designation and NO title, which is what separates them both from a
designated item header ("ITEM 9A(T). CONTROLS AND PROCEDURES", Defect B) and
from the bare, undesignated "Item 3." shape that 20-F headings use.

Once they stopped closing the section it ran to the end of the document instead,
because heading "level" here is a heuristic score rather than markup depth: this
filing's item headers score level 1 and its SIGNATURES line scores level 3, so
the level test refused it as a terminator and Item 14 swallowed the signature
page, Schedule II and the appended exhibit index (32,626 characters). A bare
SIGNATURES line now ends a section whatever its level. That reaches six other
last-item sections across the corpus, every one of them a final item that was
running past the signature block to the end of the document — see the blast
radius below.

BLAST RADIUS, measured across every fixture available on 2026-08-22 by dumping
{section: len(text)} for all four item-based forms before and after:

    era titles          adds 2 sections to this filing; nothing else moves on
                        54 10-K, 31 10-Q, 15 20-F and 15 8-K fixtures
    SIGNATURES ends it  7 sections shorten, all last items, all of them
                        previously running to end-of-document: this Item 14,
                        Item 16 on two 2021 10-Ks, Item 6 on one 10-Q, Item 19
                        and Part III on two 20-Fs, Item 9.01 on one 8-K
"""
import pathlib
import re

import pytest

from edgar.company_reports.ten_k import TenK
from edgar.documents.config import ParserConfig
from edgar.documents.extractors.pattern_section_extractor import (
    _ITEM_SUBHEADER,
    SectionExtractor,
)
from edgar.documents.parser import HTMLParser

FIXTURES = pathlib.Path(__file__).parent.parent.parent / "fixtures"
# Medicis Pharmaceutical's FY1999 10-K. Tracked in parity_gate, so this runs in
# CI rather than only where the gitignored era corpus exists.
GATE_1999 = FIXTURES / "parity_gate" / "10-K" / "0000950153-99-001234.html"
# A 2010 10-K, where Item 14 means accountant fees and Item 15 means exhibits.
GATE_2010 = FIXTURES / "parity_gate" / "10-K" / "0001193125-10-073212.html"


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
    """A subclass with every pre-``edgar.documents`` path unavailable.

    ``TenK.__getitem__`` consults the new parser, then the cross-reference index,
    then ``ChunkedDocument``; 6.0 deletes the last of those. Both are removed
    here so a pass cannot come from anywhere but the modern parser.

    A throwaway subclass rather than patching and deleting the attribute on
    ``cls``: TenK, TenQ and CurrentReport each define ``_chunked_document`` on
    themselves, so ``del`` would destroy the real override.
    """
    return type(
        f"NoLegacy{cls.__name__}",
        (cls,),
        {
            "_chunked_document": property(lambda self: None),
            "_cross_reference_index": property(lambda self: None),
        },
    )


@pytest.fixture(scope="module")
def doc_1999():
    return HTMLParser(ParserConfig(form="10-K")).parse(
        GATE_1999.read_text(encoding="utf-8", errors="replace")
    )


def test_the_tracked_fixtures_are_present():
    """Absent is not passing. Both are tracked, so neither may skip."""
    for path in (GATE_1999, GATE_2010):
        assert path.exists(), f"{path} is tracked and must be present"


def test_the_headers_really_carry_the_era_titles(doc_1999):
    """Pin the precondition.

    The headers were found and then discarded — that is the shape of this
    defect. If a future change stops emitting these candidates, everything below
    would still pass while testing something else.
    """
    headers = SectionExtractor(form="10-K")._find_section_headers(doc_1999)
    texts = [t.strip() for _n, t, _p in headers]
    assert "Item 4: Submission of Matters to a Vote of Security Holders" in texts
    assert (
        "Item 14: Exhibits, Financial Statement Schedules and Reports on Form 8-K"
        in texts
    )


def test_both_era_sections_are_detected(doc_1999):
    sections = doc_1999.sections

    assert len(sections["part_i_item_4"].text()) == 177
    assert sections["part_i_item_4"].text().startswith("Item 4: Submission of Matters")
    assert "No matters were submitted to a vote" in sections["part_i_item_4"].text()

    # 16,063 before edgartools-y0ri: the exhibit table's "Exhibit" and "No."
    # header cells sat in a column with one substantial entry per several rows,
    # which the scorer read as spacing. ZERO tokens are lost and the number
    # sequence is untouched -- the 547 added characters are those headers.
    assert len(sections["part_iii_item_14"].text()) == 16610
    assert sections["part_iii_item_14"].text().startswith("Item 14: Exhibits")

    # The neighbours are unchanged — this adds sections, it does not re-cut the
    # ones on either side. Item 4's header was already a boundary candidate even
    # while it matched no pattern, which is why Item 3 does not shrink here.
    assert len(sections["legal_proceedings"].text()) == 994
    assert len(sections["part_ii_item_5"].text()) == 489
    assert len(sections["part_iii_item_13"].text()) == 269


def test_item_14_keeps_its_schedules_and_exhibit_list(doc_1999):
    """The sub-header half of the defect: 1,189 characters became 16,063."""
    text = doc_1999.sections["part_iii_item_14"].text()

    assert "Financial Statement Schedules" in text
    assert "Exhibits Filed as Part of This Report" in text
    # An exhibit reference from deep in the list — the part that used to be lost.
    assert "Incorporated by reference to the exhibit" in text


def test_item_14_stops_at_the_signature_block(doc_1999):
    """And does not run to the end of the document, which is where it went next.

    POWER OF ATTORNEY is inside the item and SIGNATURES is the terminator, so the
    signature page proper and the appended Schedule II and exhibit index are all
    outside it.
    """
    text = doc_1999.sections["part_iii_item_14"].text()

    assert "POWER OF ATTORNEY" in text
    assert "SIGNATURES" not in text
    assert "SCHEDULE II — VALUATION AND QUALIFYING ACCOUNTS" not in text
    assert "EXHIBIT INDEX" not in text


def test_the_lookups_resolve_without_the_legacy_parser():
    """The two lookups on the dt1f.1 work list.

    Legacy returned 192 characters for Item 4 and 19,464 for Item 14; its Item 14
    ran on through the signature page and Schedule II to the exhibit index.
    """
    report = _without_legacy(TenK)(FixtureFiling(GATE_1999, "10-K"))

    assert len(report["Item 4"]) == 177
    assert len(report["4"]) == 177  # the short spelling resolves too
    # Re-pinned for edgartools-y0ri; see the note in the test above.
    assert len(report["Item 14"]) == 16610
    assert len(report["14"]) == 16610

    items = report.items
    assert "Item 4" in items
    assert "Item 14" in items
    # Item 4 used to be the hole between 3 and 5 in this filing's item list.
    assert items[:5] == ["Item 1", "Item 2", "Item 3", "Item 4", "Item 5"]


def test_a_modern_filing_keeps_the_modern_meanings():
    """The era titles are alternatives, not replacements.

    On a 2010 10-K, Item 14 is accountant fees and the exhibits are Item 15. The
    two vocabularies live in the same table, so the risk worth pinning is that
    the older Item 14 title claims a modern filing's Item 15 or vice versa.
    """
    doc = HTMLParser(ParserConfig(form="10-K")).parse(
        GATE_2010.read_text(encoding="utf-8", errors="replace")
    )

    assert len(doc.sections["part_iii_item_14"].text()) == 262
    assert "PRINCIPAL ACCOUNTANT FEES" in doc.sections["part_iii_item_14"].text()
    assert len(doc.sections["part_iv_item_15"].text()) == 153840

    # And the 1999 filing, whose exhibits are Item 14, gains no Item 15 from the
    # 'Exhibits?' pattern that already sat under part_iv_item_15.
    report = _without_legacy(TenK)(FixtureFiling(GATE_1999, "10-K"))
    assert "Item 15" not in report.items


def test_a_sub_designated_marker_is_not_a_section_start():
    """What the boundary test excludes, and what it must keep.

    The whole string must be an item number plus parenthesized sub-designations:
    a designated item header carries a title and stays a boundary, and so does a
    bare undesignated "Item 3.", the shape 20-F headings commonly use.
    """
    for text in ["Item 14(a)(1):", "Item 14 (a)(2):", "Item 14 (a)(3):",
                 "ITEM 14(A)(1)", "Item 9(b).", "Item 1122(d)"]:
        assert _ITEM_SUBHEADER.match(text), f"{text!r} should read as a sub-header"

    for text in ["ITEM 9A(T). CONTROLS AND PROCEDURES", "Item 3.", "Item 4",
                 "Item 14: Exhibits, Financial Statement Schedules",
                 "Item 1112(b) of Regulation AB. Significant Obligors",
                 "PART IV", "SIGNATURES"]:
        assert not _ITEM_SUBHEADER.match(text), f"{text!r} must stay a boundary"


def test_the_sub_headers_are_still_found_as_candidates(doc_1999):
    """Excluded as *boundaries*, not removed from detection.

    They remain candidates — the change is confined to what may close a section,
    so nothing that depends on the candidate list changes shape.
    """
    headers = SectionExtractor(form="10-K")._find_section_headers(doc_1999)
    subs = [t.strip() for _n, t, _p in headers
            if re.match(r"^Item\s+14\s*\(a\)", t.strip(), re.IGNORECASE)]
    assert subs == ["Item 14(a)(1):", "Item 14 (a)(2):", "Item 14 (a)(3):"]
