"""`.items` no longer consults the legacy parser — and `__getitem__` still does.

edgartools-07lk.23. Two halves, and the second matters as much as the first.

**What was deleted.** `TenK.items`, `TenQ.items` and `TwentyF.items` each ended
with a fallback to the legacy ``ChunkedDocument`` for filings where the new
parser found nothing. Strategy 5c (edgartools-3dp) closed the last case that
needed one, and measurement across the 115-fixture era-stratified corpus put the
difference at zero filings for all four report forms. The fallbacks are gone.

**What was NOT deleted, and why this file says so out loud.** The same measurement
found the fallbacks in ``__getitem__`` and ``get_item_with_part`` are very much
alive: 15 item lookups and 4 part-qualified lookups across the corpus return real
text only because legacy is still there. (Eight of the fifteen closed on
2026-08-21 with edgartools-dt1f.1 — see ``TestGetitemFallbackIsStillWired`` below —
leaving seven and the four.) The two are not the same question, and the reason is
structural rather than incidental —

    ``.items``       consults legacy only when the new parser found NOTHING
    ``__getitem__``  consults legacy whenever THIS ONE item is missing

— so a *partial* detection miss reaches the second and never the first. A filing
whose Items 1-13 parse cleanly and whose Item 14 does not will never trigger the
``.items`` fallback, and will always trigger the ``__getitem__`` one. Zero
difference on the first therefore implies nothing whatever about the second.

The planning note for this work described it as deleting "the now-dead
``_chunked_document`` fallbacks" from four classes and dropping four
``edgar.files`` importers. That was measured and is not accurate: only the
``.items`` third of it is dead, and because ``__getitem__`` still imports
``ChunkedDocument`` no importer is dropped at all. The live half is pinned below
so the next person to read that note finds evidence instead of repeating it.
"""
import pathlib

import pytest

from edgar.company_reports.ten_k import TenK
from edgar.company_reports.twenty_f import TwentyF

FIXTURES = pathlib.Path(__file__).parent.parent.parent / "fixtures"
# Both tracked, so these assertions run in CI. The corpus this was measured on is
# mostly gitignored (text_boundary_corpus, 91 MB); anchoring on that alone would
# make the whole file skip in CI while passing locally, which is how parity
# evidence has been lost here before.
GATE_10K = FIXTURES / "parity_gate" / "10-K" / "0000950153-99-001234.html"
GATE_20F = FIXTURES / "parity_gate" / "20-F" / "0001062993-16-008650.html"


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
    """A subclass whose legacy fallback is unavailable.

    Deliberately a throwaway subclass rather than patching and deleting the
    attribute on ``cls``: TenK, TenQ and CurrentReport each define
    ``_chunked_document`` on themselves, so ``del cls._chunked_document`` would
    destroy the real override instead of restoring it, and every later assertion
    in the session would silently measure a different object.
    """
    return type(
        f"NoLegacy{cls.__name__}",
        (cls,),
        {"_chunked_document": property(lambda self: None)},
    )


def test_the_tracked_fixtures_are_present():
    """Absent is not passing — guard the fixtures the assertions rest on."""
    for path in (GATE_10K, GATE_20F):
        assert path.exists(), f"{path} is tracked and must be present"


class TestItemsNoLongerNeedsLegacy:
    """The deleted half: `.items` is identical with and without the fallback."""

    def test_tenk_items_unchanged_without_legacy(self):
        filing = FixtureFiling(GATE_10K, "10-K")
        assert TenK(filing).items == _without_legacy(TenK)(filing).items

    def test_twentyf_items_unchanged_without_legacy(self):
        filing = FixtureFiling(GATE_20F, "20-F")
        assert TwentyF(filing).items == _without_legacy(TwentyF)(filing).items

    def test_items_is_a_list_when_nothing_is_found(self):
        """Not None — `for item in report.items` must stay safe now that the
        fallback that used to backstop an empty result is gone."""

        class Empty(TenK):
            @property
            def sections(self):
                return {}

        empty = _without_legacy(Empty)(FixtureFiling(GATE_10K, "10-K"))
        assert empty.items == []


