"""
Tests for 10-Q TenQ post-process suppression of fabricated section keys.

Bug: TOCAnalyzer occasionally fabricates `part_i_item_8` (or other
out-of-form-structure items) from page-number cells in TOC tables.
Real example: PPG Industries 10-Q `0000079879-26-000170` (filed
2026-04-29) — `TenQ.items` returns `Part I, Item 8` containing 96 KB
of Notes-to-Financial-Statements content, even though the SEC 10-Q
form has no Item 8 in either Part.

Root cause is in `edgar/documents/utils/toc_analyzer.py:761` — bare
item-number regex `^([1-9]|1[0-5])([A-Z]?)$` not form-aware. This PR
takes a post-process approach inside `TenQ` rather than restructuring
the TOC analyzer.

Fix:
- edgar/company_reports/ten_q.py:
  - `_is_valid_10q_section_key`: consults `TenQ.structure` (the SEC
    form definition) to decide whether a section key is legitimate.
  - `_fabricated_section_texts_for_part`: gathers the text of any
    fabricated section keys per Part.
  - `_section_text_with_merge`: appends fabricated content to the
    same-Part Item 1's text (preserves content; the most common
    fabrication mode is Notes-to-Financial-Statements page references,
    which semantically belong under Part I, Item 1).
  - `items`: filters fabricated keys from the returned list.
  - `__getitem__` / `get_item_with_part`: route through the merge
    helper, so Item 1 retrievals include preserved content.

Test cases cover:
- `_is_valid_10q_section_key` returns the right verdict against
  TenQ.structure.
- `items` filters fabricated keys end-to-end.
- `__getitem__("Part I, Item 1")` includes merged content from
  fabricated keys.
- Backward-compat: legitimate items still resolve unchanged.
"""
from typing import Dict, Optional
from unittest.mock import patch

import pytest


# Lightweight stand-ins for Section + Filing so we can exercise TenQ logic
# without touching the network or constructing full Document objects.

class _FakeSection:
    def __init__(self, text: str, *, part=None, item=None, title="", detection_method="toc"):
        self._text = text
        self.part = part
        self.item = item
        self.title = title
        self.detection_method = detection_method

    def text(self) -> str:
        return self._text


class _FakeHeader:
    period_of_report = None


class _FakeFiling:
    form = "10-Q"
    accession_number = "0000000000-00-000000"
    filing_date = None
    company = "Test Co"
    base_dir = None
    header = _FakeHeader()
    attachments: list = []

    def html(self):
        return ""


def _make_tenq(sections: Dict[str, _FakeSection]):
    """Build a TenQ instance whose .sections returns the given dict."""
    from edgar.company_reports.ten_q import TenQ

    tenq = TenQ.__new__(TenQ)
    tenq._filing = _FakeFiling()
    tenq._parser = None
    # Bypass cached_property by injecting a fake document
    fake_doc = type("FakeDoc", (), {"sections": sections})()
    tenq.__dict__["document"] = fake_doc
    tenq.__dict__["chunked_document"] = None
    return tenq


# ---------------------------------------------------------------------------
# _is_valid_10q_section_key
# ---------------------------------------------------------------------------

