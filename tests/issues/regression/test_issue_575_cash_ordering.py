"""
Regression test for Issue #575: Balance sheet missing Cash for IESC

Problem: IESC's 10-K filing has the presentation linkbase ordering that puts
Cash and Cash Equivalents at position 39 (the very end) instead of with other
Current Assets. This caused Cash to appear at the bottom of the balance sheet
instead of near the top with other Current Assets.

Root Cause: The IESC filing's presentation linkbase has Cash as a direct child
of the root abstract element at order 39, while the calculation linkbase
correctly shows Cash as a component of Assets Current (order 2).

Fix: Added `_reorder_by_calculation_parent()` in xbrl.py to move items
that appear after their calculation parent to appear before it. This ensures
components appear before their totals even when the presentation linkbase
has incorrect ordering.

See: https://github.com/dgunning/edgartools/issues/575
"""
import pytest


class TestIssue575CashOrdering:
    """Test that Cash appears before Total Current Assets in balance sheets."""

    @pytest.fixture
    def iesc_10k_xbrl(self):
        """Get IESC 10-K XBRL for testing."""
        from edgar import Company
        company = Company("IESC")
        filing = company.get_filings(form="10-K").latest()
        return filing.xbrl()

    @pytest.mark.network
    def test_cash_before_total_current_assets(self, iesc_10k_xbrl):
        """Test that Cash appears before Total Current Assets in IESC balance sheet."""
        bs = iesc_10k_xbrl.statements.balance_sheet()
        df = bs.to_dataframe()

        # Find indices for Cash and Total Current Assets
        cash_idx = None
        assets_current_idx = None

        for i, row in df.iterrows():
            concept = row.get('concept', '')
            if 'CashAndCashEquivalents' in concept:
                cash_idx = i
            if concept.endswith('AssetsCurrent') and 'Abstract' not in concept:
                assets_current_idx = i

        assert cash_idx is not None, "Should find Cash and Cash Equivalents"
        assert assets_current_idx is not None, "Should find Total Current Assets"
        assert cash_idx < assets_current_idx, \
            f"Cash (idx {cash_idx}) should appear BEFORE Total Current Assets (idx {assets_current_idx})"

    @pytest.mark.network
    def test_cash_has_values(self, iesc_10k_xbrl):
        """Test that Cash line has actual values."""
        bs = iesc_10k_xbrl.statements.balance_sheet()
        df = bs.to_dataframe()

        # Find Cash row
        cash_rows = df[df['concept'].str.contains('CashAndCashEquivalents', na=False)]
        assert len(cash_rows) > 0, "Should find Cash and Cash Equivalents row"

        # Get value columns
        meta_cols = ['concept', 'label', 'level', 'abstract', 'dimension', 'is_breakdown',
                     'dimension_label', 'balance', 'weight', 'preferred_sign',
                     'parent_concept', 'parent_abstract_concept']
        value_cols = [c for c in df.columns if c not in meta_cols]

        assert len(value_cols) > 0, "Should have value columns"

        # Check that at least one value column has a non-null value for Cash
        cash_row = cash_rows.iloc[0]
        has_value = False
        for col in value_cols:
            if col in cash_row and cash_row[col] is not None and str(cash_row[col]) != 'nan':
                has_value = True
                break

        assert has_value, "Cash row should have at least one value"


class TestReorderByCalculationParent:
    """Test the reorder_by_calculation_parent logic."""

    @pytest.mark.fast
    def test_reorder_moves_items_before_parent(self):
        """Test that items appearing after their calculation parent are moved before."""
        from edgar.xbrl.xbrl import XBRL

        # Simulate line items where Cash appears after AssetsCurrent
        line_items = [
            {'concept': 'us-gaap_AccountsReceivable', 'calculation_parent': 'us-gaap_AssetsCurrent'},
            {'concept': 'us-gaap_Inventory', 'calculation_parent': 'us-gaap_AssetsCurrent'},
            {'concept': 'us-gaap_AssetsCurrent', 'calculation_parent': 'us-gaap_Assets'},
            {'concept': 'us-gaap_Assets', 'calculation_parent': None},
            {'concept': 'us-gaap_CashAndCashEquivalents', 'calculation_parent': 'us-gaap_AssetsCurrent'},  # Wrong position!
        ]

        reordered = XBRL._reorder_by_calculation_parent(line_items)

        # Find indices after reordering
        cash_idx = next(i for i, item in enumerate(reordered) if 'Cash' in item['concept'])
        assets_current_idx = next(i for i, item in enumerate(reordered) if item['concept'] == 'us-gaap_AssetsCurrent')

        assert cash_idx < assets_current_idx, \
            f"Cash (idx {cash_idx}) should be before AssetsCurrent (idx {assets_current_idx})"

    @pytest.mark.fast
    def test_reorder_preserves_correct_ordering(self):
        """Test that items already in correct order are not changed."""
        from edgar.xbrl.xbrl import XBRL

        # Line items already in correct order
        line_items = [
            {'concept': 'us-gaap_CashAndCashEquivalents', 'calculation_parent': 'us-gaap_AssetsCurrent'},
            {'concept': 'us-gaap_AccountsReceivable', 'calculation_parent': 'us-gaap_AssetsCurrent'},
            {'concept': 'us-gaap_AssetsCurrent', 'calculation_parent': 'us-gaap_Assets'},
            {'concept': 'us-gaap_Assets', 'calculation_parent': None},
        ]

        reordered = XBRL._reorder_by_calculation_parent(line_items)

        # Order should be preserved
        assert reordered[0]['concept'] == 'us-gaap_CashAndCashEquivalents'
        assert reordered[1]['concept'] == 'us-gaap_AccountsReceivable'
        assert reordered[2]['concept'] == 'us-gaap_AssetsCurrent'
        assert reordered[3]['concept'] == 'us-gaap_Assets'

    @pytest.mark.fast
    def test_reorder_handles_empty_list(self):
        """Test that empty list is handled correctly."""
        from edgar.xbrl.xbrl import XBRL

        result = XBRL._reorder_by_calculation_parent([])
        assert result == []

    @pytest.mark.fast
    def test_reorder_handles_no_calculation_parents(self):
        """Test that items without calculation parents are preserved."""
        from edgar.xbrl.xbrl import XBRL

        line_items = [
            {'concept': 'us-gaap_Assets', 'calculation_parent': None},
            {'concept': 'us-gaap_Liabilities', 'calculation_parent': None},
        ]

        reordered = XBRL._reorder_by_calculation_parent(line_items)
        assert len(reordered) == 2
        assert reordered[0]['concept'] == 'us-gaap_Assets'
        assert reordered[1]['concept'] == 'us-gaap_Liabilities'
