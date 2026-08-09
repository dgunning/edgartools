"""Regression tests for edgartools-4agg — Citigroup and Wells Fargo 10-K item recovery.

Two filings that every anchor-driven strategy failed on, for two unrelated
structural reasons. The issue had folded them together as one "label-less /
link-less" class; they are not.

CITIGROUP (16.7MB, no anchors, two "Item N" strings in the whole document)
    Citi publishes a "FORM 10-K CROSS-REFERENCE INDEX" mapping each item to
    printed page ranges. ``_find_index_table()`` anchored on the heading and
    returned everything up to the FIRST ``</table>``. Citi's index has a page
    break after Item 9A, so the filer opened a second ``<table>`` for 9B onward
    and the parse stopped at 14 of 22 items — silently losing 9B, 9C and all of
    Part III. Two further defects were hidden behind that early stop:

      * ``^Part\\s+(I+|IV)`` let ``I+`` claim the leading "I" of "Part IV", so
        Item 15 was labelled Part I.
      * ``PageRange.parse`` fed "319-321*" to ``int()``, raised, and discarded
        the whole range — Item 10 lost its pages to a footnote marker.

    Separately, the index was parsed but never used to build sections, so
    ``document.sections`` held four non-canonical keys from keyword matching
    (``mda``, ``risk_factors``, ...) and a caller asking for ``part_ii_item_7``
    got nothing while ``mda`` quietly held the MD&A.

WELLS FARGO (1.6MB, no cross-reference index at all)
    Every item heading is a standalone one-row table, ``ITEM 1A. | RISK
    FACTORS``. The parser classifies that lone row as the table's *header* row,
    so it lands in ``TableNode.headers`` and leaves ``.rows`` empty — and the
    pattern extractor's table strategy only scanned ``.rows``. With no item
    headers found anywhere, matching fell through to bare-title keywords and
    published Item 15's exhibit list under ``financial_statements``: the wrong
    content under the wrong key, which is worse than the honest silence the
    issue assumed. Item 8 is a 261-char "incorporated by reference" pointer,
    so ranking candidates by content size let 42K of exhibit list win.

Offline: both filings are tracked fixtures; no network required.

Fixtures are module-scoped (Citi takes ~4s to parse and eight tests share it) but are
released explicitly at teardown. Citi is 16.7MB of source plus a parsed tree, and
tests/issues/regression/test_issue_821_citi_html_leak.py already holds one copy;
letting a second stay resident for the rest of the session pushed
test_issue_wbwn_table_matrix_quadratic's ratio check — which times a 1000-row
baseline against a 4000-row build — over its threshold through GC pressure alone.
"""
import gc
from pathlib import Path

import pytest

from edgar.documents import parse_html
from edgar.documents.config import ParserConfig
from edgar.documents.cross_reference_index import CrossReferenceIndex

FIXTURES = Path(__file__).parents[2] / "fixtures" / "html"
CITI = FIXTURES / "c" / "10k" / "c-10-k-2025-02-21.html"
WFC = FIXTURES / "wfc" / "10k" / "wfc-10-k-2025-02-25.html"

pytestmark = pytest.mark.fast


@pytest.fixture(scope="module")
def citi_html():
    assert CITI.exists(), f"committed Citigroup 10-K fixture is missing: {CITI}"
    html = CITI.read_text(encoding="utf-8", errors="replace")
    yield html
    del html
    gc.collect()


@pytest.fixture(scope="module")
def wfc_html():
    assert WFC.exists(), f"committed Wells Fargo 10-K fixture is missing: {WFC}"
    html = WFC.read_text(encoding="utf-8", errors="replace")
    yield html
    del html
    gc.collect()


@pytest.fixture(scope="module")
def citi_sections(citi_html):
    document = parse_html(citi_html, ParserConfig(form="10-K"))
    yield document.sections
    del document
    gc.collect()


@pytest.fixture(scope="module")
def wfc_sections(wfc_html):
    document = parse_html(wfc_html, ParserConfig(form="10-K"))
    yield document.sections
    del document
    gc.collect()


