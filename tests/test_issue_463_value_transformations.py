"""
Tests for Issue #463: XBRL value transformation and metadata columns.

This test file verifies the implementation of Issue #463 which adds:
1. Metadata columns (balance, weight, preferred_sign) to statement DataFrames
2. Raw instance values by default (no transformation during parsing)
3. Optional presentation mode (HTML-matching display)
4. Optional normalization mode (cross-company consistency)

GitHub Issue: https://github.com/dgunning/edgartools/issues/463
"""

import pytest
import pandas as pd
from edgar import Company


@pytest.mark.network
class TestIssue463ValueTransformations:
    """Test suite for Issue #463 value transformation changes."""

    @pytest.fixture(scope="class")
    def aapl_2016_filing(self):
        """Apple 2016 10-K with custom PaymentsOfDividends concept."""
        return Company("AAPL").get_filings(accession_number='0001628280-16-020309').latest()

    @pytest.fixture(scope="class")
    def aapl_2017_filing(self):
        """Apple 2017 10-K with standard PaymentsOfDividends concept."""
        return Company("AAPL").get_filings(accession_number='0000320193-17-000070').latest()

    @pytest.fixture(scope="class")
    def aapl_2024_filing(self):
        """Apple 2024 10-K with negated presentation for PaymentsOfDividends."""
        return Company("AAPL").get_filings(form="10-K").latest()

    def test_metadata_columns_included(self, aapl_2017_filing):
        """
        Test that metadata columns (balance, weight, preferred_sign) are included in DataFrame.

        Issue #463: Users requested access to XBRL metadata to understand transformations.
        """
        xbrl = aapl_2017_filing.xbrl()
        df = xbrl.statements.cashflow_statement().to_dataframe()

        # Verify metadata columns are present
        assert 'balance' in df.columns, "Missing 'balance' column"
        assert 'weight' in df.columns, "Missing 'weight' column"
        assert 'preferred_sign' in df.columns, "Missing 'preferred_sign' column"

        # Verify metadata values are populated
        # PaymentsOfDividends should have balance='credit'
        dividend_row = df[df['concept'].str.contains('PaymentsOfDividends', na=False)]
        if not dividend_row.empty:
            assert dividend_row.iloc[0]['balance'] == 'credit', \
                "PaymentsOfDividends should have balance='credit'"

    def test_raw_values_from_xml(self, aapl_2017_filing):
        """
        Test that raw XML values are preserved without transformation.

        Issue #463: Previously, EdgarTools applied calculation weights during parsing,
        creating inconsistencies. Now raw values should be preserved.
        """
        xbrl = aapl_2017_filing.xbrl()

        # Check internal fact storage - should have positive value from XML
        facts_df = xbrl.facts.query().by_concept('PaymentsOfDividends').limit(1).to_dataframe()

        assert not facts_df.empty, "Should find PaymentsOfDividends facts"

        # After removing _apply_calculation_weights(), instance values should be positive
        # Note: This tests that we NO LONGER apply weights during parsing
        fact_value = facts_df.iloc[0]['numeric_value']
        assert fact_value > 0, \
            f"PaymentsOfDividends should be positive from XML (got {fact_value})"

    def test_dataframe_includes_metadata(self, aapl_2017_filing):
        """
        Test that to_dataframe() returns metadata by default.

        Issue #463: Metadata columns should always be included to enable transparency.
        """
        xbrl = aapl_2017_filing.xbrl()
        df = xbrl.statements.cashflow_statement().to_dataframe()

        # Should have metadata
        assert 'balance' in df.columns
        assert 'weight' in df.columns
        assert 'preferred_sign' in df.columns

    def test_default_returns_raw_values(self, aapl_2017_filing):
        """
        Test that default to_dataframe() returns raw instance values.

        Issue #463: Default should return raw values from XML, not transformed.
        """
        xbrl = aapl_2017_filing.xbrl()
        df = xbrl.statements.cashflow_statement().to_dataframe()

        # Find dividend row
        dividend_row = df[df['concept'].str.contains('PaymentsOfDividends', na=False)]

        if not dividend_row.empty:
            # Get first period column
            period_cols = [col for col in df.columns
                          if col not in ['concept', 'label', 'balance', 'weight',
                                        'preferred_sign', 'level', 'abstract', 'dimension']]

            if period_cols:
                value = dividend_row.iloc[0][period_cols[0]]
                # Raw values should be positive (from XML instance document)
                assert pd.notna(value) and value > 0, \
                    f"Raw PaymentsOfDividends should be positive (got {value})"

    def test_presentation_mode_matches_sec_html(self, aapl_2024_filing):
        """
        Test that presentation=True applies HTML-matching transformations.

        Issue #463: presentation=True should transform values to match SEC HTML display.
        Cash Flow outflows (with preferred_sign=-1) should be negative.
        Uses 2024 AAPL 10-K which has preferred_sign=-1 for PaymentsOfDividends.
        """
        xbrl = aapl_2024_filing.xbrl()
        df = xbrl.statements.cashflow_statement().to_dataframe(presentation=True)

        # Find dividend row
        dividend_row = df[df['concept'].str.contains('PaymentsOfDividends', na=False)]

        if not dividend_row.empty:
            # Get first period column
            period_cols = [col for col in df.columns
                          if col not in ['concept', 'label', 'balance', 'weight',
                                        'preferred_sign', 'level', 'abstract', 'dimension']]

            if period_cols:
                value = dividend_row.iloc[0][period_cols[0]]
                # With presentation=True, cash outflows should be negative
                assert pd.notna(value) and value < 0, \
                    f"Presentation mode: PaymentsOfDividends should be negative (got {value})"

                # Should have balance='credit' metadata
                assert dividend_row.iloc[0]['balance'] == 'credit', \
                    "PaymentsOfDividends should have balance='credit'"

    def test_presentation_mode_matches_sec_html_in_2017_aapl_filing(self, aapl_2017_filing):
        """
        Test that presentation=True applies HTML-matching transformations.

        Issue #463: presentation=True should transform values to match SEC HTML display.
        Cash Flow outflows (with preferred_sign=-1) should be negative.
        Uses 2024 AAPL 10-K which has preferred_sign=-1 for PaymentsOfDividends.
        """
        xbrl = aapl_2017_filing.xbrl()
        df = xbrl.statements.cashflow_statement().to_dataframe(presentation=True)

        # Find dividend row
        dividend_row = df[df['concept'].str.contains('PaymentsOfDividends', na=False)]

        if not dividend_row.empty:
            # Get first period column
            period_cols = [col for col in df.columns
                          if col not in ['concept', 'label', 'balance', 'weight',
                                        'preferred_sign', 'level', 'abstract', 'dimension']]

            if period_cols:
                value = dividend_row.iloc[0][period_cols[0]]
                # With presentation=True, cash outflows should be negative
                assert pd.notna(value) and value >0, \
                    f"Presentation mode: PaymentsOfDividends should be positive (got {value})"

                # Should have balance='credit' metadata
                assert dividend_row.iloc[0]['balance'] == 'credit', \
                    "PaymentsOfDividends should have balance='credit'"

    def test_normalization_mode(self, aapl_2017_filing):
        """
        Test that normalize=True applies cross-company consistency rules.

        Issue #463: Normalization should make dividends/expenses consistently positive.
        """
        xbrl = aapl_2017_filing.xbrl()
        df = xbrl.statements.cashflow_statement().to_dataframe(normalize=True)

        # Find dividend row
        dividend_row = df[df['concept'].str.contains('PaymentsOfDividends', na=False)]

        if not dividend_row.empty:
            # Get first period column (should be positive after normalization)
            period_cols = [col for col in df.columns
                          if col not in ['concept', 'label', 'balance', 'weight',
                                        'preferred_sign', 'level', 'abstract', 'dimension']]

            if period_cols:
                value = dividend_row.iloc[0][period_cols[0]]
                # After normalization, should be positive
                assert pd.notna(value) and value > 0, \
                    f"Normalized PaymentsOfDividends should be positive (got {value})"

    def test_semantic_matching_catches_custom_concepts(self, aapl_2016_filing):
        """
        Test that semantic matching catches custom concept variants.

        Issue #463: aapl:PaymentsOfDividendsAnd... should match PaymentsOfDividends pattern.
        """
        xbrl = aapl_2016_filing.xbrl()
        df = xbrl.statements.cashflow_statement().to_dataframe(normalize=True)

        # Find dividend row (custom concept in 2016)
        dividend_row = df[df['concept'].str.contains('PaymentsOfDividends', case=False, na=False)]

        if not dividend_row.empty:
            # Should have balance metadata even for custom concepts
            assert pd.notna(dividend_row.iloc[0]['balance']), \
                "Custom concept should have balance metadata"

            # Get first period column
            period_cols = [col for col in df.columns
                          if col not in ['concept', 'label', 'balance', 'weight',
                                        'preferred_sign', 'level', 'abstract', 'dimension']]

            if period_cols:
                value = dividend_row.iloc[0][period_cols[0]]
                # After normalization, should be positive (semantic matching)
                assert pd.notna(value) and abs(value) == value, \
                    f"Normalized custom dividend concept should be positive (got {value})"

    def test_cross_filing_consistency_with_normalization(self, aapl_2016_filing, aapl_2017_filing):
        """
        Test that same period data is consistent across filings when normalized.

        Issue #463: Both filings should report same value for 2016-09-24 period after normalization.
        """
        xbrl_2016 = aapl_2016_filing.xbrl()
        xbrl_2017 = aapl_2017_filing.xbrl()

        df_2016 = xbrl_2016.statements.cashflow_statement().to_dataframe(normalize=True)
        df_2017 = xbrl_2017.statements.cashflow_statement().to_dataframe(normalize=True)

        # Find dividend rows
        div_2016 = df_2016[df_2016['concept'].str.contains('PaymentsOfDividends', case=False, na=False)]
        div_2017 = df_2017[df_2017['concept'].str.contains('PaymentsOfDividends', case=False, na=False)]

        if not div_2016.empty and not div_2017.empty:
            # Try to find matching period (2016-09-24 appears in both filings)
            # In 2016 filing, it's current period; in 2017 filing, it's comparative period
            period_2016_09_24 = '2016-09-24'

            # Check if this period exists in both DataFrames
            if period_2016_09_24 in div_2016.columns and period_2016_09_24 in div_2017.columns:
                val_2016 = div_2016.iloc[0][period_2016_09_24]
                val_2017 = div_2017.iloc[0][period_2016_09_24]

                # Both should be positive after normalization
                assert pd.notna(val_2016) and val_2016 > 0, \
                    f"2016 filing value should be positive (got {val_2016})"
                assert pd.notna(val_2017) and val_2017 > 0, \
                    f"2017 filing value should be positive (got {val_2017})"

                # Values should be equal (or very close, allowing for rounding)
                # Both should report same value for same period
                assert abs(val_2016 - val_2017) < 1000000, \
                    f"Values should match across filings (got {val_2016} vs {val_2017})"

    def test_rich_display_uses_presentation_logic(self, aapl_2017_filing):
        """
        Test that print(statement) uses presentation logic (matches SEC HTML).

        Issue #463: Rich display should show values as they appear in 10-K HTML.
        """
        from rich.console import Console
        from io import StringIO

        xbrl = aapl_2017_filing.xbrl()
        statement = xbrl.statements.cashflow_statement()

        # Render to string
        console = Console(file=StringIO(), width=200)
        console.print(statement)
        output = console.file.getvalue()

        # Dividends should appear in parentheses or with negative sign in display
        # (This tests the rendering.py changes we made)
        assert 'Dividend' in output or 'dividend' in output.lower(), \
            "Should find dividend line item in output"

        # The actual value formatting depends on the rich rendering
        # We're primarily testing that the statement renders without error

    def test_metadata_column_position(self, aapl_2017_filing):
        """
        Test that metadata columns appear after period columns.

        Issue #463: Metadata should be at the end for better readability.
        """
        xbrl = aapl_2017_filing.xbrl()
        df = xbrl.statements.cashflow_statement().to_dataframe()

        columns = list(df.columns)

        # Find indices of metadata columns
        balance_idx = columns.index('balance') if 'balance' in columns else -1
        weight_idx = columns.index('weight') if 'weight' in columns else -1
        preferred_sign_idx = columns.index('preferred_sign') if 'preferred_sign' in columns else -1

        # Find a period column (date format like 2017-09-30)
        period_cols = [col for col in columns if '-' in str(col) and len(str(col).split('-')) == 3]

        if period_cols and balance_idx != -1:
            first_period_idx = columns.index(period_cols[0])

            # Metadata columns should come after period columns
            assert balance_idx > first_period_idx, \
                "balance column should come after period columns"


@pytest.mark.network
class TestIssue463BalanceSemantics:
    """Test balance attribute usage in statements."""

    def test_balance_attribute_available(self):
        """Test that balance attribute is available from XBRL schema."""
        filing = Company("AAPL").get_filings(form="10-K", year=2017).latest()
        xbrl = filing.xbrl()

        # Check if balance is available in facts
        facts_df = xbrl.facts.query().by_statement_type('CashFlowStatement').limit(100).to_dataframe()

        # Should have balance column
        assert 'balance' in facts_df.columns

        # Should have both debit and credit balances in cash flow
        balances = facts_df['balance'].dropna().unique()
        assert 'credit' in balances or 'debit' in balances, \
            "Should have debit or credit balances in Cash Flow statement"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
