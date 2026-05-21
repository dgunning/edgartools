"""
Regression test for GitHub Issue #821:
TenK.business / tenk["Item 1"] silently returned 669KB of Part II MD&A content
on Goldman Sachs's 2025 10-K because the section detector emitted a
`part_ii_item_1` key for content that was actually MD&A, and
TenK.__getitem__ fell back through Part I → Part II → Part III → Part IV
when looking up an item — happily returning whatever it found, regardless
of whether SEC form rules allow Item 1 to live in Part II.

Fix: TenK.__getitem__ now consults _ITEM_TO_PART_10K to look up an item only
in its SEC-canonical Part. Item 1 is only checked in Part I; Item 7 is only
checked in Part II; etc. If the canonical-Part key is missing, the lookup
falls through to the legacy chunked_document parser rather than silently
returning content from a wrong Part.
"""

from unittest.mock import MagicMock

import pytest

from edgar.company_reports.ten_k import TenK, _ITEM_TO_PART_10K


@pytest.fixture
def make_tenk(monkeypatch):
    """Factory returning a TenK whose .sections is a dict the caller supplies.

    Uses monkeypatch so the property is restored after each test — no
    cross-test contamination of the real TenK.sections.
    """

    def _factory(sections_data: dict) -> TenK:
        tenk = TenK.__new__(TenK)
        tenk.chunked_document = MagicMock()
        tenk.chunked_document.__getitem__ = MagicMock(return_value=None)
        tenk._cross_reference_index = None
        tenk._filing = MagicMock()
        tenk._filing.accession_number = "0000000000-00-000000"

        sections = {}
        for key, text in sections_data.items():
            sec = MagicMock()
            sec.text = MagicMock(return_value=text)
            sections[key] = sec

        monkeypatch.setattr(TenK, "sections", property(lambda _self: sections))
        return tenk

    return _factory


class TestItemToPartMap:
    """The 10-K item-to-part mapping mirrors SEC form structure."""

    def test_part_i_items(self):
        for item in ['1', '1a', '1b', '1c', '2', '3', '4']:
            assert _ITEM_TO_PART_10K[item] == 'i', f"Item {item} must map to Part I"

    def test_part_ii_items(self):
        for item in ['5', '6', '7', '7a', '8', '9', '9a', '9b', '9c']:
            assert _ITEM_TO_PART_10K[item] == 'ii', f"Item {item} must map to Part II"

    def test_part_iii_items(self):
        for item in ['10', '11', '12', '13', '14']:
            assert _ITEM_TO_PART_10K[item] == 'iii', f"Item {item} must map to Part III"

    def test_part_iv_items(self):
        for item in ['15', '16']:
            assert _ITEM_TO_PART_10K[item] == 'iv', f"Item {item} must map to Part IV"


class TestNoCrossPartFallback:
    """Issue #821 — TenK.__getitem__ never returns content from the wrong Part."""

    def test_item_1_lookup_does_not_return_part_ii_content(self, make_tenk):
        """The GS bug: part_ii_item_1 contains MD&A. Item 1 lookup must not return it."""
        wrong_content = "Management's Discussion and Analysis\n" + "x" * 1000
        tenk = make_tenk({'part_ii_item_1': wrong_content})

        result = tenk['Item 1']
        assert result is None, (
            "Item 1 must not return Part II content even when part_ii_item_1 exists. "
            "Got %d chars starting with %r" % (len(result) if result else 0,
                                                result[:80] if result else None)
        )

    def test_item_1_returns_part_i_content_when_present(self, make_tenk):
        """Sanity: when part_i_item_1 exists, it is returned correctly."""
        correct_content = "Business: We are a leading global financial institution..."
        tenk = make_tenk({
            'part_i_item_1': correct_content,
            'part_ii_item_1': "WRONG CONTENT - MD&A",
        })

        result = tenk['Item 1']
        assert result == correct_content

    def test_item_7_returns_part_ii_content(self, make_tenk):
        """Item 7 (MD&A) lives in Part II — lookup must succeed."""
        mda = "Management's Discussion and Analysis: revenues grew..."
        tenk = make_tenk({'part_ii_item_7': mda})

        result = tenk['Item 7']
        assert result == mda

    def test_item_7_does_not_return_part_i_content(self, make_tenk):
        """Inverse: Item 7 must never be looked up in Part I."""
        wrong_content = "Business overview (Part I content tagged as item 7)"
        tenk = make_tenk({'part_i_item_7': wrong_content})

        result = tenk['Item 7']
        assert result is None

    def test_item_10_does_not_return_part_i_or_ii(self, make_tenk):
        """Item 10 lives in Part III only."""
        tenk = make_tenk({
            'part_i_item_10': "wrong part I content",
            'part_ii_item_10': "wrong part II content",
        })
        result = tenk['Item 10']
        assert result is None

    def test_item_15_lives_in_part_iv(self, make_tenk):
        """Item 15 (Exhibits) lives in Part IV only."""
        exhibits = "Exhibits list..."
        tenk = make_tenk({'part_iv_item_15': exhibits})

        result = tenk['Item 15']
        assert result == exhibits

    def test_short_format_item_1_no_cross_part_fallback(self, make_tenk):
        """tenk['1'] (short format) also respects SEC structure."""
        tenk = make_tenk({'part_ii_item_1': "WRONG"})
        assert tenk['1'] is None

    def test_friendly_name_business_no_cross_part_fallback(self, make_tenk):
        """tenk.business (which calls tenk['Item 1']) must not silently return Part II."""
        tenk = make_tenk({'part_ii_item_1': "WRONG MD&A CONTENT"})

        # business property goes through __getitem__('Item 1')
        result = tenk.business
        assert result is None