class TestCitiCrossReferenceIndexSpansTables:
    """The index parse must not stop at the page break after Item 9A."""

    def test_all_22_items_parse(self, citi_html):
        entries = CrossReferenceIndex(citi_html).parse()

        # Ground truth: hand-counted from the filing's own index, which runs
        # 1 through 15 across Parts I-IV. Reading only the first table gave 14.
        assert len(entries) == 22, f"expected 22 index entries, got {len(entries)}"
        assert set(entries) == {
            "1", "1A", "1B", "1C", "2", "3", "4",
            "5", "6", "7", "7A", "8", "9", "9A", "9B", "9C",
            "10", "11", "12", "13", "14", "15",
        }

    def test_items_past_the_page_break_are_present(self, citi_html):
        """9B onward live in the second table — the half that used to be lost."""
        entries = CrossReferenceIndex(citi_html).parse()

        assert entries["9B"].item_title == "Other Information"
        assert [str(p) for p in entries["9B"].pages] == ["317"]
        assert entries["12"].part == "Part III"

    def test_part_iv_is_not_labelled_part_i(self, citi_html):
        """`I+` used to win the alternation and swallow the "I" of "Part IV"."""
        entries = CrossReferenceIndex(citi_html).parse()

        assert entries["15"].part == "Part IV"

    def test_footnote_marker_does_not_discard_the_page_range(self, citi_html):
        """Item 10's cell reads "319-321*" — the pages are real, the * is a note."""
        entries = CrossReferenceIndex(citi_html).parse()

        assert [str(p) for p in entries["10"].pages] == ["319-321"]

    def test_marker_only_cells_yield_no_pages(self, citi_html):
        """Items 11-14 carry only asterisks (incorporated by reference from the
        proxy), and 1B/2/4/9/9C read "Not Applicable". Neither is a page range."""
        entries = CrossReferenceIndex(citi_html).parse()

        for item in ("11", "12", "13", "14", "1B", "2", "4", "9", "9C"):
            assert entries[item].pages == [], f"Item {item} should have no pages"


class TestCitiSectionsAreCanonical:
    """The index must reach document.sections, not just the parser."""

    def test_sections_use_canonical_keys(self, citi_sections):
        assert len(citi_sections) == 11, f"got {sorted(citi_sections)}"
        # Previously: mda / risk_factors / financial_statements / controls_procedures.
        assert "part_ii_item_7" in citi_sections
        assert "part_ii_item_8" in citi_sections
        assert "mda" not in citi_sections

    def test_sections_carry_part_and_item_metadata(self, citi_sections):
        section = citi_sections["part_ii_item_7"]

        assert section.part == "II"
        assert section.item == "7"
        assert section.detection_method == "index"

    def test_item_7_is_the_mda(self, citi_sections):
        """Ground truth: MD&A is cited at pages 7-32 and 70-129 and opens on its
        own title. The keyword fallback previously returned 234,483 chars under
        `mda`; the filer's own range yields the full 473,576."""
        text = citi_sections["part_ii_item_7"].text()

        assert text.lstrip().startswith("MANAGEMENT"), f"got {text[:80]!r}"
        assert "EXECUTIVE SUMMARY" in text[:2000]
        assert len(text) > 400_000

    def test_item_8_is_the_financial_statements(self, citi_sections):
        text = citi_sections["part_ii_item_8"].text()

        assert text.lstrip().startswith("CONSOLIDATED BALANCE SHEET"), f"got {text[:80]!r}"

    def test_item_1a_is_the_risk_factors(self, citi_sections):
        text = citi_sections["part_i_item_1a"].text()

        assert text.lstrip().startswith("RISK FACTORS"), f"got {text[:80]!r}"

    def test_items_without_pages_produce_no_section(self, citi_sections):
        """Silence check.

        "Not Applicable" (1B, 2, 4, 9, 9C) and asterisked incorporation by
        reference (11-14) mean there is no disclosure in THIS document. Emitting
        an empty section would present absence as content, so the map omits them
        — and omission here is a positive result, not a detection failure.
        """
        for item, part in (("1b", "i"), ("2", "i"), ("4", "i"),
                           ("9", "ii"), ("9c", "ii"),
                           ("11", "iii"), ("12", "iii"), ("13", "iii"), ("14", "iii")):
            key = f"part_{part}_item_{item}"
            assert key not in citi_sections, f"{key} has no page range and should not be a section"

    @pytest.mark.xfail(
        reason="Citi's own index cites pages 135-136 for Item 9A, but the "
               "Controls and Procedures content is on page 134 (135 is "
               "Forward-Looking Statements, 136 the auditor's report). The folio "
               "map is exact (329/330 recovered, offset uniformly -1, zero "
               "outliers), so this is the filer mis-citing, not map drift. "
               "Snapping to the nearest matching heading is deliberately left to "
               "edgartools-llmp.6.6 (low-confidence section signaling) rather "
               "than added as a lone heuristic here.",
        strict=True,
    )
    def test_item_9a_is_controls_and_procedures(self, citi_sections):
        text = citi_sections["part_ii_item_9a"].text()

        assert "MANAGEMENT" in text[:200] and "INTERNAL CONTROL" in text[:200]


