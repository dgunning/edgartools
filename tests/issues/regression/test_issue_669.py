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
        """Default to_dataframe() should apply preferred_sign (negate raw values)."""
        xbrl = azn_filing.xbrl()
        cf = xbrl.statements.cashflow_statement()
        if cf is None:
            pytest.skip("Cash flow statement not found")
        df_pres = cf.to_dataframe()  # presentation=True is default
        df_raw = cf.to_dataframe(presentation=False)

        if 'preferred_sign' not in df_pres.columns:
            pytest.skip("No preferred_sign column")

        period_cols = get_period_columns(df_pres)
        if not period_cols:
            pytest.skip("No period columns")

        # For rows with preferred_sign=-1, presentation values should be negated vs raw
        neg_mask = df_pres['preferred_sign'] == -1
        if not neg_mask.any():
            pytest.skip("No rows with preferred_sign=-1")

        col = period_cols[0]
        pres_val = df_pres.loc[neg_mask, col].dropna()
        raw_val = df_raw.loc[neg_mask, col].dropna()
        if pres_val.empty or raw_val.empty:
            pytest.skip("No non-null values to compare")

        # The key invariant: presentation flips the sign relative to raw
        assert pres_val.iloc[0] == -raw_val.iloc[0], (
            f"presentation=True should negate raw values for preferred_sign=-1. "
            f"pres={pres_val.iloc[0]}, raw={raw_val.iloc[0]}"
        )

    def test_presentation_false_returns_raw(self, azn_filing):
        """presentation=False should return unmodified XBRL instance values."""
        xbrl = azn_filing.xbrl()
        cf = xbrl.statements.cashflow_statement()
        if cf is None:
            pytest.skip("Cash flow statement not found")
        df_pres = cf.to_dataframe(presentation=True)
        df_raw = cf.to_dataframe(presentation=False)

        if 'preferred_sign' not in df_pres.columns:
            pytest.skip("No preferred_sign column")

        period_cols = get_period_columns(df_pres)
        if not period_cols:
            pytest.skip("No period columns")

        neg_mask = df_pres['preferred_sign'] == -1
        if not neg_mask.any():
            pytest.skip("No rows with preferred_sign=-1")

        col = period_cols[0]
        pres_val = df_pres.loc[neg_mask, col].dropna()
        raw_val = df_raw.loc[neg_mask, col].dropna()
        if pres_val.empty or raw_val.empty:
            pytest.skip("No non-null values to compare")

        # Raw and presentation should differ (sign flip)
        assert pres_val.iloc[0] != raw_val.iloc[0], (
            f"presentation=True and False should produce different values. "
            f"Both returned {pres_val.iloc[0]}"
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
        cf = financials.cashflow_statement()
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
        cf = financials.cashflow_statement()
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
