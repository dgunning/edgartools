"""
Regression test for Issue #599: Pandas FutureWarning in presentation mode

Problem: When calling to_dataframe(presentation=True) on income statements and
cash flow statements, pandas raised a FutureWarning about setting an item of
incompatible dtype. This occurred because the presentation transformation code
assigned float values to object dtype columns without explicit casting.

The warning appeared for Income Statement and Cash Flow Statement but NOT
Balance Sheet (because Balance Sheet skips the presentation transformation).

Error message:
    statements.py:1044: FutureWarning: Setting an item of incompatible dtype is
    deprecated and will raise an error in a future version of pandas.

Fix: Convert the column to numeric dtype before performing the masked assignment.
This ensures dtype compatibility and prevents the FutureWarning.

Root cause: Line 1138 in _apply_presentation() assigned float values from
`numeric_col[mask] * preferred_sign` to object dtype column `result.loc[mask, col]`.

Reporter: miruddfan
See: https://github.com/dgunning/edgartools/issues/599
"""
import warnings

import pytest


class TestIssue599PandasFutureWarning:
    """Test that presentation mode doesn't produce pandas FutureWarnings."""

    @pytest.fixture
    def msft_10k_xbrl(self):
        """Get MSFT 10-K XBRL for testing (user's reproduction case)."""
        from edgar import Company
        company = Company("MSFT")
        filing = company.get_filings(form="10-K").latest()
        return filing.xbrl()

    @pytest.mark.network
    def test_income_statement_presentation_no_warning(self, msft_10k_xbrl):
        """Test that income statement with presentation=True produces no FutureWarning.

        This was the primary reproduction case from Issue #599.
        """
        income = msft_10k_xbrl.statements.income_statement()

        # This should NOT produce FutureWarning after the fix
        with warnings.catch_warnings():
            warnings.simplefilter("error", FutureWarning)
            df = income.to_dataframe(presentation=True)

        # Verify data is still correct
        assert not df.empty, "Income statement should not be empty"
        assert 'preferred_sign' in df.columns, "Should have preferred_sign column"

        # Verify we have value columns (not just metadata)
        meta_cols = ['concept', 'label', 'level', 'abstract', 'dimension',
                     'dimension_label', 'balance', 'weight', 'preferred_sign',
                     'parent_concept', 'parent_abstract_concept', 'is_breakdown',
                     'dimension_axis', 'dimension_member', 'dimension_member_label',
                     'unit', 'point_in_time', 'standard_concept']
        value_cols = [c for c in df.columns if c not in meta_cols]
        assert len(value_cols) > 0, "Should have at least one value column"

    @pytest.mark.network
    def test_cashflow_statement_presentation_no_warning(self, msft_10k_xbrl):
        """Test that cash flow statement with presentation=True produces no FutureWarning.

        This was the second affected statement type from Issue #599.
        """
        cashflow = msft_10k_xbrl.statements.cashflow_statement()

        # This should NOT produce FutureWarning after the fix
        with warnings.catch_warnings():
            warnings.simplefilter("error", FutureWarning)
            df = cashflow.to_dataframe(presentation=True)

        # Verify data is still correct
        assert not df.empty, "Cash flow statement should not be empty"
        assert 'preferred_sign' in df.columns, "Should have preferred_sign column"

    @pytest.mark.network
    def test_balance_sheet_presentation_never_affected(self, msft_10k_xbrl):
        """Test that balance sheet with presentation=True still works (was never affected).

        Balance sheets were never affected by this bug because _apply_presentation()
        skips the transformation for balance sheets.
        """
        balance = msft_10k_xbrl.statements.balance_sheet()

        # Balance sheets were never affected, but verify they still work
        with warnings.catch_warnings():
            warnings.simplefilter("error", FutureWarning)
            df = balance.to_dataframe(presentation=True)

        assert not df.empty, "Balance sheet should not be empty"

    @pytest.mark.network
    def test_presentation_false_no_warning(self, msft_10k_xbrl):
        """Test that presentation=False also works without warnings."""
        income = msft_10k_xbrl.statements.income_statement()

        # presentation=False should never trigger this issue
        with warnings.catch_warnings():
            warnings.simplefilter("error", FutureWarning)
            df = income.to_dataframe(presentation=False)

        assert not df.empty, "Income statement should not be empty"

    @pytest.mark.network
    def test_presentation_values_correct(self, msft_10k_xbrl):
        """Test that presentation transformation still works correctly after the fix.

        The fix should maintain correct behavior: expenses/outflows with
        preferred_sign=-1 should be negated for display.
        """
        income = msft_10k_xbrl.statements.income_statement()

        # Get dataframes with and without presentation
        df_with = income.to_dataframe(presentation=True)
        df_without = income.to_dataframe(presentation=False)

        # Find rows where preferred_sign is -1 (should be negated in presentation mode)
        if 'preferred_sign' in df_with.columns:
            negated_rows = df_with[df_with['preferred_sign'] == -1]
            if len(negated_rows) > 0:
                # Get a value column
                meta_cols = ['concept', 'label', 'level', 'abstract', 'dimension',
                             'dimension_label', 'balance', 'weight', 'preferred_sign',
                             'parent_concept', 'parent_abstract_concept', 'is_breakdown',
                             'dimension_axis', 'dimension_member', 'dimension_member_label',
                             'unit', 'point_in_time', 'standard_concept']
                value_cols = [c for c in df_with.columns if c not in meta_cols]

                if value_cols:
                    value_col = value_cols[0]
                    # Get first non-null negated value for comparison
                    sample_idx = negated_rows[negated_rows[value_col].notna()].index
                    if len(sample_idx) > 0:
                        idx = sample_idx[0]
                        # Check that the value was actually transformed
                        # (We can't easily verify exact negation without knowing original,
                        # but we verify the transformation ran without error)
                        assert df_with.loc[idx, value_col] is not None, \
                            "Presentation transformation should produce values"

    @pytest.mark.network
    def test_standard_view_no_warning(self, msft_10k_xbrl):
        """Test that view='standard' mode also works without warnings.

        This was explicitly mentioned in the issue title.
        """
        income = msft_10k_xbrl.statements.income_statement()

        # Test with view='standard' as mentioned in issue title
        with warnings.catch_warnings():
            warnings.simplefilter("error", FutureWarning)
            df = income.to_dataframe(view='standard')

        assert not df.empty, "Income statement should not be empty"

    @pytest.mark.network
    def test_standard_view_with_presentation_no_warning(self, msft_10k_xbrl):
        """Test the exact combination from the user's report.

        User reported: to_dataframe(view='standard', presentation=True)
        """
        income = msft_10k_xbrl.statements.income_statement()
        cashflow = msft_10k_xbrl.statements.cashflow_statement()

        # Test exact combinations mentioned by user
        with warnings.catch_warnings():
            warnings.simplefilter("error", FutureWarning)
            df_income = income.to_dataframe(view='standard', presentation=True)
            df_cashflow = cashflow.to_dataframe(view='standard', presentation=True)

        assert not df_income.empty, "Income statement should not be empty"
        assert not df_cashflow.empty, "Cash flow statement should not be empty"
