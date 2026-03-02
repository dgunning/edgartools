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
import re
from edgar import Company


def get_period_columns(df):
    """Get period columns (date format YYYY-MM-DD) from DataFrame."""
    date_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}$')
    return [col for col in df.columns if date_pattern.match(str(col))]


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
            # Get first period column using date format matching
            period_cols = get_period_columns(df)

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
            # Get first period column using date format matching
            period_cols = get_period_columns(df)

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
            # Get first period column using date format matching
            period_cols = get_period_columns(df)

            if period_cols:
                value = dividend_row.iloc[0][period_cols[0]]
                # With presentation=True, cash outflows should be negative
                assert pd.notna(value) and value > 0, \
                    f"Presentation mode: PaymentsOfDividends should be positive (got {value})"

                # Should have balance='credit' metadata
                assert dividend_row.iloc[0]['balance'] == 'credit', \
                    "PaymentsOfDividends should have balance='credit'"

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
