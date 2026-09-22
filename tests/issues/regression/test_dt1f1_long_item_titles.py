"""A long item title is still an item title (edgartools-dt1f.1, Defect C).

``ContextualDetector._looks_like_header`` refuses to call anything longer than
fifteen words a header. That is a fair proxy for unlabelled text and an unfair
one for labelled text, because several of the SEC's own canonical item titles
run past fifteen words — Item 5's

    Market for Registrant's Common Equity, Related Stockholder Matters and
    Issuer Purchases of Equity Securities

is seventeen. The cap therefore rejected precisely the longest *real* headers,
and on ``0001376474-16-000635`` Item 5 was the one item of twenty that never
became a heading. ``tenk["Item 5"]`` returned text only because the legacy
``ChunkedDocument`` fallback was still wired in — the last of the fifteen
``__getitem__`` lookups dt1f.1 set out to close.

WHY THIS DETECTOR AND NOT ANOTHER. The bead recorded this as a *style* defect:
bold scoring +0.3, all-caps +0.2 but only at ten words or fewer, against a 0.4
threshold. Instrumenting the real pipeline says otherwise, and the difference
matters because it is what a fix has to target. The element that gets scored is
the ``<font>``, whose own style carries no weight, so ``style.is_bold`` is False
and ``StyleBasedDetector`` never fires at all — it returns None for Items 4, 5
and 6 alike. The only detector that fires on this filing is the contextual one,
and it lands on exactly 0.600 against a 0.600 threshold for the items that
survive. Item 5 differs from its neighbours in one respect: seventeen words
against five.

WHAT WAS DELIBERATELY NOT FIXED. ``PatternBasedDetector.HEADER_PATTERNS`` spells
its own item separator inline as ``[.\\s]+``, which accepts a period or a space
and nothing else, so "ITEM 5: ..." does not match it either — the same defect
edgartools-dt1f fixed in the section vocabulary, surviving in the one place the
drift guard does not look. Wiring it to ``_ITEM_SEP`` also fixes this filing,
and it was measured and rejected: that pattern carries level 1, so every
colon-separated item header would be promoted from level 3 to level 1, and
``_find_section_end`` only lets a header close a section at its own level or
higher. On the 20-F ``0001104659-16-108848`` that collapsed part_i from 387,410
characters to 6, part_ii from 10,294 to 7 and part_iii from 11,911 to 8. It is
tracked separately (edgartools-orfh) rather than left unrecorded.

BLAST RADIUS, measured across every fixture available on 2026-08-22: one section
added to one filing, and NOTHING else moves on 54 10-K, 31 10-Q, 15 20-F and 15
8-K fixtures. Headings were measured separately, since ``_looks_like_header``
governs ``doc.headings`` and the markdown table of contents as well as section
detection: across 69 10-K and 20-F fixtures the change adds exactly one heading
— this one — and removes none.

CORPUS NOTE. The fixture was copied into ``tests/fixtures/parity_gate/10-K/`` in
the same commit, the way 0000950153-99-001234 and 0001193125-10-073212 were, so
this runs in CI. Its original lives in the gitignored ``text_boundary_corpus``.
"""
import pathlib

import pytest

from edgar.company_reports.ten_k import TenK
from edgar.documents.config import ParserConfig
from edgar.documents.parser import HTMLParser
from edgar.documents.strategies.header_detection import ContextualDetector

FIXTURES = pathlib.Path(__file__).parent.parent.parent / "fixtures"
GATE_10K = FIXTURES / "parity_gate" / "10-K" / "0001376474-16-000635.html"

# The header at the centre of this defect, verbatim from the filing.
ITEM_5_TITLE = (
    "ITEM 5: MARKET FOR THE REGISTRANTS COMMON EQUITY, RELATED STOCKHOLDER "
    "MATTERS AND ISSUER PURCHASES OF EQUITY SECURITIES"
)


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
def doc():
    return HTMLParser(ParserConfig(form="10-K")).parse(
        GATE_10K.read_text(encoding="utf-8", errors="replace")
    )


def test_the_tracked_fixture_is_present():
    """Absent is not passing. This one is tracked, so it must never skip."""
    assert GATE_10K.exists(), (
        f"{GATE_10K} was copied into parity_gate so this regression is visible "
        f"to CI; without it every assertion below is vacuous"
    )


