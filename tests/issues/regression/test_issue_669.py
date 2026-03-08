"""
Tests for Issue #669: to_dataframe() should apply preferred_sign by default.

The Rich rendering path already applied preferred_sign, but to_dataframe() returned
raw XBRL instance values by default (e.g., Interest Paid = +1,313M instead of -1,313M).

This fix:
1. Changes Statement.to_dataframe() default from presentation=False to presentation=True
2. Preserves preferred_sign through stitching so StitchedStatement.to_dataframe() also works
3. Adds BalanceSheet to _apply_presentation() for contra accounts (Treasury Stock)

GitHub Issue: https://github.com/dgunning/edgartools/issues/669
"""

import re

import pandas as pd
import pytest

from edgar import Company


def get_period_columns(df):
    """Get period columns (date format YYYY-MM-DD) from DataFrame."""
    date_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}$')
    return [col for col in df.columns if date_pattern.match(str(col))]


@pytest.mark.network
class TestIssue669PreferredSignInDataFrame:
    """Verify that to_dataframe() applies preferred_sign by default."""

    @pytest.fixture(scope="class")
    def azn_filing(self):
        """AstraZeneca 2024 10-K filing (uses InterestPaidNet with preferred_sign=-1)."""
        return Company("AZN").get_filings(form="20-F", year=2024).latest()

    def test_default_applies_preferred_sign(self, azn_filing):
        """Default to_dataframe() should show cash outflows as negative."""
        xbrl = azn_filing.xbrl()
        cf = xbrl.statements.cashflow_statement()
        if cf is None:
            pytest.skip("Cash flow statement not found")
        df = cf.to_dataframe()

        # Find an outflow concept that has preferred_sign=-1
        if 'preferred_sign' in df.columns:
            negative_rows = df[df['preferred_sign'] == -1]
            if not negative_rows.empty:
                period_cols = get_period_columns(df)
                if period_cols:
                    # With presentation=True (default), values with preferred_sign=-1 should be negative
                    row = negative_rows.iloc[0]
                    value = row[period_cols[0]]
                    if pd.notna(value) and value != 0:
                        assert value < 0, (
                            f"Default to_dataframe() should show outflows as negative. "
                            f"Got {value} for {row.get('concept', 'unknown')}"
                        )

    def test_presentation_false_returns_raw(self, azn_filing):
        """presentation=False should return raw positive XBRL instance values."""
        xbrl = azn_filing.xbrl()
        cf = xbrl.statements.cashflow_statement()
        if cf is None:
            pytest.skip("Cash flow statement not found")
        df = cf.to_dataframe(presentation=False)

        # Find an outflow concept that has preferred_sign=-1
        if 'preferred_sign' in df.columns:
            negative_rows = df[df['preferred_sign'] == -1]
            if not negative_rows.empty:
                period_cols = get_period_columns(df)
                if period_cols:
                    # With presentation=False, raw values should be positive
                    row = negative_rows.iloc[0]
                    value = row[period_cols[0]]
                    if pd.notna(value) and value != 0:
                        assert value > 0, (
                            f"presentation=False should return raw positive values. "
                            f"Got {value} for {row.get('concept', 'unknown')}"
                        )


@pytest.mark.network
class TestIssue669StitchedPreferredSign:
    """Verify that stitched statements also apply preferred_sign."""

    def test_stitched_dataframe_has_preferred_sign(self):
        """StitchedStatement.to_dataframe() should include preferred_sign column."""
        company = Company("AAPL")
        financials = company.get_financials()
        if financials is None:
            pytest.skip("Financials not available")
        cf = financials.cashflow_statement
        if cf is None:
            pytest.skip("Cash flow statement not available")
        df = cf.to_dataframe()
        assert 'preferred_sign' in df.columns, "Stitched DataFrame should include preferred_sign column"

    def test_stitched_dataframe_applies_signs(self):
        """StitchedStatement.to_dataframe() should apply preferred_sign by default."""
        company = Company("AAPL")
        financials = company.get_financials()
        if financials is None:
            pytest.skip("Financials not available")
        cf = financials.cashflow_statement
        if cf is None:
            pytest.skip("Cash flow statement not available")

        df_pres = cf.to_dataframe(presentation=True)
        df_raw = cf.to_dataframe(presentation=False)

        # Find rows with preferred_sign=-1
        if 'preferred_sign' in df_pres.columns:
            neg_mask = df_pres['preferred_sign'] == -1
            period_cols = get_period_columns(df_pres)
            if neg_mask.any() and period_cols:
                col = period_cols[0]
                # For rows with preferred_sign=-1, presentation values should be negated vs raw
                pres_val = df_pres.loc[neg_mask, col].dropna().iloc[0] if not df_pres.loc[neg_mask, col].dropna().empty else None
                raw_val = df_raw.loc[neg_mask, col].dropna().iloc[0] if not df_raw.loc[neg_mask, col].dropna().empty else None
                if pres_val is not None and raw_val is not None and raw_val != 0:
                    assert pres_val == -raw_val, (
                        f"Stitched presentation values should be negated vs raw. "
                        f"pres={pres_val}, raw={raw_val}"
                    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
