"""
Regression tests for GitHub Issue #703: Balance sheet missing equity components.

Root cause: _merge_same_label_line_items (a global post-processing step) incorrectly
merged genuine equity-component line items with equity-changes breakdown rows that
shared the same label and coincidentally equal values.

Fix: Removed the global merge heuristic entirely.  Replaced with
_merge_sibling_concept_switches which runs during tree traversal, scoped to direct
siblings under the same parent.  This correctly handles XBRL concept switches
(GH-572) without affecting unrelated concepts elsewhere in the statement.
"""

import pytest
from edgar.xbrl.xbrl import XBRL


@pytest.mark.fast
class TestIssue703SiblingMerge:
    """Verify sibling-scoped merge handles concept switches without false merges."""

    def _make_node(self, element_name, depth, children=None, display_label='', parent=None,
                   is_abstract=False, order=1.0, preferred_label=None):
        """Create a minimal PresentationNode-like object for testing."""
        class FakeNode:
            pass
        node = FakeNode()
        node.element_name = element_name
        node.depth = depth
        node.children = children or []
        node.display_label = display_label
        node.parent = parent
        node.is_abstract = is_abstract
        node.order = order
        node.preferred_label = preferred_label
        node.is_company_preferred_label = False
        return node

    def test_complementary_siblings_merge(self):
        """Sibling concepts with same label and non-overlapping periods should merge."""
        nodes = {
            'concept_new': self._make_node('concept_new', 2, display_label='Revenue'),
            'concept_old': self._make_node('concept_old', 2, display_label='Revenue'),
        }
        children = ['concept_new', 'concept_old']

        result = [
            {
                'concept': 'concept_new', 'label': 'Revenue',
                'values': {'2025': 100}, 'all_names': ['concept_new'],
                'is_abstract': False, 'has_values': True,
                'decimals': {}, 'units': {}, 'period_types': {},
                'preferred_signs': {}, 'balance': {}, 'weight': {},
            },
            {
                'concept': 'concept_old', 'label': 'Revenue',
                'values': {'2024': 90, '2023': 80}, 'all_names': ['concept_old'],
                'is_abstract': False, 'has_values': True,
                'decimals': {}, 'units': {}, 'period_types': {},
                'preferred_signs': {}, 'balance': {}, 'weight': {},
            },
        ]

        XBRL._merge_sibling_concept_switches(result, 0, children, nodes)

        assert len(result) == 1
        assert result[0]['values'] == {'2025': 100, '2024': 90, '2023': 80}

    def test_different_concepts_same_label_not_merged(self):
        """Non-sibling concepts with same label must NOT be merged (the #703 bug)."""
        # Simulate BA's case: APIC and SE breakdown row are NOT siblings
        # (they have different parents in the tree), so they would never
        # be passed to _merge_sibling_concept_switches together.
        # This test verifies the method doesn't merge when secondary adds no new periods.
        nodes = {
            'us-gaap:APIC': self._make_node('us-gaap:APIC', 5, display_label='Additional paid-in capital'),
            'us-gaap:SE': self._make_node('us-gaap:SE', 6, display_label='Additional paid-in capital'),
        }
        children = ['us-gaap:APIC', 'us-gaap:SE']

        result = [
            {
                'concept': 'us-gaap:APIC', 'label': 'Additional paid-in capital',
                'values': {'2025': 21441, '2024': 18964},
                'all_names': ['us-gaap:APIC'],
                'is_abstract': False, 'has_values': True,
                'decimals': {}, 'units': {}, 'period_types': {},
                'preferred_signs': {}, 'balance': {}, 'weight': {},
            },
            {
                'concept': 'us-gaap:SE', 'label': 'Additional paid-in capital',
                'values': {'2022': 9947, '2023': 10309, '2024': 18964, '2025': 21441},
                'all_names': ['us-gaap:SE'],
                'is_abstract': False, 'has_values': True,
                'decimals': {}, 'units': {}, 'period_types': {},
                'preferred_signs': {}, 'balance': {}, 'weight': {},
            },
        ]

        XBRL._merge_sibling_concept_switches(result, 0, children, nodes)

        # APIC is a subset of SE — secondary adds no new periods → not merged
        assert len(result) == 2

    def test_disagreeing_values_not_merged(self):
        """Siblings with same label but different overlapping values must NOT merge."""
        nodes = {
            'us-gaap:A': self._make_node('us-gaap:A', 3, display_label='Adjustment'),
            'us-gaap:B': self._make_node('us-gaap:B', 3, display_label='Adjustment'),
        }
        children = ['us-gaap:A', 'us-gaap:B']

        result = [
            {
                'concept': 'us-gaap:A', 'label': 'Adjustment',
                'values': {'2025': 100, '2024': 50},
                'all_names': ['us-gaap:A'],
                'is_abstract': False, 'has_values': True,
                'decimals': {}, 'units': {}, 'period_types': {},
                'preferred_signs': {}, 'balance': {}, 'weight': {},
            },
            {
                'concept': 'us-gaap:B', 'label': 'Adjustment',
                'values': {'2024': 999, '2023': 80},
                'all_names': ['us-gaap:B'],
                'is_abstract': False, 'has_values': True,
                'decimals': {}, 'units': {}, 'period_types': {},
                'preferred_signs': {}, 'balance': {}, 'weight': {},
            },
        ]

        XBRL._merge_sibling_concept_switches(result, 0, children, nodes)

        assert len(result) == 2

    def test_non_leaf_concepts_not_merged(self):
        """Concepts with children in the tree should not be merged."""
        nodes = {
            'concept_a': self._make_node('concept_a', 2, children=['child1'],
                                          display_label='Total'),
            'concept_b': self._make_node('concept_b', 2, display_label='Total'),
        }
        children = ['concept_a', 'concept_b']

        result = [
            {
                'concept': 'concept_a', 'label': 'Total',
                'values': {'2025': 100}, 'all_names': ['concept_a'],
                'is_abstract': False, 'has_values': True,
                'decimals': {}, 'units': {}, 'period_types': {},
                'preferred_signs': {}, 'balance': {}, 'weight': {},
            },
            {
                'concept': 'concept_b', 'label': 'Total',
                'values': {'2024': 90}, 'all_names': ['concept_b'],
                'is_abstract': False, 'has_values': True,
                'decimals': {}, 'units': {}, 'period_types': {},
                'preferred_signs': {}, 'balance': {}, 'weight': {},
            },
        ]

        XBRL._merge_sibling_concept_switches(result, 0, children, nodes)

        # concept_a has children → not a leaf → skip merge
        assert len(result) == 2
