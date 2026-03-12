"""
Regression tests for GitHub Issue #703: Balance sheet missing equity components.

When a company's filing contains both a balance sheet and a Statement of Changes in
Stockholders' Equity (embedded in the same XBRL document), the presentation tree can
have multiple instances of `StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest`
with preferred labels matching equity component names (e.g., "Additional paid-in capital",
"Retained earnings").

The _merge_same_label_line_items function was incorrectly merging the genuine
equity-component line items (e.g., AdditionalPaidInCapital) with the equity-changes
SE breakdown rows because:
  1. Both had the same label ("Additional paid-in capital")
  2. Both had matching values for the overlapping balance sheet dates

The fix: only merge when the secondary item adds at least one new period that the
primary doesn't already have.  If the primary covers all of the secondary's periods
(i.e. the secondary is a subset), they are different concepts that happen to agree
on the shared dates — keep both.
"""

import pytest
from edgar.xbrl.xbrl import XBRL


@pytest.mark.fast
class TestIssue703MergeGuard:
    """Unit tests for the 'secondary must add new periods' guard."""

    def test_subset_secondary_not_merged(self):
        """Secondary is a subset of primary — must NOT be merged (GH-703 case)."""
        # Primary = equity-changes breakdown row, Secondary = dedicated concept
        # Both have values for 2024 and 2025 that happen to be equal.
        line_items = [
            {
                'concept': 'us-gaap:AdditionalPaidInCapital',
                'label': 'Additional paid-in capital',
                'values': {'instant_2025-12-31': 21441, 'instant_2024-12-31': 18964},
                'all_names': ['us-gaap:AdditionalPaidInCapital'],
                'is_abstract': False,
                'decimals': {}, 'units': {}, 'period_types': {},
                'preferred_signs': {}, 'balance': {}, 'weight': {},
            },
            {
                # StockholdersEquity breakdown labeled "Additional paid-in capital"
                'concept': 'us-gaap:StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest',
                'label': 'Additional paid-in capital',
                'values': {
                    'instant_2022-12-31': 9947,
                    'instant_2023-12-31': 10309,
                    'instant_2024-12-31': 18964,   # matches APIC
                    'instant_2025-12-31': 21441,   # matches APIC
                },
                'all_names': ['us-gaap:StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest'],
                'is_abstract': False,
                'decimals': {}, 'units': {}, 'period_types': {},
                'preferred_signs': {}, 'balance': {}, 'weight': {},
            },
        ]

        result = XBRL._merge_same_label_line_items(line_items)

        # Both should be preserved — APIC is NOT a subset of SE breakdown
        assert len(result) == 2

    def test_complementary_periods_still_merge(self):
        """Items with non-overlapping periods should still be merged (original use case)."""
        line_items = [
            {
                'concept': 'aapl:DerivativeInstrument',
                'label': 'Change in fair value of derivative instruments',
                'values': {'2024': 10, '2023': -5},
                'all_names': ['aapl:DerivativeInstrument'],
                'is_abstract': False,
                'decimals': {}, 'units': {}, 'period_types': {},
                'preferred_signs': {}, 'balance': {}, 'weight': {},
            },
            {
                'concept': 'us-gaap:CashFlowHedge',
                'label': 'Change in fair value of derivative instruments',
                'values': {'2025': 15},
                'all_names': ['us-gaap:CashFlowHedge'],
                'is_abstract': False,
                'decimals': {}, 'units': {}, 'period_types': {},
                'preferred_signs': {}, 'balance': {}, 'weight': {},
            },
        ]

        result = XBRL._merge_same_label_line_items(line_items)
        assert len(result) == 1
        assert result[0]['values'] == {'2025': 15, '2024': 10, '2023': -5}

    def test_partial_overlap_with_new_periods_merges(self):
        """Secondary that adds new periods AND has agreeing overlap values should merge."""
        line_items = [
            {
                'concept': 'us-gaap:ConceptA',
                'label': 'Net income',
                'values': {'2025': 100, '2024': 90},
                'all_names': ['ConceptA'],
                'is_abstract': False,
                'decimals': {}, 'units': {}, 'period_types': {},
                'preferred_signs': {}, 'balance': {}, 'weight': {},
            },
            {
                'concept': 'company:ConceptB',
                'label': 'Net income',
                'values': {'2024': 90, '2023': 80},   # adds 2023
                'all_names': ['ConceptB'],
                'is_abstract': False,
                'decimals': {}, 'units': {}, 'period_types': {},
                'preferred_signs': {}, 'balance': {}, 'weight': {},
            },
        ]

        result = XBRL._merge_same_label_line_items(line_items)
        assert len(result) == 1
        assert result[0]['values'] == {'2025': 100, '2024': 90, '2023': 80}

    def test_equal_period_sets_with_equal_values_not_merged(self):
        """Two items with identical period sets and identical values are different concepts — don't merge."""
        line_items = [
            {
                'concept': 'us-gaap:RetainedEarnings',
                'label': 'Retained earnings',
                'values': {'2025': 17252, '2024': 15362},
                'all_names': ['us-gaap:RetainedEarnings'],
                'is_abstract': False,
                'decimals': {}, 'units': {}, 'period_types': {},
                'preferred_signs': {}, 'balance': {}, 'weight': {},
            },
            {
                'concept': 'us-gaap:StockholdersEquityTotal',
                'label': 'Retained earnings',
                'values': {'2025': 17252, '2024': 15362},  # identical periods and values
                'all_names': ['us-gaap:StockholdersEquityTotal'],
                'is_abstract': False,
                'decimals': {}, 'units': {}, 'period_types': {},
                'preferred_signs': {}, 'balance': {}, 'weight': {},
            },
        ]

        result = XBRL._merge_same_label_line_items(line_items)
        # Neither contributes new periods to the other — keep both
        assert len(result) == 2
