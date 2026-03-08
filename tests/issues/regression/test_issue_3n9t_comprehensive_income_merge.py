"""
Regression test for edgartools-3n9t / gh:572: Merge same-label rows with complementary NaN values.

AAPL's Comprehensive Income statement has duplicate rows where the company switched
XBRL concepts between fiscal years. For example, "Change in fair value of derivative
instruments" uses us-gaap:...CashFlowHedge... in 2025 but aapl:...DerivativeInstrument...
in 2024/2023. This produces two rows with the same label but complementary NaN values
instead of one merged row.

Key constraint: the "Adjustment for net (gains)/losses" label appears on 3 different
concepts — two are derivatives that should merge, one is securities that must NOT merge.
Label-only matching is unsafe; the value agreement check prevents incorrect merges.
"""

import pytest
from edgar.xbrl.xbrl import XBRL


class TestMergeSameLabelLineItems:
    """Unit tests for _merge_same_label_line_items using synthetic data."""

    def test_complementary_values_merged(self):
        """Two items with same label and non-overlapping periods should merge."""
        line_items = [
            {
                'concept': 'us-gaap:ConceptA',
                'label': 'Revenue from operations',
                'values': {'2025': 100, '2024': 90},
                'all_names': ['ConceptA'],
                'is_abstract': False,
                'decimals': {'2025': -6, '2024': -6},
                'units': {'2025': 'USD', '2024': 'USD'},
                'period_types': {'2025': 'duration', '2024': 'duration'},
                'preferred_signs': {},
                'balance': {},
                'weight': {},
            },
            {
                'concept': 'company:ConceptB',
                'label': 'Revenue from operations',
                'values': {'2023': 80},
                'all_names': ['ConceptB'],
                'is_abstract': False,
                'decimals': {'2023': -6},
                'units': {'2023': 'USD'},
                'period_types': {'2023': 'duration'},
                'preferred_signs': {},
                'balance': {},
                'weight': {},
            },
        ]

        result = XBRL._merge_same_label_line_items(line_items)
        assert len(result) == 1
        merged = result[0]
        assert merged['values'] == {'2025': 100, '2024': 90, '2023': 80}
        assert set(merged['all_names']) == {'ConceptA', 'ConceptB'}

    def test_overlapping_agreeing_values_merged(self):
        """Items with same label and agreeing overlap values should merge."""
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
                'values': {'2024': 90, '2023': 80},
                'all_names': ['ConceptB'],
                'is_abstract': False,
                'decimals': {}, 'units': {}, 'period_types': {},
                'preferred_signs': {}, 'balance': {}, 'weight': {},
            },
        ]

        result = XBRL._merge_same_label_line_items(line_items)
        assert len(result) == 1
        assert result[0]['values'] == {'2025': 100, '2024': 90, '2023': 80}

    def test_overlapping_disagreeing_values_not_merged(self):
        """Items with same label but different overlap values must NOT merge."""
        line_items = [
            {
                'concept': 'us-gaap:ConceptA',
                'label': 'Adjustment for net (gains)/losses',
                'values': {'2025': 100, '2024': 50},
                'all_names': ['ConceptA'],
                'is_abstract': False,
                'decimals': {}, 'units': {}, 'period_types': {},
                'preferred_signs': {}, 'balance': {}, 'weight': {},
            },
            {
                'concept': 'us-gaap:ConceptB',
                'label': 'Adjustment for net (gains)/losses',
                'values': {'2024': 999, '2023': 80},
                'all_names': ['ConceptB'],
                'is_abstract': False,
                'decimals': {}, 'units': {}, 'period_types': {},
                'preferred_signs': {}, 'balance': {}, 'weight': {},
            },
        ]

        result = XBRL._merge_same_label_line_items(line_items)
        assert len(result) == 2

    def test_abstract_items_not_merged(self):
        """Abstract items with same label should not be merged."""
        line_items = [
            {
                'concept': 'us-gaap:Abstract1',
                'label': 'Section header',
                'values': {},
                'all_names': ['Abstract1'],
                'is_abstract': True,
                'decimals': {}, 'units': {}, 'period_types': {},
                'preferred_signs': {}, 'balance': {}, 'weight': {},
            },
            {
                'concept': 'us-gaap:Abstract2',
                'label': 'Section header',
                'values': {},
                'all_names': ['Abstract2'],
                'is_abstract': True,
                'decimals': {}, 'units': {}, 'period_types': {},
                'preferred_signs': {}, 'balance': {}, 'weight': {},
            },
        ]

        result = XBRL._merge_same_label_line_items(line_items)
        assert len(result) == 2

    def test_single_items_unchanged(self):
        """Items with unique labels should pass through unchanged."""
        line_items = [
            {
                'concept': 'us-gaap:Revenue',
                'label': 'Revenue',
                'values': {'2025': 100},
                'all_names': ['Revenue'],
                'is_abstract': False,
                'decimals': {}, 'units': {}, 'period_types': {},
                'preferred_signs': {}, 'balance': {}, 'weight': {},
            },
            {
                'concept': 'us-gaap:NetIncome',
                'label': 'Net income',
                'values': {'2025': 50},
                'all_names': ['NetIncome'],
                'is_abstract': False,
                'decimals': {}, 'units': {}, 'period_types': {},
                'preferred_signs': {}, 'balance': {}, 'weight': {},
            },
        ]

        result = XBRL._merge_same_label_line_items(line_items)
        assert len(result) == 2

    def test_metadata_propagated(self):
        """Metadata from secondary item should fill gaps in primary."""
        line_items = [
            {
                'concept': 'us-gaap:ConceptA',
                'label': 'Some item',
                'values': {'2025': 100},
                'all_names': ['ConceptA'],
                'is_abstract': False,
                'decimals': {'2025': -6},
                'units': {'2025': 'USD'},
                'period_types': {'2025': 'duration'},
                'preferred_signs': {'2025': -1},
                'balance': {},
                'weight': {},
            },
            {
                'concept': 'company:ConceptB',
                'label': 'Some item',
                'values': {'2023': 80},
                'all_names': ['ConceptB'],
                'is_abstract': False,
                'decimals': {'2023': -3},
                'units': {'2023': 'USD'},
                'period_types': {'2023': 'duration'},
                'preferred_signs': {'2023': -1},
                'balance': {},
                'weight': {},
            },
        ]

        result = XBRL._merge_same_label_line_items(line_items)
        assert len(result) == 1
        merged = result[0]
        assert merged['decimals'] == {'2025': -6, '2023': -3}
        assert merged['units'] == {'2025': 'USD', '2023': 'USD'}
        assert merged['preferred_signs'] == {'2025': -1, '2023': -1}

    def test_primary_is_item_with_more_values(self):
        """The item with more period values should be primary."""
        line_items = [
            {
                'concept': 'company:OldConcept',
                'label': 'Some item',
                'values': {'2023': 80},
                'all_names': ['OldConcept'],
                'is_abstract': False,
                'decimals': {}, 'units': {}, 'period_types': {},
                'preferred_signs': {}, 'balance': {}, 'weight': {},
            },
            {
                'concept': 'us-gaap:NewConcept',
                'label': 'Some item',
                'values': {'2025': 100, '2024': 90},
                'all_names': ['NewConcept'],
                'is_abstract': False,
                'decimals': {}, 'units': {}, 'period_types': {},
                'preferred_signs': {}, 'balance': {}, 'weight': {},
            },
        ]

        result = XBRL._merge_same_label_line_items(line_items)
        assert len(result) == 1
        # Primary should be NewConcept (has more values)
        assert result[0]['concept'] == 'us-gaap:NewConcept'
        assert result[0]['values'] == {'2025': 100, '2024': 90, '2023': 80}

    def test_three_items_same_label_with_disagreement(self):
        """Three items with same label: two should merge, one should stay separate."""
        line_items = [
            {
                'concept': 'us-gaap:DerivativeA',
                'label': 'Adjustment for net (gains)/losses',
                'values': {'2025': 100},
                'all_names': ['DerivativeA'],
                'is_abstract': False,
                'decimals': {}, 'units': {}, 'period_types': {},
                'preferred_signs': {}, 'balance': {}, 'weight': {},
            },
            {
                'concept': 'company:DerivativeB',
                'label': 'Adjustment for net (gains)/losses',
                'values': {'2024': 90, '2023': 80},
                'all_names': ['DerivativeB'],
                'is_abstract': False,
                'decimals': {}, 'units': {}, 'period_types': {},
                'preferred_signs': {}, 'balance': {}, 'weight': {},
            },
            {
                'concept': 'us-gaap:Securities',
                'label': 'Adjustment for net (gains)/losses',
                'values': {'2025': 500, '2024': 400, '2023': 300},
                'all_names': ['Securities'],
                'is_abstract': False,
                'decimals': {}, 'units': {}, 'period_types': {},
                'preferred_signs': {}, 'balance': {}, 'weight': {},
            },
        ]

        result = XBRL._merge_same_label_line_items(line_items)
        # DerivativeA and DerivativeB can merge (no overlap)
        # Securities can't merge with either (overlapping values disagree)
        assert len(result) == 2

    def test_three_items_all_mergeable_secondary_swap(self):
        """When first item becomes secondary, its remaining matches must still merge.

        A has 1 value, B has 2, C has 1. A merges into B (A is secondary).
        Then B (now with 3 values) should merge C in a subsequent outer-loop pass.
        All 3 values + C's value must end up in one item.
        """
        line_items = [
            {
                'concept': 'company:OldConcept',
                'label': 'Some metric',
                'values': {'2025': 100},
                'all_names': ['OldConcept'],
                'is_abstract': False,
                'decimals': {}, 'units': {}, 'period_types': {},
                'preferred_signs': {}, 'balance': {}, 'weight': {},
            },
            {
                'concept': 'us-gaap:NewConcept',
                'label': 'Some metric',
                'values': {'2024': 90, '2023': 80},
                'all_names': ['NewConcept'],
                'is_abstract': False,
                'decimals': {}, 'units': {}, 'period_types': {},
                'preferred_signs': {}, 'balance': {}, 'weight': {},
            },
            {
                'concept': 'company:OlderConcept',
                'label': 'Some metric',
                'values': {'2022': 70},
                'all_names': ['OlderConcept'],
                'is_abstract': False,
                'decimals': {}, 'units': {}, 'period_types': {},
                'preferred_signs': {}, 'balance': {}, 'weight': {},
            },
        ]

        result = XBRL._merge_same_label_line_items(line_items)
        assert len(result) == 1
        assert result[0]['values'] == {'2025': 100, '2024': 90, '2023': 80, '2022': 70}


