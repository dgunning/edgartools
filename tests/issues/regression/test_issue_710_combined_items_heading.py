"""
Regression test for GH #710: TenK.business returns None when filing uses
combined "Items 1 and 2. Business and Properties" heading.

The new HTMLParser correctly identifies the section as
part_i_items_1_and_2._business_and_properties, but TenK.__getitem__ builds
the key part_i_item_1 and never checks the combined-items variant.

Fix: Add combined-items key scan in __getitem__ after standard part lookups.
"""

import pytest
from unittest.mock import MagicMock, patch


class FakeSection:
    """Fake section that returns text content."""

    def __init__(self, content):
        self._content = content

    def text(self):
        return self._content


class TestCombinedItemsHeading:
    """Test that TenK.__getitem__ resolves combined 'Items 1 and 2' headings."""

    def _make_tenk_with_sections(self, sections_dict):
        """Create a minimal TenK mock with the given sections."""
        from edgar.company_reports.ten_k import TenK

        fake_sections = {k: FakeSection(v) for k, v in sections_dict.items()}

        tenk = object.__new__(TenK)
        tenk._filing = MagicMock()
        tenk._filing.accession_number = "0002074176-26-000010"
        tenk._cross_reference_index = None

        # Patch document and chunked_document on the instance using mock descriptors
        fake_doc = MagicMock()
        fake_doc.sections = fake_sections
        # Use patch.object on the instance to avoid polluting the class
        self._patches = [
            patch.object(type(tenk), 'document', new_callable=lambda: property(lambda self: fake_doc)),
            patch.object(type(tenk), 'chunked_document', new_callable=lambda: property(lambda self: {})),
        ]
        for p in self._patches:
            p.start()

        return tenk

    def teardown_method(self):
        """Clean up patches to avoid leaking into other tests."""
        for p in getattr(self, '_patches', []):
            p.stop()

    def test_item_1_resolves_combined_items_1_and_2(self):
        """Item 1 lookup should resolve to combined 'Items 1 and 2' section."""
        sections = {
            'part_i_items_1_and_2._business_and_properties': 'Business and Properties content here',
            'part_i_item_1a': 'Risk factors content',
            'part_ii_item_7': 'MDA content',
        }
        tenk = self._make_tenk_with_sections(sections)
        result = tenk['Item 1']
        assert result is not None
        assert 'Business and Properties content here' in result

    def test_item_2_resolves_combined_items_2_and_3(self):
        """Item 2 as first number in combined heading."""
        sections = {
            'part_i_items_2_and_3._properties_and_legal': 'Properties and Legal content',
        }
        tenk = self._make_tenk_with_sections(sections)
        result = tenk['Item 2']
        assert result is not None
        assert 'Properties and Legal content' in result

    def test_item_2_resolves_combined_items_1_and_2(self):
        """Item 2 as second number in combined heading (VNOM pattern)."""
        sections = {
            'part_i_items_1_and_2._business_and_properties': 'Business and Properties content here',
        }
        tenk = self._make_tenk_with_sections(sections)
        result = tenk['Item 2']
        assert result is not None
        assert 'Business and Properties content here' in result

    def test_friendly_name_business_resolves_combined(self):
        """Friendly name 'business' should also resolve combined headings."""
        sections = {
            'part_i_items_1_and_2._business_and_properties': 'Business and Properties content here',
        }
        tenk = self._make_tenk_with_sections(sections)
        result = tenk['business']
        assert result is not None
        assert 'Business and Properties content here' in result

    def test_short_format_resolves_combined(self):
        """Short format '1' should also resolve combined headings."""
        sections = {
            'part_i_items_1_and_2._business_and_properties': 'Business and Properties content here',
        }
        tenk = self._make_tenk_with_sections(sections)
        result = tenk['1']
        assert result is not None
        assert 'Business and Properties content here' in result

    def test_standard_item_still_preferred_over_combined(self):
        """If both standard and combined keys exist, standard should be preferred."""
        sections = {
            'part_i_item_1': 'Standard Item 1 content',
            'part_i_items_1_and_2._business_and_properties': 'Combined content',
        }
        tenk = self._make_tenk_with_sections(sections)
        result = tenk['Item 1']
        assert result is not None
        assert 'Standard Item 1 content' in result