def test_the_title_really_is_over_the_cap():
    """Pin the precondition, in the filing's own words.

    Seventeen words against a fifteen-word cap. If the SEC ever shortened this
    title, or the fixture were replaced, the assertions below would still pass
    while testing nothing.
    """
    assert len(ITEM_5_TITLE.split()) == 17


def test_a_labelled_header_is_not_length_capped():
    """The unit of the fix, at the exact boundary it moved."""
    looks_like_header = ContextualDetector()._looks_like_header

    assert looks_like_header(ITEM_5_TITLE)
    # A Part label is waived too, and case does not matter.
    assert looks_like_header("PART II " + "word " * 20)
    assert looks_like_header("Item 7. " + "word " * 20)

    # Unlabelled text over the cap is still rejected — the cap is waived, not
    # removed, so this stays the ordinary answer for ordinary long text.
    assert not looks_like_header("Some Descriptive Phrase " + "word " * 20)
    # And a labelled *sentence* is still rejected, by the punctuation test the
    # waiver does not touch. This is what keeps prose cross-references out.
    assert not looks_like_header(
        "Item 5 of this report and the discussion under Item 7 are incorporated "
        "herein by reference in their entirety."
    )
    # Short unlabelled headers are unaffected either way.
    assert looks_like_header("SELECTED FINANCIAL DATA")


def test_item_5_is_detected(doc):
    sections = doc.sections

    assert len(sections["part_ii_item_5"].text()) == 10778
    assert sections["part_ii_item_5"].text().startswith("ITEM 5: MARKET FOR")
    assert "There is no public market for the units" in sections["part_ii_item_5"].text()

    # Its neighbours are unchanged — the fix adds a section, it does not re-cut
    # the ones on either side.
    assert len(sections["part_i_item_4"].text()) == 47
    assert len(sections["part_ii_item_6"].text()) == 47
    # And Item 15 in particular, which the rejected pattern-detector fix would
    # have grown from 2,877 characters to 74,793 by promoting item headers to
    # level 1. See the module docstring.
    # 2,877 before edgartools-y0ri. Pure gain: ZERO tokens lost, and the two
    # gained are "(a)" and "(3)" -- exhibit-list labels that lived in a sparsely
    # filled column the scorer had been reading as spacing. Parentheses balance
    # 10 -> 12 and every number is still present in order.
    assert len(sections["part_iv_item_15"].text()) == 2968


def test_the_header_became_a_heading(doc):
    """The section exists because the header was promoted, not by another route."""
    from edgar.documents.nodes import HeadingNode

    headings = [n.text().strip() for n in doc.root.find(lambda n: isinstance(n, HeadingNode))]
    assert ITEM_5_TITLE in headings


def test_item_5_resolves_without_the_legacy_parser():
    """The last of the fifteen __getitem__ lookups on the dt1f.1 work list.

    Legacy returned 13,223 characters against this 10,778. Same span — both
    start at the header and end on "...does not receive a corresponding cash
    distribution." — so the difference is whitespace and table rendering, not a
    boundary.
    """
    report = _without_legacy(TenK)(FixtureFiling(GATE_10K, "10-K"))

    text = report["Item 5"]
    assert len(text) == 10778
    assert len(report["5"]) == 10778  # the short spelling resolves too
    assert text.startswith("ITEM 5: MARKET FOR")
    assert text.rstrip().endswith("does not receive a corresponding cash distribution.")


def test_every_item_legacy_finds_is_now_found():
    """Twenty items, the same twenty the legacy parser lists.

    This filing is the one the item-separator fix (edgartools-dt1f) was measured
    on — before it, ``TenK.items`` was ``['Item 8']`` against legacy's twenty.
    Item 5 was the last one still missing.
    """
    report = _without_legacy(TenK)(FixtureFiling(GATE_10K, "10-K"))

    assert report.items == [
        "Item 1", "Item 1A", "Item 1B", "Item 2", "Item 3", "Item 4", "Item 5",
        "Item 6", "Item 7", "Item 7A", "Item 8", "Item 9", "Item 9A", "Item 9B",
        "Item 10", "Item 11", "Item 12", "Item 13", "Item 14", "Item 15",
    ]