@pytest.mark.network
def test_aapl_comprehensive_income_no_unexpected_duplicate_labels():
    """AAPL comprehensive income should merge concept-switch duplicates while preserving
    legitimate same-label items that have different values.

    After merging, the only remaining "duplicate" label should be the
    "Adjustment for net (gains)/losses realized and included in net income" row
    which appears for both derivatives and securities — these are genuinely
    different line items with different values that correctly refuse to merge.
    """
    from edgar import Company

    company = Company('AAPL')
    filing = company.get_filings(form='10-K').latest()
    xbrl = filing.xbrl()
    stmt = xbrl.statements.comprehensive_income()
    assert stmt is not None, "AAPL should have a comprehensive income statement"

    df = stmt.to_dataframe()
    non_abstract = df[~df['abstract']]

    # Check for duplicate labels among non-abstract rows
    label_counts = non_abstract['label'].value_counts()
    duplicates = label_counts[label_counts > 1]

    # The only legitimate duplicate is the Adjustment row (derivatives vs securities)
    expected_duplicates = {'Adjustment for net (gains)/losses realized and included in net income'}
    actual_duplicates = set(duplicates.index)
    unexpected = actual_duplicates - expected_duplicates

    assert not unexpected, (
        f"Found unexpected duplicate labels in non-abstract rows: "
        f"{{k: duplicates[k] for k in unexpected}}"
    )


@pytest.mark.network
def test_aapl_comprehensive_income_merged_rows_have_all_periods():
    """After merging, rows that had complementary NaN values should have all period values."""
    from edgar import Company

    company = Company('AAPL')
    filing = company.get_filings(form='10-K').latest()
    xbrl = filing.xbrl()
    stmt = xbrl.statements.comprehensive_income()
    df = stmt.to_dataframe()

    value_cols = [c for c in df.columns if c.startswith('20')]
    non_abstract = df[~df['abstract']]

    # After merge, non-abstract value cells should have minimal NaN
    nan_count = non_abstract[value_cols].isna().sum().sum()
    assert nan_count == 0, (
        f"Found {nan_count} NaN values in non-abstract rows — merge may have failed"
    )
