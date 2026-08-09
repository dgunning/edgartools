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

import pandas as pd
import pytest

# Everything to_dataframe() emits that is not a period column.
META_COLS = ['concept', 'label', 'level', 'abstract', 'dimension',
             'dimension_label', 'balance', 'weight', 'preferred_sign',
             'parent_concept', 'parent_abstract_concept', 'is_breakdown',
             'dimension_axis', 'dimension_member', 'dimension_member_label',
             'unit', 'point_in_time', 'standard_concept']


def value_columns(df):
    return [c for c in df.columns if c not in META_COLS]


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
        assert len(value_columns(df)) > 0, "Should have at least one value column"

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
        """The transformation negates exactly the preferred_sign=-1 rows.

        WHAT THIS USED TO BE. Four nested ``if``s ending in ``assert
        df_with.loc[idx, value_col] is not None``, on the INCOME statement --
        which for MSFT has no preferred_sign=-1 rows at all (44 rows at +1, two
        null). Every run took the outermost false branch and asserted nothing.
        Its own comment conceded the point: "we can't easily verify exact
        negation without knowing the original".

        The original is one call away. ``to_dataframe(presentation=False)``
        returns the same rows untransformed, so negation is checkable exactly,
        for every row and every period, without pinning a single figure -- which
        matters because the fixture is MSFT's *latest* 10-K and its numbers move
        every year.

        The cash flow statement is the one to check: it is where the sign flips
        live (working-capital movements, debt repayments), and it was the second
        statement named in #599.
        """
        cashflow = msft_10k_xbrl.statements.cashflow_statement()
        df_with = cashflow.to_dataframe(presentation=True)
        df_without = cashflow.to_dataframe(presentation=False)

        assert list(df_with.index) == list(df_without.index), \
            "presentation changed the row set, so rows cannot be compared pairwise"
        assert 'preferred_sign' in df_with.columns
        cols = value_columns(df_with)
        assert cols, "no period columns to compare"

        negated = 0
        for col in cols:
            for idx in df_with.index:
                raw = pd.to_numeric(df_without.loc[idx, col], errors='coerce')
                shown = pd.to_numeric(df_with.loc[idx, col], errors='coerce')
                if pd.isna(raw):
                    continue
                sign = df_with.loc[idx, 'preferred_sign']
                label = df_with.loc[idx, 'label']
                if sign == -1:
                    assert shown == -raw, (
                        f"{label!r} [{col}] has preferred_sign=-1 but displays "
                        f"{shown} against an underlying {raw}"
                    )
                    negated += 1
                else:
                    assert shown == raw, (
                        f"{label!r} [{col}] has preferred_sign={sign} and must "
                        f"display unchanged, but shows {shown} against {raw}"
                    )

        assert negated > 0, (
            "no preferred_sign=-1 values were found in MSFT's cash flow "
            "statement, so the negation this test exists to check never ran. "
            "That is how the income-statement version of this test passed "
            "without asserting anything."
        )

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
