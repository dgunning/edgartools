"""Item 9A(T) is an item number, not an unmatchable one (edgartools-dt1f.1, Defect B).

Between roughly 2007 and 2010 a smaller reporting company filed its
internal-control report under the SEC's transitional designation, writing the
header as::

    ITEM 9A(T).  CONTROLS AND PROCEDURES

The 10-K pattern for that section is ``^(Item|ITEM)\\s+9A`` followed by the item
separator and then ``Controls.*Procedures``. The separator's punctuation class
held ``.``, ``:``, ``;`` and the dashes — not ``(`` — so the match died
immediately after the ``9A`` and no ``controls_procedures`` section was created.
The header was never missing: it is right there in the candidate list as a
``TableNode``, and it was discarded at match time.

``tenk["Item 9A"]`` therefore returned text only because the legacy
``ChunkedDocument`` fallback was still wired in, which is what dt1f.1 has to
close before ``edgar.files`` can go.

WHERE THE FIX LIVES, AND WHY THERE. ``_ITEM_SEP`` in ``edgar/documents/form_schema.py``
is the single definition of what a filer may put between an item number and its
title, and an existing drift guard (``test_dt1f_item_separator.py``) requires
every item-numbered pattern in all three item-based forms to be built from it. So
the designation is one optional group in one constant, and 10-K, 10-Q and 20-F
all get it without a second author's opinion about which punctuation counts.

One letter only. A Regulation AB number like "Item 1112(b)" must not read as item
11 carrying a designation — though the title each pattern requires next already
rules that out on its own, which is why the ABS filing 0001193125-21-101193 does
not gain a spurious Item 11 from this change (it is asserted below, because that
filing is the reason one lookup was retired from this bead rather than fixed).

BLAST RADIUS, measured across every fixture available on 2026-08-22: this adds
one section to one filing and changes nothing else on 55 10-K, 31 10-Q and 18
20-F filings.

CORPUS NOTE. The fixture was copied into ``tests/fixtures/parity_gate/10-K/`` in
the same commit, the way 0000950153-99-001234 was for the separator fix, so this
test runs in CI. Its original lives in ``tests/fixtures/text_boundary_corpus/``,
which is gitignored — anchoring there would have left the only evidence for a
whole cohort of filings invisible to CI. ``build_corpus`` measures the tracked
copy and skips the era one, so the two can never disagree.
"""
import pathlib
import re

import pytest

from edgar.company_reports.ten_k import TenK
from edgar.documents.config import ParserConfig
from edgar.documents.extractors.pattern_section_extractor import SectionExtractor
from edgar.documents.form_schema import _ITEM_SEP
from edgar.documents.parser import HTMLParser

FIXTURES = pathlib.Path(__file__).parent.parent.parent / "fixtures"
GATE_10K = FIXTURES / "parity_gate" / "10-K" / "0001193125-10-073212.html"
ABS_10K = (FIXTURES / "text_boundary_corpus" / "e5_2020_2026" / "10-K"
           / "0001193125-21-101193.html")


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


def test_the_tracked_fixture_is_present():
    """Absent is not passing. This one is tracked, so it must never skip."""
    assert GATE_10K.exists(), (
        f"{GATE_10K} was copied into parity_gate so this regression is visible "
        f"to CI; without it every assertion below is vacuous"
    )


def test_the_header_really_is_written_9at():
    """Pin the precondition.

    The header is found and then discarded — that is the whole shape of this
    defect. If a future change stops emitting this candidate, the assertions
    below would still pass while testing something else entirely.
    """
    doc = HTMLParser(ParserConfig(form="10-K")).parse(
        GATE_10K.read_text(encoding="utf-8", errors="replace")
    )
    headers = SectionExtractor(form="10-K")._find_section_headers(doc)
    matches = [t.strip() for _n, t, _p in headers
               if re.match(r"^\s*ITEM\s+9A\(T\)", t.strip(), re.IGNORECASE)]
    assert matches == ["ITEM 9A(T). CONTROLS AND PROCEDURES"]


def test_the_9at_section_is_detected():
    doc = HTMLParser(ParserConfig(form="10-K")).parse(
        GATE_10K.read_text(encoding="utf-8", errors="replace")
    )
    section = doc.sections["controls_procedures"]

    assert len(section.text()) == 2142
    assert section.text().startswith("ITEM 9A(T).")
    # Its neighbours are unchanged — the fix adds a section, it does not
    # re-cut the ones on either side.
    assert len(doc.sections["part_ii_item_9"].text()) == 2236
    assert len(doc.sections["part_ii_item_9b"].text()) == 78


def test_item_9a_resolves_without_the_legacy_parser():
    """The lookup on the dt1f.1 work list. Legacy returned 2,136 characters."""
    report = _without_legacy(TenK)(FixtureFiling(GATE_10K, "10-K"))

    assert len(report["Item 9A"]) == 2142
    assert len(report["9A"]) == 2142  # the short spelling resolves too
    assert "Item 9A" in report.items


def test_the_designation_is_one_letter_and_optional():
    """The separator still accepts everything it did, and not much more.

    ``test_dt1f_item_separator.py`` holds the general drift guard; these are the
    cases specific to the designation slot, including the one that would matter
    if it were widened to ``\\(\\w+\\)``.
    """
    # The designation, with and without a space, and with either case.
    for spelling in ["(T).", "(t).", " (T).", "(T)"]:
        assert re.fullmatch(_ITEM_SEP, spelling), f"_ITEM_SEP rejects {spelling!r}"
    # Everything the separator accepted before is untouched.
    for spelling in [".", ":", " -", " —", "", ". "]:
        assert re.fullmatch(_ITEM_SEP, spelling), f"_ITEM_SEP rejects {spelling!r}"
    # Not a multi-character parenthetical: "(b)" is one letter and allowed, but
    # a Regulation AB sub-number is not a designation.
    assert not re.fullmatch(_ITEM_SEP, "(12).")
    assert not re.fullmatch(_ITEM_SEP, "(iii).")
    # And it stays a separator rather than swallowing the title.
    assert not re.fullmatch(_ITEM_SEP, "(T). Controls and Procedures")


@pytest.mark.skipif(
    not ABS_10K.exists(),
    reason="text_boundary_corpus is gitignored; present on developer machines only",
)
def test_a_regulation_ab_sub_number_does_not_become_an_item():
    """The asset-backed issuer filing must not gain items from this change.

    Its numbering is Reg AB — Items 1112(b), 1114(b), 1122, 1123 — and the
    parenthesis in "Item 1112(b)" is the shape the designation slot now accepts.
    It cannot match anyway, because ``\\s+11`` is followed by "12" rather than by
    the separator, and because every pattern demands its title next. Legacy's
    prefix match on that number is exactly why the Item 11 lookup was retired
    from dt1f.1 instead of fixed, so it is worth pinning that the modern parser
    still declines to invent one.
    """
    report = _without_legacy(TenK)(FixtureFiling(ABS_10K, "10-K"))
    assert "Item 11" not in report.items