class TestGetitemFallbackIsStillWired:
    """The half that was NOT deleted, pinned as live rather than asserted dead.

    If a later change to the pattern extractor makes these pass without legacy,
    that is good news and this class should be revisited — but it has to be
    *observed*, not assumed. Failing here means the fallback stopped being
    load-bearing, so re-measure and then delete it deliberately.

    That is what happened on 2026-08-21, and it is why the 20-F case that used to
    sit here is gone: edgartools-dt1f.1 closed eight of the fifteen lookups —
    this filing's Items 6 and 11, 10-K Item 7A, and five on the 2010 20-F — by
    normalizing the source's line wrapping out of header text before matching.
    They are asserted from the other side now, in
    ``test_dt1f1_wrapped_item_headers.py``. Two more — Items 5 and 6 on gs/10q —
    closed on 2026-08-22 when Strategy 3b was allowed to recover a 10-Q's Part II
    boundary, and are asserted in ``test_dt1f1_10q_part_boundary.py``.

    Item 9A on 0001193125-10-073212 closed on the same day, once the item
    separator was taught that "ITEM 9A(T)" carries a designation rather than a
    stray parenthesis (``test_dt1f1_item_9at.py``).

    Items 4 and 14 on this filing closed on 2026-08-22 as well, when the 10-K
    vocabulary gained the titles those items carried before the 2011 and 2003
    renumberings. They used to be parametrized here, asserted as reachable only
    through legacy; they are asserted from the other side now, in
    ``test_dt1f1_era_item_titles.py``.

    ONE remains: Item 5 on 0001376474-16-000635, whose bold all-caps header
    scores below the header-detection threshold because its canonical title runs
    past ten words. Its filing lives in the gitignored era corpus, so the
    load-bearing claim can no longer be demonstrated on a TRACKED fixture — which
    is what this class is now named for. What it pins instead is the wiring: a
    missing item still reaches the fallback, and TenK dereferences it unguarded
    where TwentyF returns None, the difference 07lk.3 has to handle at both call
    sites.

    One and not two: Item 11 on 0001193125-21-101193 was listed here and was
    DROPPED on 2026-08-22 rather than fixed, because the new parser is right and
    legacy is wrong. That filing is an asset-backed issuer 10-K on Regulation AB
    numbering (Items 1112, 1114(b), 1122, 1123), and ABS filers omit the Part III
    items — the only bare "Item 11" in the document is a table-of-contents row.
    The 2,250 characters legacy returned begin "Item 1112(b) of Regulation AB.
    Significant Obligors of Pool Assets": it prefix-matched a longer item number.
    Returning nothing is the correct answer there, so it is not evidence that the
    fallback is load-bearing and must not be counted as a lookup to close.
    """

    @pytest.mark.parametrize("item,least", [("Item 14", 5000), ("Item 4", 100)])
    def test_1999_tenk_items_no_longer_need_legacy(self, item, least):
        """Formerly the pin; now the completion signal for dt1f.1 Defect A.

        The same two lookups, asserted the other way round: the modern parser
        answers them on its own. Exact character counts live in
        ``test_dt1f1_era_item_titles.py`` — what this keeps is the *shape* of the
        claim this class makes, so the running tally above stays checkable.
        """
        filing = FixtureFiling(GATE_10K, "10-K")

        text = _without_legacy(TenK)(filing)[item]
        assert text and len(text) > least, (
            f"{item} should now come from edgar.documents with no legacy fallback"
        )

    def test_a_missing_item_still_reaches_the_fallback(self):
        """The wiring, on an item the filing genuinely does not have.

        A 1999 10-K has no Item 16 — Form 10-K Summary was added in 2016 — so the
        lookup falls through the new parser and the cross-reference index to
        ``ChunkedDocument``. TenK dereferences it unguarded and therefore raises
        once it is None; TwentyF guards and returns None. Both call sites are
        deleted by 07lk.3, and they do not behave the same way, which is the part
        worth pinning now that no tracked fixture can show the fallback returning
        real text.
        """
        with pytest.raises(TypeError):
            _without_legacy(TenK)(FixtureFiling(GATE_10K, "10-K"))["Item 16"]

        assert _without_legacy(TwentyF)(FixtureFiling(GATE_20F, "20-F"))["Item 20"] is None