class TestIsValid10qSectionKey:
    """The "valid" predicate is whether a key should be kept in `items`.

    For fabricated keys, the answer depends on whether a same-Part Item 1
    sibling exists (the merge target). To make these tests deterministic
    we set up sections that include BOTH Part I Item 1 and Part II Item 1,
    so any fabricated key has a valid sibling and should be filtered.
    The separate "no Item 1 sibling" path is tested below.
    """

    @pytest.fixture
    def tenq(self):
        return _make_tenq({
            'part_i_item_1': _FakeSection("Item 1 body", part='I', item='1'),
            'part_ii_item_1': _FakeSection("Item 1 body", part='II', item='1'),
        })

    def test_valid_part_i_items(self, tenq):
        for key in ('part_i_item_1', 'part_i_item_2', 'part_i_item_3', 'part_i_item_4'):
            assert tenq._is_valid_10q_section_key(key), f"{key} should be valid"

    def test_invalid_part_i_items(self, tenq):
        for key in ('part_i_item_5', 'part_i_item_6', 'part_i_item_7',
                    'part_i_item_8', 'part_i_item_9', 'part_i_item_1a'):
            assert not tenq._is_valid_10q_section_key(key), (
                f"{key} should be filtered when Item 1 sibling exists"
            )

    def test_valid_part_ii_items(self, tenq):
        for key in ('part_ii_item_1', 'part_ii_item_1a', 'part_ii_item_2',
                    'part_ii_item_3', 'part_ii_item_4', 'part_ii_item_5',
                    'part_ii_item_6'):
            assert tenq._is_valid_10q_section_key(key), f"{key} should be valid"

    def test_invalid_part_ii_items(self, tenq):
        for key in ('part_ii_item_7', 'part_ii_item_8', 'part_ii_item_1b'):
            assert not tenq._is_valid_10q_section_key(key), (
                f"{key} should be filtered when Item 1 sibling exists"
            )

    def test_non_part_keys_passthrough(self, tenq):
        """TOC-based keys not prefixed with `part_` are not filtered."""
        for key in ('item_1', 'Item 1', 'Item 1A', 'business', 'cybersecurity'):
            assert tenq._is_valid_10q_section_key(key), f"{key} should be considered valid"

    def test_fabricated_key_kept_when_no_item_1_sibling(self):
        """Real JPM regression case: `part_i_item_1` is missing from
        sections but `part_i_item_8` exists with the only Financial
        Statements content. Filtering would lose the content with no
        merge target — keep the fabricated key visible instead.

        Filing: JPM 10-Q `0001628280-26-029344` (filed 2026-05) — its
        sections dict has no `part_i_item_1`. Earlier version of this
        fix dropped `part_i_item_8` regardless, regressing `tenq.items`
        from "9 items including content access" to "8 items with the
        Financial Statements section unreachable."
        """
        sections = {
            # No part_i_item_1 here — mirrors the real JPM filing shape.
            'part_i_item_2': _FakeSection("MD&A", part='I', item='2'),
            'part_i_item_3': _FakeSection("Market risk", part='I', item='3'),
            'part_i_item_8': _FakeSection("Notes / Financial Statements content",
                                          part='I', item='8'),
            'part_ii_item_1': _FakeSection("Legal", part='II', item='1'),
        }
        tenq = _make_tenq(sections)
        assert tenq._is_valid_10q_section_key('part_i_item_8'), (
            "fabricated key must be kept when no Part I Item 1 exists to merge into"
        )
        # And `items` should include it so users can retrieve the content.
        assert 'Part I, Item 8' in tenq.items, (
            f"fabricated Part I, Item 8 must remain accessible; got: {tenq.items}"
        )

    def test_fabricated_key_filtered_when_item_1_sibling_present(self):
        """Sanity counterpart: when valid Item 1 exists, fabricated key is filtered."""
        sections = {
            'part_i_item_1': _FakeSection("Financial statements", part='I', item='1'),
            'part_i_item_8': _FakeSection("Notes (fabricated)", part='I', item='8'),
        }
        tenq = _make_tenq(sections)
        assert not tenq._is_valid_10q_section_key('part_i_item_8')
        assert 'Part I, Item 8' not in tenq.items


# ---------------------------------------------------------------------------
# items property filters fabricated keys
# ---------------------------------------------------------------------------

class TestItemsFiltering:

    def test_fabricated_part_i_item_8_filtered_from_items(self):
        sections = {
            'part_i_item_1': _FakeSection("Financial statements body", part='I', item='1'),
            'part_i_item_2': _FakeSection("MD&A body", part='I', item='2'),
            'part_i_item_8': _FakeSection("FABRICATED Notes body", part='I', item='8'),
            'part_ii_item_1': _FakeSection("Legal proceedings", part='II', item='1'),
        }
        tenq = _make_tenq(sections)
        items = tenq.items
        assert 'Part I, Item 1' in items
        assert 'Part I, Item 2' in items
        assert 'Part II, Item 1' in items
        assert 'Part I, Item 8' not in items, f"fabricated item leaked: {items}"

    def test_legitimate_items_preserved(self):
        sections = {
            'part_i_item_1': _FakeSection("Financial", part='I', item='1'),
            'part_i_item_2': _FakeSection("MD&A", part='I', item='2'),
            'part_i_item_3': _FakeSection("Market risk", part='I', item='3'),
            'part_i_item_4': _FakeSection("Controls", part='I', item='4'),
            'part_ii_item_1': _FakeSection("Legal", part='II', item='1'),
            'part_ii_item_1a': _FakeSection("Risk factors", part='II', item='1A'),
            'part_ii_item_6': _FakeSection("Exhibits", part='II', item='6'),
        }
        tenq = _make_tenq(sections)
        items = tenq.items
        for expected in ('Part I, Item 1', 'Part I, Item 2', 'Part I, Item 3',
                         'Part I, Item 4', 'Part II, Item 1', 'Part II, Item 1A',
                         'Part II, Item 6'):
            assert expected in items, f"missing {expected!r} in items: {items}"


