"""Regression test for the "Citi HTML leakage" half of GH #821 (bead edgartools-sldz,
mechanism recorded on edgartools-llmp.6.4).

Bug:
    TenK.__getitem__ prefers the Cross Reference Index when a filing has one
    (edgar/company_reports/ten_k.py, "prefer it over chunked_document"). That
    branch returned CrossReferenceIndex.extract_item_content() directly, and
    that method returns HTML by contract — it slices the source document by
    page range. Every other branch of the same method returns text.

    So callers asking for an item got raw markup. On Citigroup's 2024 10-K,
    tenk['Item 1'] returned 1,685,461 characters beginning
    '<div style="min-height:36pt;width:100%">...'.

    It surfaced on Citi specifically because doc.sections yields only four
    non-canonical keys there (mda, risk_factors, financial_statements,
    controls_procedures). Items that coincide with one of those returned clean
    text; Item 1 (Business) has no such section, missed the part_key lookup,
    and fell through to the cross-reference branch.

    The giveaway that this was a bug rather than a contract: the code
    immediately below the return strips a trailing 'PART IV' line using
    text.split("\\n")[-1], which is written for text and silently does nothing
    to markup.

Fix:
    Convert with parse_html(...).text() before the PART-stripping. An empty
    conversion falls through to the legacy fallback rather than returning the
    markup.

Later (edgartools-4agg):
    Citi now resolves 11 canonically-keyed sections from its Cross Reference
    Index, so 'Item 1' is answered by doc.sections['part_i_item_1'] and no
    longer reaches the cross-reference branch at all. The branch is still live
    for filings whose index covers items that section detection does not, so
    the conversion contract is now exercised directly — by emptying the section
    map to force the fall-through — rather than by relying on Citi having no
    section for Item 1.

Offline: drives TenK against the tracked 16.7MB Citi fixture through a minimal
filing stub, so no network is required.
"""
from pathlib import Path

import pytest

from edgar.company_reports import TenK

FIXTURE = Path(__file__).parents[2] / "fixtures" / "html" / "c" / "10k" / "c-10-k-2025-02-21.html"

pytestmark = pytest.mark.skipif(not FIXTURE.exists(),
                                reason="Citigroup 10-K fixture not available")


class _StubFiling:
    """Minimal surface TenK needs: html(), and identifiers used in logging."""
    accession_number = "0000831001-25-000029"
    base_dir = ""
    form = "10-K"
    company = "Citigroup Inc."
    cik = 831001
    filing_date = "2025-02-21"

    def __init__(self, html: str):
        self._html = html

    def html(self) -> str:
        return self._html


@pytest.fixture(scope="module")
def citi_tenk():
    return TenK(_StubFiling(FIXTURE.read_text(encoding="utf-8")))


class TestCitiItemsAreTextNotHtml:

    def test_cross_reference_index_is_still_detected(self, citi_tenk):
        """Guard against a vacuous pass.

        If Citi ever stops being detected as a Cross Reference Index filing,
        every assertion below would hold for a reason unrelated to this bug.

        Detection alone is not the precondition, though: the branch under test
        slices the document BY PAGE RANGE, so what has to hold is that the
        index parses to entries and that Item 1 — the item that leaked markup —
        carries page ranges to slice. An index that is detected but parses to
        nothing would satisfy `is not None` and still leave the test below
        passing for an unrelated reason.
        """
        index = citi_tenk._cross_reference_index
        assert index is not None, \
            "Citi is no longer detected as a Cross Reference Index filing"

        # Read off the tracked fixture, which is a fixed 2024 10-K and so does
        # not move: 22 items, Part I through Part IV.
        entries = index.parse()
        assert len(entries) == 22, f"index parsed {len(entries)} items, expected 22"

        item1 = entries['1']
        assert item1.item_title == 'Business'
        assert item1.part == 'Part I'
        assert [str(p) for p in item1.pages] == \
            ['4-32', '130-135', '137', '169-173', '314-315'], \
            f"Item 1 page ranges are {[str(p) for p in item1.pages]}; with no " \
            "ranges the cross-reference branch has nothing to slice and returns " \
            "nothing at all, markup or otherwise"

    def test_cross_reference_branch_returns_text_not_markup(self, citi_tenk):
        """The #821 fix itself, exercised directly.

        Item 1 no longer reaches this branch (edgartools-4agg gave Citi a real
        part_i_item_1 section), so the section map is emptied to force the
        fall-through. Without the parse_html(...).text() conversion this returns
        ~1.7MB of <div>/<span> markup.
        """
        from edgar.documents.document import Sections

        document = citi_tenk.document
        original = document.sections
        try:
            document._sections = Sections()
            item1 = citi_tenk['Item 1']
        finally:
            document._sections = original

        assert item1, "Item 1 returned nothing via the cross-reference branch"
        # Reduce to a bool before asserting — see the note below.
        leaked_markup = '<div' in item1 or '<span' in item1
        assert not leaked_markup, \
            f"Cross-reference branch returned raw HTML: {item1[:120]!r}"

    def test_item_1_returns_text_not_markup(self, citi_tenk):
        item1 = citi_tenk['Item 1']

        assert item1 is not None, "Item 1 (Business) should not be None"
        # Reduce to a bool before asserting. When this fails the item is ~1.7MB
        # of markup, and pytest's assertion introspection renders the operands —
        # asserting on the string directly turns a failure into a multi-minute
        # hang instead of a test report.
        leaked_markup = '<div' in item1 or '<span' in item1
        assert not leaked_markup, f"Item 1 returned raw HTML: {item1[:120]!r}"

    def test_item_1_carries_the_business_narrative(self, citi_tenk):
        """Ground truth, hand-checked against the filing.

        Length alone would not catch the bug — the HTML was 1.68M characters,
        far longer than the correct text — so assert on content that only the
        Business section contains.
        """
        item1 = citi_tenk['Item 1']

        # Bools first — see the note in test_item_1_returns_text_not_markup.
        has_narrative = ("Citigroup's history dates back to the founding of the City B" in item1
                         or "Citigroup’s history dates back to the founding of the City B" in item1)
        assert has_narrative, "Item 1 does not open on Citi's Business narrative"

        starts_at_overview = item1.lstrip().startswith('OVERVIEW')
        assert starts_at_overview, \
            f"Item 1 should begin at the Business overview, got {item1[:60]!r}"

    @pytest.mark.parametrize("item", ["Item 1", "Item 1A", "Item 7", "Item 8"])
    def test_no_item_leaks_markup(self, citi_tenk, item):
        """The other items resolved from doc.sections and were already text.
        They are included so a future change that routes them through the
        cross-reference branch cannot regress them silently."""
        value = citi_tenk[item]

        assert value, f"{item} returned nothing"
        leaked_markup = '<div' in value or '<span' in value
        assert not leaked_markup, f"{item} returned raw HTML: {value[:120]!r}"