class TestWellsFargoItemHeadingTables:
    """One-row `ITEM N. | TITLE` tables must be recognised as item headings."""

    def test_every_item_is_detected(self, wfc_sections):
        # Ground truth: WFC's 10-K runs Item 1 through Item 16 with 1A, 1B, 1C,
        # 7A, 9A, 9B, 9C — 23 items, each its own one-row heading table.
        assert len(wfc_sections) == 23, f"got {sorted(wfc_sections)}"

    def test_item_8_is_the_incorporation_pointer_not_the_exhibit_list(self, wfc_sections):
        """The core data-correctness bug.

        WFC incorporates its financial statements from the 2024 Annual Report,
        so Item 8 is a short pointer. The previous output published 42,462 chars
        of Item 15's exhibit list under this key.
        """
        section = wfc_sections["financial_statements"]

        assert section.item == "8"
        text = section.text()
        assert "incorporated into this item by reference" in text
        assert "2024 Annual Report to Shareholders" in text
        # The exhibit list is ~42K; the pointer plus boundary text is far shorter.
        assert len(text) < 10_000, f"Item 8 is {len(text)} chars — exhibit list leaked back in"

    def test_exhibit_list_lives_under_item_15(self, wfc_sections):
        section = wfc_sections["part_iv_item_15"]

        assert section.item == "15"
        assert section.part == "IV"
        text = section.text()
        assert "FINANCIAL STATEMENTS" in text
        assert len(text) > 30_000, "Item 15 should hold the full exhibit list"

    def test_items_that_had_no_vocabulary_entry_are_recovered(self, wfc_sections):
        """Items 4, 5, 6, 9, 9B, 9C and 15 had no pattern in the 10-K schema at
        all, so on a filing whose only usable headers are "Item N" markers they
        were unrecoverable and their content was absorbed by the item before."""
        for key in ("part_i_item_4", "part_ii_item_5", "part_ii_item_6",
                    "part_ii_item_9", "part_ii_item_9b", "part_ii_item_9c",
                    "part_iv_item_15"):
            assert key in wfc_sections, f"{key} missing"

    def test_every_section_opens_on_its_own_item_heading(self, wfc_sections):
        """Each item's text must start at that item's heading — the property the
        one-row-table recognition buys, and the one that fails loudly if header
        rows stop being scanned."""
        for key, section in wfc_sections.items():
            if not section.item:
                continue
            text = section.text().lstrip()
            expected = f"ITEM {section.item.upper()}."
            assert text.startswith(expected), \
                f"{key} starts {text[:60]!r}, expected to open on {expected!r}"

    def test_wfc_has_no_cross_reference_index(self, wfc_html):
        """Guard against a vacuous pass: WFC must be fixed by the table-heading
        path, not by accidentally acquiring Citi's index path."""
        assert CrossReferenceIndex(wfc_html).has_index() is False