# ---------------------------------------------------------------------------
# __getitem__ merges fabricated content into Item 1
# ---------------------------------------------------------------------------

class TestGetItemMergesFabricatedContent:

    def test_part_i_item_1_includes_fabricated_item_8_content(self):
        sections = {
            'part_i_item_1': _FakeSection("ITEM1_BODY", part='I', item='1'),
            'part_i_item_8': _FakeSection("FABRICATED_NOTES_BODY", part='I', item='8'),
            'part_ii_item_1': _FakeSection("PART2_ITEM1", part='II', item='1'),
        }
        tenq = _make_tenq(sections)
        text = tenq["Part I, Item 1"]
        assert "ITEM1_BODY" in text
        assert "FABRICATED_NOTES_BODY" in text, (
            "fabricated Part I content must be folded into Item 1"
        )

    def test_part_i_item_1_unchanged_when_no_fabrication(self):
        sections = {
            'part_i_item_1': _FakeSection("ITEM1_BODY", part='I', item='1'),
            'part_i_item_2': _FakeSection("ITEM2_BODY", part='I', item='2'),
        }
        tenq = _make_tenq(sections)
        assert tenq["Part I, Item 1"] == "ITEM1_BODY"

    def test_part_ii_item_1_merges_part_ii_fabrications_only(self):
        """A fabricated part_i_item_8 must NOT leak into Part II Item 1."""
        sections = {
            'part_i_item_1': _FakeSection("I1_BODY", part='I', item='1'),
            'part_i_item_8': _FakeSection("PART_I_FAB", part='I', item='8'),
            'part_ii_item_1': _FakeSection("II1_BODY", part='II', item='1'),
            'part_ii_item_8': _FakeSection("PART_II_FAB", part='II', item='8'),
        }
        tenq = _make_tenq(sections)
        part_ii_text = tenq["Part II, Item 1"]
        assert "II1_BODY" in part_ii_text
        assert "PART_II_FAB" in part_ii_text
        assert "PART_I_FAB" not in part_ii_text, (
            "Part I fabricated content must not bleed into Part II Item 1"
        )

    def test_item_2_unaffected_by_fabrications(self):
        """Non-Item-1 lookups are returned untouched."""
        sections = {
            'part_i_item_2': _FakeSection("MDA_BODY", part='I', item='2'),
            'part_i_item_8': _FakeSection("FAB", part='I', item='8'),
        }
        tenq = _make_tenq(sections)
        assert tenq["Part I, Item 2"] == "MDA_BODY"


# ---------------------------------------------------------------------------
# Integration test against the patcher's reference items dict shape
# ---------------------------------------------------------------------------

class TestEndToEndPPGShape:
    """Mirrors what the PPG 10-Q probe (0000079879-26-000170) actually returns."""

    def _ppg_like_sections(self):
        return {
            'part_i_item_1': _FakeSection(
                "Condensed Consolidated Balance Sheet... [66K of body]",
                part='I', item='1',
            ),
            'part_i_item_2': _FakeSection("MD&A...", part='I', item='2'),
            'part_i_item_3': _FakeSection("Market Risk...", part='I', item='3'),
            'part_i_item_8': _FakeSection(
                "Notes to Condensed Consolidated Financial Statements...",
                part='I', item='8',
            ),
            'part_ii_item_1': _FakeSection("Legal Proceedings", part='II', item='1'),
            'part_ii_item_1a': _FakeSection("Risk Factors", part='II', item='1A'),
            'part_ii_item_2': _FakeSection("Unregistered Sales", part='II', item='2'),
            'part_ii_item_5': _FakeSection("Other Information", part='II', item='5'),
            'part_ii_item_6': _FakeSection("Exhibits", part='II', item='6'),
        }

    def test_items_list_excludes_fabricated(self):
        tenq = _make_tenq(self._ppg_like_sections())
        assert 'Part I, Item 8' not in tenq.items

    def test_items_list_includes_all_valid(self):
        tenq = _make_tenq(self._ppg_like_sections())
        items = tenq.items
        for expected in (
            'Part I, Item 1', 'Part I, Item 2', 'Part I, Item 3',
            'Part II, Item 1', 'Part II, Item 1A', 'Part II, Item 2',
            'Part II, Item 5', 'Part II, Item 6',
        ):
            assert expected in items

    def test_notes_content_preserved_in_part_i_item_1(self):
        tenq = _make_tenq(self._ppg_like_sections())
        item_1_text = tenq["Part I, Item 1"]
        assert "Condensed Consolidated Balance Sheet" in item_1_text
        assert "Notes to Condensed Consolidated Financial Statements" in item_1_text
